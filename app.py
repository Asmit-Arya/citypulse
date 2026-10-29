"""CityPulse Flask application.

Local development defaults to demo login. Configure GOOGLE_CLIENT_ID and
SESSION_SECRET in the environment before deploying with real users.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
import hashlib
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from pathlib import Path
from functools import wraps

from werkzeug.security import generate_password_hash, check_password_hash

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = Path(os.getenv("CITYPULSE_DB_PATH", str(BASE_DIR / "citypulse.db")))

from calibration import update_service_ema, calculate_dynamic_queue_wait
from ai_service import get_ai_ticket_modifier

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SESSION_SECRET", "citypulse-dev-only-change-this-secret"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
    JSON_SORT_KEYS=False,
)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
DEMO_LOGIN_ENABLED = os.getenv("ENABLE_DEMO_LOGIN", "true").lower() == "true"
MERCHANT_EMAILS = {email.strip().lower() for email in os.getenv("MERCHANT_EMAILS", "").split(",") if email.strip()}
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME).strip()
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"


def now_string() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=8)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    return conn


def ensure_schema() -> None:
    """Create the database if needed and migrate existing CityPulse databases."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            city TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            current_queue INTEGER NOT NULL DEFAULT 0,
            active_counters INTEGER NOT NULL DEFAULT 1
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            current_estimated_duration REAL NOT NULL DEFAULT 15,
            total_completed_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS queue_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            notes TEXT,
            is_walkin INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'waiting',
            ai_duration_modifier REAL NOT NULL DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        )""")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(queue_tickets)").fetchall()}
        if "customer_key" not in columns:
            conn.execute("ALTER TABLE queue_tickets ADD COLUMN customer_key TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_business_status_created ON queue_tickets(business_id, status, created_at, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_customer_key ON queue_tickets(customer_key, created_at)")
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            created_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reset_tokens_user ON password_reset_tokens(user_id, expires_at)")
        count = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO businesses(name, category, city, status, active_counters) VALUES (?, ?, ?, ?, ?)",
                [
                    ("Urban Cut Studio", "Salon", "Raipur", "open", 1),
                    ("Apex Dental Clinic", "Healthcare", "Raipur", "open", 1),
                    ("Metro Auto Workshop", "Automotive", "Bhilai", "busy", 2),
                ],
            )
            conn.executemany("INSERT INTO services(business_id, name, current_estimated_duration) VALUES (?, ?, ?)", [
                (1, "Standard Haircut", 20),
                (1, "Beard Trim & Lineup", 10),
                (1, "Hair Color & Styling", 45),
                (2, "Dental Consultation", 20),
                (2, "Dental Cleaning", 35),
                (3, "Quick Repair", 30),
                (3, "General Vehicle Service", 50),
            ])
        conn.commit()
    finally:
        conn.close()


ensure_schema()


def current_user():
    return session.get("user")


def require_login(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "Please sign in to continue."}), 401
        return fn(*args, **kwargs)
    return wrapped


def require_merchant(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "Please sign in to continue."}), 401
        if user.get("role") != "merchant":
            return jsonify({"error": "Your server session is not authorized for the merchant workspace. Sign out, then sign in with an authorized merchant account."}), 403
        return fn(*args, **kwargs)
    return wrapped


def ensure_customer_key() -> str:
    key = session.get("customer_key")
    if not key:
        key = str(uuid.uuid4())
        session["customer_key"] = key
    return key


def ticket_display(ticket: sqlite3.Row | dict) -> dict:
    item = dict(ticket)
    item.pop("customer_key", None)
    item["status_label"] = {
        "pending_confirmation": "Waiting for merchant",
        "waiting": "Confirmed · in queue",
        "in_service": "Your service is in progress",
        "completed": "Completed",
        "declined": "Declined by merchant",
    }.get(item.get("status"), item.get("status", "Unknown").replace("_", " ").title())
    return item


def refresh_business_count(conn: sqlite3.Connection, business_id: int) -> int:
    count = conn.execute("SELECT COUNT(*) FROM queue_tickets WHERE business_id = ? AND status IN ('waiting','in_service')", (business_id,)).fetchone()[0]
    conn.execute("UPDATE businesses SET current_queue = ? WHERE id = ?", (count, business_id))
    return count


def business_exists(conn, business_id):
    return conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()


@app.get("/")
def home():
    return render_template("index.html", google_client_id=GOOGLE_CLIENT_ID, demo_login_enabled=DEMO_LOGIN_ENABLED)


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "CityPulse"}), 200


@app.get("/api/config")
def api_config():
    return jsonify({"google_client_id": GOOGLE_CLIENT_ID, "demo_login_enabled": DEMO_LOGIN_ENABLED})


@app.get("/api/me")
def api_me():
    user = current_user()
    if not user:
        return jsonify({"authenticated": False, "google_enabled": bool(GOOGLE_CLIENT_ID), "demo_login_enabled": DEMO_LOGIN_ENABLED})
    return jsonify({"authenticated": True, "user": user, "google_enabled": bool(GOOGLE_CLIENT_ID), "demo_login_enabled": DEMO_LOGIN_ENABLED})


@app.post("/api/auth/guest")
def auth_guest():
    """Local/demo login. This is intentionally not a password-authenticated account."""
    if not DEMO_LOGIN_ENABLED:
        return jsonify({"error": "Demo login is disabled. Please use Google sign-in or an account."}), 403
    data = request.get_json(silent=True) or {}
    role = data.get("role", "customer")
    if role not in ("customer", "merchant"):
        return jsonify({"error": "Invalid demo role."}), 400
    supplied_name = str(data.get("name") or "").strip()[:100]
    default_name = "Demo Customer" if role == "customer" else "CityPulse Merchant"
    display_name = supplied_name or default_name
    session.clear()
    session.permanent = bool(data.get("remember", True))
    session["customer_key"] = str(uuid.uuid4())
    session["user"] = {
        "id": f"demo-{role}-{uuid.uuid4().hex[:8]}",
        "name": display_name,
        "email": None,
        "picture": None,
        "provider": "demo",
        "role": role,
    }
    return jsonify({"authenticated": True, "user": session["user"]}), 200


@app.post("/api/auth/register")
def auth_register():
    """Create a real password-based customer account."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()[:100]
    email = str(data.get("email") or "").strip().lower()[:254]
    password = str(data.get("password") or "")
    if len(name) < 2:
        return jsonify({"error": "Please enter your full name."}), 400
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Use a password with at least 8 characters."}), 400
    if data.get("role", "customer") != "customer":
        return jsonify({"error": "Merchant accounts must be authorized separately."}), 403
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
            (name, email, generate_password_hash(password), "customer", now_string()),
        )
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "An account with this email already exists. Please sign in."}), 409
    conn.close()
    session.clear()
    session.permanent = bool(data.get("remember", True))
    session["customer_key"] = str(uuid.uuid4())
    session["user"] = {
        "id": f"account-{user_id}", "name": name, "email": email,
        "picture": None, "provider": "password", "role": "customer"
    }
    return jsonify({"authenticated": True, "user": session["user"]}), 201


