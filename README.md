# CityPulse

A Flask + SQLite live queue and service-booking prototype. Customer bookings begin in `pending_confirmation`; the merchant accepts or declines each request; accepted customers enter the queue. Customer and merchant views synchronize in the background without full-page reloads.

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create and activate a virtual environment:
   - Windows PowerShell: `py -m venv .venv` then `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install packages: `python -m pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and set a private `SESSION_SECRET`.
6. Run `python app.py` and open `http://127.0.0.1:5000`.

The updated source bundle intentionally omits the submitted `citypulse.db` because it contained old queue/test entries. On startup, the app creates a fresh database with Urban Cut Studio, Apex Dental Clinic, Metro Auto Workshop, and sample services. If you copy your own existing `citypulse.db` into the project folder, it is migrated automatically and its records are preserved.

## Google sign-in

1. In Google Cloud Console, create an OAuth 2.0 **Web application** client ID.
2. Add `http://127.0.0.1:5000` and `http://localhost:5000` to **Authorized JavaScript origins** for local development. Add your deployed HTTPS origin before launch.
3. Put the client ID in `.env` as `GOOGLE_CLIENT_ID=...`.
4. Add the Google account(s) authorized to manage the prototype business to `MERCHANT_EMAILS`, separated by commas.
5. Restart Flask. Google sign-in becomes available on the first screen. A Google account not on the allowlist remains a customer account.

CityPulse sends the Google ID credential to the backend, where the token is verified with Google's HTTPS tokeninfo endpoint and the audience is checked against `GOOGLE_CLIENT_ID`. The remember-me checkbox controls Flask's persistent session cookie (up to 30 days when checked).

## Live booking behaviour

- A customer sends a request; the ticket is stored as `pending_confirmation` and does not yet consume a queue position.
- The merchant console polls the queue every 2.5 seconds, displays pending requests, and may also show browser desktop notifications after the merchant grants notification permission.
- Accept changes the ticket to `waiting` and adds it to the customer queue. Decline changes the ticket to `declined`.
- The customer booking panel polls every 2.5 seconds and updates the status without a page reload.
- Merchant walk-in names are optional. Use the `#n` control or leave the name blank to identify the walk-in by the next queue number.
- The app uses a custom responsive CityPulse interface and includes its SVG logo locally. Bootstrap is used for standard layout utilities and modal behaviour.

## Important prototype limitations before public launch

- Demo login is enabled by default so the app can be tried without credentials. Set `ENABLE_DEMO_LOGIN=false` before public launch. Google accounts must be explicitly listed in `MERCHANT_EMAILS` before they can enter the merchant console. The current allowlist is not a full multi-tenant ownership model: every allowlisted merchant can manage every listed business. Bind each merchant account to its own business before exposing the site publicly.
- Pending bookings are shown in the merchant queue with Accept and Decline actions. The current implementation does not send push notifications when the browser is closed; that needs a push provider, service worker, and push-subscription storage.
- SQLite is suitable for local/demo traffic. For a multi-merchant production deployment, use a managed database and deploy with HTTPS, a strong `SESSION_SECRET`, rate limiting, CSRF protections, and access controls.

## Deployment variables

Set `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `MERCHANT_EMAILS`, `ENABLE_DEMO_LOGIN=false`, and `COOKIE_SECURE=true` in the hosting provider's secret/environment settings. Keep `.env`, virtual environments, and local database backups out of source control.
