// File: static/js/api.js
// Purpose: Dynamic Merchant Console Controller & Asynchronous Network Bridge

const CURRENT_BUSINESS_ID = 1; // Default business ID for testing

// --- 1. Network Communication Functions ---

// Fetch the current queue and active customer from Flask
async function fetchQueueState(businessId) {
    try {
        const response = await fetch(`/api/businesses/${businessId}/queue`);
        if (!response.ok) throw new Error("Network response failed");
        return await response.json();
    } catch (err) {
        console.error("Failed to load queue data:", err);
        return null;
    }
}

// Send an in-person walk-in customer to Flask
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
        console.error("Walk-in request failed:", err);
    }
}

// Seat the next customer in line
async function requestSeatNext(ticketId) {
    try {
        const response = await fetch(`/api/queue/${ticketId}/start`, { method: "PUT" });
        return await response.json();
    } catch (err) {
        console.error("Seat customer failed:", err);
    }
}

// Mark the service finished (triggers the EMA calibration calculation)
async function requestCompleteService(ticketId) {
    try {
        const response = await fetch(`/api/queue/${ticketId}/complete`, { method: "PUT" });
        return await response.json();
    } catch (err) {
        console.error("Complete service failed:", err);
    }
}

// --- 2. Dynamic Screen Rendering ---

async function refreshMerchantConsole() {
    const data = await fetchQueueState(CURRENT_BUSINESS_ID);
    if (!data) return;

    // A. Update the "Active in Chair" Card
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

    // B. Update the Upcoming Queue List
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

    // C. Update Dynamic Wait Interval Badge
    const waitBadge = document.getElementById("dynamicWaitBadge");
    if (waitBadge && data.wait_stats) {
        waitBadge.innerText = data.wait_stats.display;
    }
}

// --- 3. Click Handlers and Form Listeners ---

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

// Wire up the Add Walk-In modal submission
document.addEventListener("DOMContentLoaded", () => {
    const walkInForm = document.getElementById("walkInForm");
    if (walkInForm) {
        walkInForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = document.getElementById("walkInCustomerName").value.trim();
            const serviceId = document.getElementById("walkInServiceSelect").value;

            await requestAddWalkIn(CURRENT_BUSINESS_ID, serviceId, name);

            // Close modal if Bootstrap modal is present
            const modalEl = document.getElementById("addWalkInModal");
            if (modalEl && typeof bootstrap !== "undefined") {
                const modalInstance = bootstrap.Modal.getInstance(modalEl);
                if (modalInstance) modalInstance.hide();
            }
            walkInForm.reset();

            await refreshMerchantConsole();
        });
    }

    // Initial render and poll every 10 seconds for live updates
    refreshMerchantConsole();
    setInterval(refreshMerchantConsole, 10000);
});