@app.post("/api/auth/login")
def auth_password_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()[:254]
    password = str(data.get("password") or "")
    requested_role = data.get("role", "customer")
    if requested_role not in ("customer", "merchant"):
        return jsonify({"error": "Invalid account type."}), 400
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    conn.close()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "The email or password is incorrect."}), 401
    if requested_role != row["role"]:
        return jsonify({"error": "This account is not authorized for the selected workspace. Merchants must be authorized by the CityPulse administrator."}), 403
    session.clear()
    session.permanent = bool(data.get("remember", True))
    session["customer_key"] = str(uuid.uuid4())
    session["user"] = {
        "id": f"account-{row['id']}", "name": row["name"],
        "email": row["email"], "picture": None, "provider": "password",
        "role": row["role"]
    }
    return jsonify({"authenticated": True, "user": session["user"]}), 200


def _send_reset_email(recipient: str, reset_url: str) -> None:
    if not (SMTP_HOST and SMTP_FROM):
        raise RuntimeError("Password reset email is not configured. Add SMTP_HOST and SMTP_FROM to .env.")
    message = EmailMessage()
    message["Subject"] = "Reset your CityPulse password"
    message["From"] = SMTP_FROM
    message["To"] = recipient
    message.set_content(
        "We received a request to reset your CityPulse password. "
        "Open this link within 60 minutes to choose a new password:\n\n"
        f"{reset_url}\n\nIf you did not request this, ignore this email."
    )
    if SMTP_USE_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)


