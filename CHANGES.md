
## Requested follow-up implementation (2026-10-29)
- Centered the Get Started CTA and tagline on mobile.
- Added city to customer registration, merchant registration, and demo sign-in; city is retained in account data and remembered in the browser for subsequent sessions.
- Added merchant onboarding with business name, city, category, and services; it creates the merchant's business card and service records.
- Merchant dashboard now loads the business owned by the signed-in merchant instead of always assuming business ID 1.
- Added server-side ownership checks so merchants cannot see or manage another business's queue or bookings.
- Booking notes are included in merchant pending requests.
- Queue-number walk-ins use a sentinel so the UI displays a single queue number rather than `#n · #n`.
- Removed Profile and Settings from the user dropdown, leaving Sign Out.
- Customer booking service options are loaded from the selected business's service list.

## Product upgrade (2026-11-14)
- Added merchant registration that creates a password-authenticated merchant account and its business profile/services in one transaction.
- Added a merchant onboarding path for allowlisted Google merchant accounts without a registered business.
- Added business ownership to the schema and enforced ownership on merchant queue, booking decisions, service lifecycle, walk-ins, and business status updates.
- Replaced the hardcoded merchant Business ID 1 with the signed-in merchant's owned business and dynamically loaded its services.
- Added customer booking status cards at the bottom of the customer workspace, including request, confirmation, in-service, completed/declined states, merchant messages, and live polling.
- Made authenticated customer booking identity stable across sign-in sessions.
- Added a layered midnight-blue / violet workspace background consistent with the landing and authentication screens.
- Expanded Google Identity Services and Render setup documentation.


## Frontend feature repairs (latest package)
- Added a visible **My Booking Status** panel to the customer workspace, with a manual refresh control and the existing five-second background refresh.
- Added the merchant business details required by the existing `/api/auth/register` endpoint to the merchant account creation modal (business name, city, category, and comma-separated services).
- Added the merchant business onboarding panel used by the existing `/api/my-business` endpoint for merchant accounts without a business profile.
- Added the merchant business heading target used by the merchant console.
- Triggered booking-status refresh when a customer workspace is opened.
- Kept the existing Flask routes, database compatibility layer, styling, customer flows, and merchant queue workflows.

## Validation performed for this package
- Python syntax compilation passed for `app.py`, `db.py`, `init_db.py`, `calibration.py`, and `ai_service.py`.
- JavaScript syntax checks passed for `static/js/ui.js`, `static/js/api.js`, and `static/js/customer-city.js`.
- HTML structure/required-element checks and ZIP integrity checks are performed before packaging.
- A live Flask/API integration test could not be run in the build environment because project dependencies are not installed and package-network access is unavailable. Run the local test checklist in `POSTGRES_SETUP.txt` after installing requirements.
