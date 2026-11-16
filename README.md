# CityPulse

A Flask live queue and service-booking platform. Local development uses SQLite by default; set `DATABASE_URL` to use PostgreSQL (Neon) in production. Customers can discover local businesses, request appointments, and follow every booking from merchant confirmation to service completion. Merchants create an account with their business profile and manage only their own queue.

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create and activate a virtual environment:
   - Windows PowerShell: `py -m venv .venv` then `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install packages: `python -m pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and set a long, private `SESSION_SECRET`.
6. Run `python app.py` and open `http://127.0.0.1:5000`.

Existing SQLite databases are migrated on startup. New databases receive sample businesses for demonstration. When `DATABASE_URL` is set, CityPulse connects to PostgreSQL and creates the required tables automatically. For Render + Neon, set `DATABASE_URL` in the Render service Environment settings. Do not commit `.env` or include it in ZIP uploads. If `DATABASE_URL` is blank, the app continues to use local SQLite.

## Merchant accounts and business setup

Choose **Merchant** on the sign-in screen, select **Create an account**, and enter the merchant's name, email, password, business name, city, category, and comma-separated services. The account and business are created together. Each merchant account is linked to its own business, and server-side ownership checks prevent one merchant from managing another merchant's bookings.

Google accounts are permitted into the merchant workspace only when their email is listed in `MERCHANT_EMAILS`. A permitted Google merchant without a business profile is prompted to complete business setup after sign-in.

## Google Sign-In setup

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Configure the OAuth consent screen / Google Auth Platform branding and audience. For a public production service, complete Google's verification requirements applicable to your app and requested scopes. CityPulse uses basic sign-in identity only.
3. Open **Google Auth Platform → Clients** (or **APIs & Services → Credentials** in the older console) and create an **OAuth client ID** of type **Web application**.
4. Under **Authorized JavaScript origins**, add the exact origin of your Render deployment, for example `https://your-citypulse-service.onrender.com`. Also add `http://localhost:5000` and `http://127.0.0.1:5000` for local development. Do not add a path such as `/login`.
5. Copy the OAuth **Client ID** (the value ending in `.apps.googleusercontent.com`). The current Google Identity Services button flow does not require an authorized redirect URI.
6. In Render → your CityPulse web service → **Environment**, set `GOOGLE_CLIENT_ID` to that Client ID. Set `MERCHANT_EMAILS` to comma-separated merchant Google account emails if those accounts should use the merchant workspace.
7. Save changes and redeploy/restart the service. Refresh the login page. The disabled “Google sign-in needs setup” placeholder should be replaced by Google's sign-in button.
8. If it still fails, check that the browser's address bar origin exactly matches an Authorized JavaScript origin, the Client ID is copied correctly, the consent screen is configured, and the Render service has restarted with the new environment value.

Do not put a Google client secret in frontend code. CityPulse needs the Client ID only for this Google Identity Services ID-token flow; the server verifies the returned credential with Google's token verification endpoint and checks its audience.

## Booking lifecycle

- Customer booking creates a `pending_confirmation` request.
- Merchant sees the request, may add a message, and accepts or declines it.
- Accepting moves the booking to `waiting`; the customer sees the merchant response and queue position.
- When the merchant selects **Seat Next**, the booking becomes `in_service`.
- When the merchant selects **Complete Service**, it becomes `completed`.
- The customer dashboard's bottom **Your bookings & service status** section polls every five seconds and retains the booking card with its final completed status.

## Render environment variables

Set these in Render → Environment:

- `SESSION_SECRET`: a long random secret; never use the development default.
- `GOOGLE_CLIENT_ID`: Google OAuth Web Client ID.
- `MERCHANT_EMAILS`: optional comma-separated Google merchant allowlist.
- `ENABLE_DEMO_LOGIN=false`: disable demo access in public production.
- `COOKIE_SECURE=true`: enable secure session cookies over HTTPS.
- `DATABASE_URL`: Neon PostgreSQL connection string (required for persistent production database). Keep it private.
- `CITYPULSE_DB_PATH`: optional local SQLite path when `DATABASE_URL` is not set.

## Production notes

This is a working prototype, not yet a hardened high-scale production system. Before a public commercial launch, add CSRF protection, rate limiting, stronger operational monitoring, and automated database backups. PostgreSQL support is included, but the deployment should be tested end-to-end before public launch. Keep `.env`, secrets, and database backups out of source control.