@app.post("/api/auth/forgot-password")
def auth_forgot_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()[:254]
    if "@" not in email:
        return jsonify({"error": "Enter a valid email address."}), 400
    if not (SMTP_HOST and SMTP_FROM):
        return jsonify({"error": "Password reset email is not configured yet. Configure SMTP_HOST, SMTP_FROM, SMTP_PORT, SMTP_USERNAME and SMTP_PASSWORD in .env."}), 503
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    if row:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO password_reset_tokens(user_id,token_hash,expires_at,created_at) VALUES (?,?,?,?)", (row["id"], token_hash, expires, now_string()))
        conn.commit()
        reset_url = request.url_root.rstrip("/") + "/?" + urlencode({"reset_token": token, "email": email})
        try:
            _send_reset_email(email, reset_url)
        except (OSError, smtplib.SMTPException, RuntimeError):
            app.logger.exception("Unable to send CityPulse password reset email")
            conn.close()
            return jsonify({"error": "Could not send the reset email. Check the SMTP settings in .env."}), 502
    conn.close()
    # Same response whether or not the email exists to reduce account enumeration.
    return jsonify({"message": "If an account exists for that email, a password reset link has been sent."}), 200


@app.post("/api/auth/reset-password")
def auth_reset_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()[:254]
    token = str(data.get("token") or "")
    password = str(data.get("password") or "")
    if len(password) < 8:
        return jsonify({"error": "Use a password with at least 8 characters."}), 400
    if not email or not token:
        return jsonify({"error": "This reset link is incomplete."}), 400
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = now_string()
    conn = get_db()
    row = conn.execute("""
        SELECT rt.id AS reset_id, u.id AS user_id FROM password_reset_tokens rt
        JOIN users u ON u.id = rt.user_id
        WHERE u.email = ? COLLATE NOCASE AND rt.token_hash = ?
          AND rt.used_at IS NULL AND rt.expires_at >= ?
        ORDER BY rt.id DESC LIMIT 1
    """, (email, token_hash, now)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "This reset link is invalid or has expired. Request a new one."}), 400
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), row["user_id"]))
    conn.execute("UPDATE password_reset_tokens SET used_at = ? WHERE id = ?", (now, row["reset_id"]))
    conn.commit()
    conn.close()
    return jsonify({"message": "Password reset successfully. You can now sign in."}), 200


@app.post("/api/auth/google")
def auth_google():
    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "Google sign-in has not been configured yet. Add GOOGLE_CLIENT_ID to your .env file."}), 503
    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    if not credential or not isinstance(credential, str):
        return jsonify({"error": "Google did not return a sign-in credential."}), 400
    try:
        # Google verifies the signature and expiration on this HTTPS endpoint;
        # we independently check that the token was issued to this application.
        verify_response = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credential}, timeout=5,
        )
        if verify_response.status_code != 200:
            return jsonify({"error": "Google could not verify this sign-in. Please try again."}), 401
        profile = verify_response.json()
        if profile.get("aud") != GOOGLE_CLIENT_ID or profile.get("email_verified") not in (True, "true") or not profile.get("sub"):
            return jsonify({"error": "Google sign-in verification failed for this application."}), 401
        session.clear()
        session.permanent = bool(data.get("remember", True))
        session["customer_key"] = str(uuid.uuid4())
        session["user"] = {
            "id": profile["sub"],
            "name": profile.get("name") or profile.get("email", "CityPulse User").split("@")[0],
            "email": profile.get("email"),
            "picture": profile.get("picture"),
            "provider": "google",
            "role": "customer",
        }
        return jsonify({"authenticated": True, "user": session["user"]}), 200
    except requests.RequestException:
        app.logger.exception("Google token verification request failed")
        return jsonify({"error": "Could not reach Google to verify sign-in. Try again."}), 502


