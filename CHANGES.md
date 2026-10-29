
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
