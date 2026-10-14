/*
=============================================================================
FILE: static/js/api.js
TIER: Client-Side Controller & Asynchronous Network Bridge
-----------------------------------------------------------------------------
PURPOSE:
Acts as the intermediary between browser Document Object Model (DOM) events
and Flask REST API routes. Enables single-page application (SPA) functionality
by sending background network requests using the Fetch API without full page reloads.

KEY OPERATIONS:
1. Polling: Continuously synchronizes merchant view every 10 seconds.
2. State Transition: Dispatches PUT requests when seating or completing patrons.
3. DOM Mutation: Updates the 'Active in Chair' card, waiting list, and wait badges.
=============================================================================
*/

// Configuration: Default establishment identifier for testing
const CURRENT_BUSINESS_ID = 1;

// -----------------------------------------------------------------------------
// 1. Asynchronous Network Helpers (HTTP Dispatchers)
// -----------------------------------------------------------------------------

/**
 * Retrieves the current queue state, active patron, and wait metrics from Flask.
 */
async function fetchQueueState(businessId) {
    try {
        const response = await fetch(`/api/businesses/${businessId}/queue`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (err) {
        console.error("[CityPulse Network Error] Failed to fetch queue state:", err);
        return null;
    }
}

/**
 * Dispatches an asynchronous POST request to enroll an in-person walk-in customer.
 */
async function requestAddWalkIn(businessId, serviceId, customerName) {
    try {
        const response = await fetch("/api/walkin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                business_id: businessId,
                service_id: serviceId,
                customer_name: customerName
            })
        });
        return await response.json();
    } catch (err) {
        console.error("[CityPulse Network Error] Failed to register walk-in:", err);
    }
}

/**
 * Dispatches an asynchronous PUT request to seat the next patron in the active chair.
 */
async function requestSeatNext(ticketId) {
    try {
        const response = await fetch(`/api/queue/${ticketId}/start`, { method: "PUT" });
        return await response.json();
    } catch (err) {
        console.error("[CityPulse Network Error] Failed to seat patron:", err);
    }
}

/**
 * Dispatches an asynchronous PUT request to mark a service complete and trigger EMA.
 */
async function requestCompleteService(ticketId) {
    try {
        const response = await fetch(`/api/queue/${ticketId}/complete`, { method: "PUT" });
        return await response.json();
    } catch (err) {
        console.error("[CityPulse Network Error] Failed to complete service:", err);
    }
}

// -----------------------------------------------------------------------------
// 2. Dynamic DOM Rendering (Screen Mutation)
// -----------------------------------------------------------------------------

/**
 * Renders the live state of the queue directly into HTML elements without page refresh.
 */
async function refreshMerchantConsole() {
    const data = await fetchQueueState(CURRENT_BUSINESS_ID);
    if (!data) return;

    // --- Sub-View A: Active Patron in Chair ---
    const chairContainer = document.getElementById("activeChairContainer");
    if (chairContainer) {
        if (data.active_patron) {
            const patron = data.active_patron;
            chairContainer.innerHTML = `
                <div class="card bg-primary text-white p-3 shadow-sm border-0 mb-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="badge bg-light text-primary fw-bold">ACTIVE IN CHAIR</span>
                        <span class="badge bg-warning text-dark">In Progress</span>
                    </div>
                    <h3 class="mt-2 mb-0 fw-bold">${patron.customer_name}</h3>
                    <p class="mb-2 text-white-50">${patron.service_name} • Est: ${patron.current_estimated_duration} mins</p>
                    <button class="btn btn-light btn-sm fw-bold w-100 mt-2" onclick="handleCompleteServiceClick(${patron.id})">
                        ✓ Complete Service
                    </button>
                </div>`;
        } else {
            chairContainer.innerHTML = `
                <div class="card bg-light p-4 text-center border-dashed mb-3">
                    <h5 class="text-muted mb-1">Chair is Currently Vacant</h5>
                    <small class="text-secondary">Click "Seat Next" on the upcoming list below.</small>
                </div>`;
        }
    }

    // --- Sub-View B: Upcoming Queue Patron List ---
    const queueList = document.getElementById("merchantQueueList");
    if (queueList) {
        queueList.innerHTML = "";
        if (data.waiting_list.length === 0) {
            queueList.innerHTML = `<li class="list-group-item text-center text-muted py-3">No patrons currently waiting.</li>`;
        } else {
            data.waiting_list.forEach((ticket, idx) => {
                const badge = ticket.is_walkin 
                    ? `<span class="badge bg-secondary ms-2">Walk-In</span>` 
                    : `<span class="badge bg-info text-dark ms-2">App User</span>`;

                // Only the person at the head of the line (#1) can be seated, and only if chair is vacant
                const canSeat = idx === 0 && !data.active_patron;
                const seatButton = canSeat 
                    ? `<button class="btn btn-sm btn-success ms-auto" onclick="handleSeatNextClick(${ticket.id})">Seat Next</button>` 
                    : "";

                const item = document.createElement("li");
                item.className = "list-group-item d-flex justify-content-between align-items-center";
                item.innerHTML = `
                    <div>
                        <strong>#${idx + 1} ${ticket.customer_name}</strong> ${badge}
                        <div class="small text-muted">${ticket.service_name} (~${ticket.current_estimated_duration} mins)</div>
                    </div>
                    <div>${seatButton}</div>`;
                queueList.appendChild(item);
            });
        }
    }

    // --- Sub-View C: Real-Time Dynamic Wait Interval Badge ---
    const waitBadge = document.getElementById("dynamicWaitBadge");
    if (waitBadge && data.wait_stats) {
        waitBadge.innerText = data.wait_stats.display;
    }
}

// -----------------------------------------------------------------------------
// 3. User Interaction Event Handlers
// -----------------------------------------------------------------------------

window.handleSeatNextClick = async function(ticketId) {
    await requestSeatNext(ticketId);
    await refreshMerchantConsole();
};

window.handleCompleteServiceClick = async function(ticketId) {
    const result = await requestCompleteService(ticketId);
    if (result && result.actual_duration_minutes) {
        alert(`Service finished in ${result.actual_duration_minutes} mins! Calibrated EMA: ${result.calibrated_ema}m`);
    }
    await refreshMerchantConsole();
};

// -----------------------------------------------------------------------------
// 4. Initialization & Polling Cycle
// -----------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    const walkInForm = document.getElementById("walkInForm");
    if (walkInForm) {
        walkInForm.addEventListener("submit", async (e) => {
            e.preventDefault(); // Stop default browser full-page form submission
            const name = document.getElementById("walkInCustomerName").value.trim();
            const serviceId = document.getElementById("walkInServiceSelect").value;

            await requestAddWalkIn(CURRENT_BUSINESS_ID, serviceId, name);

            walkInForm.reset();
            await refreshMerchantConsole();
        });
    }

    // Initial load on page startup
    refreshMerchantConsole();

    // Poll the Flask backend every 10,000 milliseconds (10 seconds)
    setInterval(refreshMerchantConsole, 10000);
});