@app.put("/api/auth/role")
@require_login
def auth_role():
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    if role not in ("customer", "merchant"):
        return jsonify({"error": "Invalid account view."}), 400
    existing_user = session.get("user", {})
    if role == "merchant":
        provider = existing_user.get("provider")
        if provider == "demo":
            if not DEMO_LOGIN_ENABLED:
                return jsonify({"error": "Demo merchant access is disabled."}), 403
        elif provider == "google":
            if (existing_user.get("email") or "").lower() not in MERCHANT_EMAILS:
                return jsonify({"error": "This Google account is not enabled for merchant access yet."}), 403
        else:
            return jsonify({"error": "This account is not authorized for merchant access."}), 403
    user = dict(session["user"])
    user["role"] = role
    session["user"] = user
    ensure_customer_key()
    return jsonify({"user": user}), 200


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify({"ok": True}), 200


@app.get("/api/businesses")
def api_get_businesses():
    city = (request.args.get("city") or "").strip()
    category = (request.args.get("category") or "").strip()
    conn = get_db()
    query = "SELECT * FROM businesses WHERE 1=1"
    params = []
    if city:
        query += " AND city = ?"
        params.append(city)
    if category:
        query += " AND category = ?"
        params.append(category)
    rows = conn.execute(query + " ORDER BY name", params).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["current_queue"] = conn.execute(
            "SELECT COUNT(*) FROM queue_tickets WHERE business_id = ? AND status IN ('waiting','in_service')", (row["id"],)
        ).fetchone()[0]
        services = conn.execute("SELECT id, name, current_estimated_duration FROM services WHERE business_id = ? ORDER BY id", (row["id"],)).fetchall()
        item["services"] = [dict(s) for s in services]
        item["wait_stats"] = calculate_dynamic_queue_wait(row["id"])
        results.append(item)
    conn.close()
    return jsonify(results), 200


@app.get("/api/businesses/<int:business_id>/queue")
@require_merchant
def get_merchant_queue(business_id):
    conn = get_db()
    if not business_exists(conn, business_id):
        conn.close()
        return jsonify({"error": "Business not found."}), 404
    active = conn.execute("""
        SELECT q.*, s.name AS service_name, s.current_estimated_duration
        FROM queue_tickets q JOIN services s ON q.service_id = s.id
        WHERE q.business_id = ? AND q.status = 'in_service'
        ORDER BY q.started_at ASC, q.id ASC LIMIT 1
    """, (business_id,)).fetchone()
    waiting = conn.execute("""
        SELECT q.*, s.name AS service_name, s.current_estimated_duration
        FROM queue_tickets q JOIN services s ON q.service_id = s.id
        WHERE q.business_id = ? AND q.status = 'waiting'
        ORDER BY q.created_at ASC, q.id ASC
    """, (business_id,)).fetchall()
    pending = conn.execute("""
        SELECT q.*, s.name AS service_name, s.current_estimated_duration
        FROM queue_tickets q JOIN services s ON q.service_id = s.id
        WHERE q.business_id = ? AND q.status = 'pending_confirmation'
        ORDER BY q.created_at ASC, q.id ASC
    """, (business_id,)).fetchall()
    completed_today = conn.execute("""
        SELECT COUNT(*) FROM queue_tickets WHERE business_id = ? AND status = 'completed'
        AND date(completed_at) = date('now')
    """, (business_id,)).fetchone()[0]
    biz = business_exists(conn, business_id)
    count = refresh_business_count(conn, business_id)
    conn.commit()
    conn.close()
    return jsonify({
        "business": {"id": biz["id"], "name": biz["name"], "status": biz["status"], "current_queue": count},
        "active_patron": ticket_display(active) if active else None,
        "waiting_list": [ticket_display(t) for t in waiting],
        "pending_bookings": [ticket_display(t) for t in pending],
        "wait_stats": calculate_dynamic_queue_wait(business_id),
        "completed_today": completed_today,
    }), 200


@app.post("/api/walkin")
@require_merchant
def add_walkin():
    data = request.get_json(silent=True) or {}
    try:
        b_id = int(data.get("business_id", 1))
        s_id = int(data.get("service_id", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Choose a valid business and service."}), 400
    name = (data.get("customer_name") or "").strip()[:80]
    use_queue_number = bool(data.get("use_queue_number"))
    conn = get_db()
    biz = business_exists(conn, b_id)
    service = conn.execute("SELECT * FROM services WHERE id = ? AND business_id = ?", (s_id, b_id)).fetchone()
    if not biz or not service:
        conn.close()
        return jsonify({"error": "Business or service was not found."}), 404
    queue_position = conn.execute("SELECT COUNT(*) FROM queue_tickets WHERE business_id = ? AND status IN ('waiting','in_service')", (b_id,)).fetchone()[0] + 1
    display_name = f"#{queue_position}" if use_queue_number or not name else name
    cursor = conn.execute("""
        INSERT INTO queue_tickets (business_id, service_id, customer_name, is_walkin, status, created_at)
        VALUES (?, ?, ?, 1, 'waiting', ?)
    """, (b_id, s_id, display_name, now_string()))
    ticket_id = cursor.lastrowid
    refresh_business_count(conn, b_id)
    conn.commit()
    conn.close()
    return jsonify({"message": f"{display_name} added to the queue.", "ticket_id": ticket_id, "queue_number": queue_position}), 201


@app.post("/api/appointments")
@require_login
def book_appointment():
    data = request.get_json(silent=True) or {}
    try:
        b_id = int(data.get("business_id"))
        s_id = int(data.get("service_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Choose a valid business and service."}), 400
    user = current_user() or {}
    name = (data.get("customer_name") or user.get("name") or "").strip()[:80]
    notes = (data.get("notes") or "").strip()[:500]
    if not name:
        return jsonify({"error": "Please enter the name for this booking."}), 400
    conn = get_db()
    biz = business_exists(conn, b_id)
    service = conn.execute("SELECT * FROM services WHERE id = ? AND business_id = ?", (s_id, b_id)).fetchone()
    if not biz or not service:
        conn.close()
        return jsonify({"error": "This service is not available at that business."}), 404
    if biz["status"] == "closed":
        conn.close()
        return jsonify({"error": "This business is currently closed to new bookings."}), 409
    # The notes triage helper uses a fast local fallback unless optional AI is configured.
    ai_modifier = get_ai_ticket_modifier(service["name"], notes)
    cursor = conn.execute("""
        INSERT INTO queue_tickets (business_id, service_id, customer_name, notes, is_walkin,
            status, ai_duration_modifier, created_at, customer_key)
        VALUES (?, ?, ?, ?, 0, 'pending_confirmation', ?, ?, ?)
    """, (b_id, s_id, name, notes, ai_modifier, now_string(), ensure_customer_key()))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({
        "message": "Booking request sent. Waiting for the merchant to confirm.",
        "ticket_id": ticket_id,
        "status": "pending_confirmation",
        "business_name": biz["name"],
        "service_name": service["name"],
        "estimated_wait": calculate_dynamic_queue_wait(b_id)["display"],
    }), 201


@app.get("/api/my-bookings")
@require_login
def my_bookings():
    key = ensure_customer_key()
    conn = get_db()
    rows = conn.execute("""
        SELECT q.*, s.name AS service_name, s.current_estimated_duration,
               b.name AS business_name, b.city AS business_city
        FROM queue_tickets q
        JOIN services s ON q.service_id = s.id
        JOIN businesses b ON q.business_id = b.id
        WHERE q.customer_key = ?
        ORDER BY q.created_at DESC, q.id DESC LIMIT 25
    """, (key,)).fetchall()
    results = []
    for row in rows:
        item = ticket_display(row)
        if item["status"] in ("waiting", "in_service"):
            ahead = conn.execute("""
                SELECT COUNT(*) FROM queue_tickets
                WHERE business_id = ? AND status IN ('waiting','in_service')
                  AND (created_at < ? OR (created_at = ? AND id < ?))
            """, (item["business_id"], item["created_at"], item["created_at"], item["id"])).fetchone()[0]
            item["queue_position"] = max(1, ahead + 1)
            item["estimated_wait"] = calculate_dynamic_queue_wait(item["business_id"])["display"]
        else:
            item["queue_position"] = None
            item["estimated_wait"] = calculate_dynamic_queue_wait(item["business_id"])["display"]
        results.append(item)
    conn.close()
    return jsonify(results), 200


@app.put("/api/queue/<int:ticket_id>/decision")
@require_merchant
def decide_booking(ticket_id):
    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    if decision not in ("accept", "decline"):
        return jsonify({"error": "Decision must be accept or decline."}), 400
    conn = get_db()
    ticket = conn.execute("SELECT * FROM queue_tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        return jsonify({"error": "Booking request not found."}), 404
    if ticket["status"] != "pending_confirmation":
        conn.close()
        return jsonify({"error": "This booking request has already been handled."}), 409
    new_status = "waiting" if decision == "accept" else "declined"
    conn.execute("UPDATE queue_tickets SET status = ? WHERE id = ? AND status = 'pending_confirmation'", (new_status, ticket_id))
    if decision == "accept":
        refresh_business_count(conn, ticket["business_id"])
    conn.commit()
    conn.close()
    return jsonify({
        "message": "Booking accepted. The customer has been notified." if decision == "accept" else "Booking declined. The customer has been notified.",
        "ticket_id": ticket_id,
        "status": new_status,
    }), 200


@app.put("/api/queue/<int:ticket_id>/start")
@require_merchant
def seat_customer(ticket_id):
    conn = get_db()
    ticket = conn.execute("SELECT * FROM queue_tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        return jsonify({"error": "Ticket not found."}), 404
    now = now_string()
    cursor = conn.execute("UPDATE queue_tickets SET status = 'in_service', started_at = ? WHERE id = ? AND status = 'waiting'", (now, ticket_id))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "This customer is not waiting in the queue."}), 409
    refresh_business_count(conn, ticket["business_id"])
    conn.commit()
    conn.close()
    return jsonify({"message": f"{ticket['customer_name']} is now being served."}), 200


@app.put("/api/queue/<int:ticket_id>/complete")
@require_merchant
def complete_service(ticket_id):
    conn = get_db()
    ticket = conn.execute("SELECT * FROM queue_tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        return jsonify({"error": "Ticket not found."}), 404
    if ticket["status"] != "in_service":
        conn.close()
        return jsonify({"error": "Only a customer currently in service can be completed."}), 409
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        started = datetime.strptime(ticket["started_at"], "%Y-%m-%d %H:%M:%S") if ticket["started_at"] else None
        duration = max(0, (now - started).total_seconds() / 60.0) if started else 20.0
    except ValueError:
        duration = 20.0
    done_at = now.strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE queue_tickets SET status = 'completed', completed_at = ? WHERE id = ?", (done_at, ticket_id))
    refresh_business_count(conn, ticket["business_id"])
    conn.commit()
    conn.close()
    new_ema = update_service_ema(ticket["service_id"], duration)
    return jsonify({"message": "Service completed.", "duration": round(duration, 1), "new_ema": new_ema}), 200


@app.put("/api/businesses/<int:business_id>/status")
@require_merchant
def set_business_status(business_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("open", "busy", "closed"):
        return jsonify({"error": "Choose open, busy, or closed."}), 400
    conn = get_db()
    cursor = conn.execute("UPDATE businesses SET status = ? WHERE id = ?", (status, business_id))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Business not found."}), 404
    return jsonify({"message": f"Business status updated to {status}.", "status": status}), 200


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true", port=int(os.getenv("PORT", "5000")))
