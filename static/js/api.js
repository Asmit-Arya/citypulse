
/* CityPulse queue API bridge. Existing Flask endpoints are preserved. */
let CURRENT_BUSINESS_ID = null;
let CURRENT_BUSINESS_OWNER = null;

async function loadMerchantBusiness() {
    const owner = String(window.cityPulseCurrentUser?.id || "");
    const response = await fetch("/api/my-business", { headers: { "Accept": "application/json" } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Could not load your business.");
    CURRENT_BUSINESS_OWNER = owner;
    if (!data.business) {
        CURRENT_BUSINESS_ID = null;
        const panel = document.getElementById("merchantOnboardingPanel");
        if (panel) panel.hidden = false;
        return null;
    }
    CURRENT_BUSINESS_ID = Number(data.business.id);
    const panel = document.getElementById("merchantOnboardingPanel");
    if (panel) panel.hidden = true;
    const heading = document.getElementById("merchantBusinessHeading");
    if (heading) heading.textContent = data.business.name;
    const serviceSelect = document.getElementById("walkInServiceSelect");
    if (serviceSelect) {
        serviceSelect.innerHTML = data.services.map(service => `<option value="${Number(service.id)}">${escapeQueueText(service.name)} (~${Number(service.current_estimated_duration) || 15}m)</option>`).join("");
    }
    return data.business;
}

async function refreshCustomerBookings() {
    if (window.cityPulseRole !== "customer") return;
    const container = document.getElementById("customerBookingsList");
    if (!container) return;
    try {
        const response = await fetch("/api/my-bookings", { headers: { "Accept": "application/json" } });
        const bookings = await response.json().catch(() => []);
        if (!response.ok) throw new Error("Could not load bookings.");
        if (!bookings.length) {
            container.innerHTML = '<div class="empty-state">No bookings yet. Choose a local business above to get started.</div>';
            return;
        }
        const steps = ["pending_confirmation", "waiting", "in_service", "completed"];
        const labels = ["Request sent", "Merchant confirmed", "Service in progress", "Completed"];
        container.innerHTML = bookings.map(ticket => {
            const index = steps.indexOf(ticket.status);
            const declined = ticket.status === "declined";
            const activeIndex = declined ? 0 : Math.max(0,index);
            const progress = labels.map((label,i) => `<div class="booking-step ${!declined && i <= activeIndex ? "done" : ""}">${label}</div>`).join("");
            const responseNote = ticket.merchant_response ? `<div class="booking-response"><strong>Merchant response:</strong> ${escapeQueueText(ticket.merchant_response)}</div>` : (ticket.status === "waiting" ? '<div class="booking-response">The merchant accepted your request. You are in the queue.</div>' : "");
            return `<article class="booking-status-card ${declined ? "booking-declined" : ""}">
              <div class="booking-status-top"><div><div class="booking-status-title">${escapeQueueText(ticket.business_name)} · ${escapeQueueText(ticket.service_name)}</div><div class="booking-status-meta">Booking #${Number(ticket.id)} · ${escapeQueueText(ticket.business_city || "")} · ${escapeQueueText(ticket.created_at || "")}</div></div><span class="badge ${declined ? "badge-status-closed" : ticket.status === "completed" ? "badge-status-open" : "badge-status-busy"}">${escapeQueueText(ticket.status_label || ticket.status)}</span></div>
              ${declined ? '<div class="booking-response">This request was declined by the merchant. You can choose another time or business.</div>' : `<div class="booking-progress">${progress}</div>`}
              ${responseNote}
              ${ticket.queue_position ? `<div class="booking-status-meta mt-2">Queue position: <strong>#${Number(ticket.queue_position)}</strong> · Estimated wait: ${escapeQueueText(ticket.estimated_wait || "Updating")}</div>` : ""}
            </article>`;
        }).join("");
    } catch (error) { console.warn("Booking status refresh failed", error); }
}
window.refreshCustomerBookings = refreshCustomerBookings;

async function fetchQueueState(businessId) {
    try {
        const response = await fetch(
            `/api/businesses/${businessId}/queue`,
            { headers: { "Accept": "application/json" } }
        );

        if (!response.ok) {
            throw new Error(`Queue request returned ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error("[CityPulse] Could not load queue:", error);
        return null;
    }
}

async function requestAddWalkIn(businessId, serviceId, customerName, useQueueNumber = false) {
    try {
        const response = await fetch("/api/walkin", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify({
                business_id: businessId,
                service_id: serviceId,
                customer_name: useQueueNumber ? "" : customerName,
                use_queue_number: Boolean(useQueueNumber)
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Could not add walk-in customer.");
        }

        return result;
    } catch (error) {
        console.error("[CityPulse] Could not add walk-in:", error);
        if (typeof window.toast === "function") window.toast(error.message);
        return null;
    }
}

async function requestSeatNext(ticketId) {
    const response = await fetch(
        `/api/queue/${ticketId}/start`,
        { method: "PUT" }
    );

    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "Could not start service.");
    }

    return result;
}

async function requestCompleteService(ticketId) {
    const response = await fetch(
        `/api/queue/${ticketId}/complete`,
        { method: "PUT" }
    );

    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "Could not complete service.");
    }

    return result;
}

function escapeQueueText(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[ch]);
}

async function refreshMerchantConsole() {
    // Avoid merchant requests while the customer workspace is active.
    if (window.cityPulseRole !== "merchant") return;

    const signedInOwner = String(window.cityPulseCurrentUser?.id || "");
    if (!CURRENT_BUSINESS_ID || CURRENT_BUSINESS_OWNER !== signedInOwner) {
        try { await loadMerchantBusiness(); } catch (error) { console.error(error); }
        if (!CURRENT_BUSINESS_ID) return;
    }
    const data = await fetchQueueState(CURRENT_BUSINESS_ID);
    if (!data) return;

    const waiting = Array.isArray(data.waiting_list)
        ? data.waiting_list
        : [];

    const active = data.active_patron || null;

    const queueCount = document.getElementById("merchantQueueCount");
    const activeName = document.getElementById("merchantActiveName");
    const waitStat = document.getElementById("merchantWaitStat");

    if (queueCount) queueCount.textContent = String(waiting.length);

    if (activeName) {
        activeName.textContent = active
            ? (active.customer_name === "__QUEUE_NUMBER__"
                ? "Queue-number customer"
                : active.customer_name)
            : "No active service";
    }

    if (waitStat) {
        waitStat.textContent =
            data.wait_stats?.display ||
            `${waiting.length ? waiting.length * 15 : 0} min`;
    }

    // Current customer being served.
    const chairContainer = document.getElementById("activeChairContainer");

    if (chairContainer) {
        if (active) {
            const patronName =
                active.customer_name === "__QUEUE_NUMBER__"
                    ? "Queue-number customer"
                    : escapeQueueText(active.customer_name || "Walk-in Guest");

            chairContainer.innerHTML = `
              <div class="active-service-card">
                <div class="d-flex justify-content-between align-items-center gap-2">
                  <span class="badge badge-status-open">ACTIVE IN SERVICE</span>
                  <span class="live-indicator"><i></i> In progress</span>
                </div>
                <h3 class="mt-3 mb-1">${patronName}</h3>
                <p class="business-card-meta mb-3">
                  ${escapeQueueText(active.service_name || "Service")}
                  · Est. ${Number(active.current_estimated_duration) || 20} mins
                </p>
                <button class="btn btn-gradient w-100"
                  onclick="handleCompleteServiceClick(${Number(active.id)})">
                  ✓ Complete Service
                </button>
              </div>`;
        } else {
            chairContainer.innerHTML =
                '<div class="empty-state">No active service. Seat the next customer when you are ready.</div>';
        }
    }

    // Pending online requests appear before the active queue so the merchant can decide.
    const queueList = document.getElementById("merchantQueueList");
    const pending = Array.isArray(data.pending_bookings) ? data.pending_bookings : [];

    if (queueList) {
        const responseDrafts = new Map();
        queueList.querySelectorAll("[data-merchant-response]").forEach(field => responseDrafts.set(field.dataset.merchantResponse, field.value));
        queueList.innerHTML = "";

        if (pending.length) {
            const heading = document.createElement("div");
            heading.className = "pending-heading";
            heading.textContent = `Requests awaiting confirmation (${pending.length})`;
            queueList.appendChild(heading);

            pending.forEach((ticket) => {
                const item = document.createElement("div");
                item.className = "queue-ticket pending-ticket";
                item.innerHTML = `
                  <div class="queue-ticket-copy">
                    <strong>${escapeQueueText(ticket.customer_name || "Customer")}</strong>
                    <div class="small mt-1">${escapeQueueText(ticket.service_name || "Service")}</div>
                    <div class="small mt-1">New booking · awaiting your decision</div>
                    <input class="form-control cp-input mt-2" data-merchant-response="${Number(ticket.id)}" placeholder="Optional response to customer" maxlength="500" aria-label="Response to customer">
                  </div>
                  <div class="queue-ticket-actions">
                    <button type="button" class="btn btn-sm btn-success" data-decision="accept" data-ticket-id="${Number(ticket.id)}">Accept</button>
                    <button type="button" class="btn btn-sm btn-outline-danger" data-decision="decline" data-ticket-id="${Number(ticket.id)}">Decline</button>
                  </div>`;
                queueList.appendChild(item);
                const responseField = item.querySelector("[data-merchant-response]");
                if (responseField && responseDrafts.has(String(ticket.id))) responseField.value = responseDrafts.get(String(ticket.id));
            });
        }

        const waitingHeading = document.createElement("div");
        waitingHeading.className = "pending-heading waiting-heading";
        waitingHeading.textContent = `Waiting queue (${waiting.length})`;
        queueList.appendChild(waitingHeading);

        if (!waiting.length) {
            const empty = document.createElement("div");
            empty.className = "empty-state";
            empty.textContent = "No customers are waiting right now.";
            queueList.appendChild(empty);
        } else {
            waiting.forEach((ticket, index) => {
                const name = escapeQueueText(ticket.customer_name || "Walk-in Guest");
                const position = index + 1;
                const kind = ticket.is_walkin ? "Walk-in" : "Online booking";
                const item = document.createElement("div");
                item.className = "queue-ticket";
                item.innerHTML = `
                  <div class="queue-ticket-copy">
                    <strong>#${position} · ${name}</strong>
                    <div class="small mt-1">${escapeQueueText(ticket.service_name || "Service")} · ${Number(ticket.current_estimated_duration) || 20} min</div>
                    <div class="small mt-1">${kind}</div>
                  </div>
                  <div class="queue-ticket-actions">
                    ${index === 0 && !active ? `<button type="button" class="btn btn-sm btn-success" data-seat-ticket="${Number(ticket.id)}">Seat Next</button>` : ""}
                  </div>`;
                queueList.appendChild(item);
            });
        }

        // Use delegated listeners on the newly rendered buttons.
        queueList.querySelectorAll("[data-decision]").forEach((button) => {
            button.addEventListener("click", () => {
                const responseField = queueList.querySelector(`[data-merchant-response="${button.dataset.ticketId}"]`);
                decideBooking(Number(button.dataset.ticketId), button.dataset.decision, button, responseField?.value || "");
            });
        });
        queueList.querySelectorAll("[data-seat-ticket]").forEach((button) => {
            button.addEventListener("click", () => window.handleSeatNextClick(Number(button.dataset.seatTicket)));
        });
    }

    async function decideBooking(ticketId, decision, button, merchantResponse = "") {
        button.disabled = true;
        try {
            const response = await fetch(`/api/queue/${ticketId}/decision`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", "Accept": "application/json" },
                body: JSON.stringify({ decision, merchant_response: merchantResponse })
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.error || "Could not update booking.");
            if (typeof window.toast === "function") window.toast(result.message || `Booking ${decision}ed.`);
            await refreshMerchantConsole();
        } catch (error) {
            if (typeof window.toast === "function") window.toast(error.message);
        } finally {
            button.disabled = false;
        }
    }

    const waitBadge = document.getElementById("dynamicWaitBadge");

    if (waitBadge && data.wait_stats?.display) {
        waitBadge.textContent = data.wait_stats.display;
    }
}

window.refreshMerchantConsole = refreshMerchantConsole;
window.resetMerchantBusinessContext = function() { CURRENT_BUSINESS_ID = null; CURRENT_BUSINESS_OWNER = null; };

window.handleSeatNextClick = async function(ticketId) {
    try {
        await requestSeatNext(ticketId);
        await refreshMerchantConsole();
    } catch (error) {
        console.error(error);
        alert(error.message || "Could not start service.");
    }
};

window.handleCompleteServiceClick = async function(ticketId) {
    try {
        const result = await requestCompleteService(ticketId);

        if (result && (result.duration || result.actual_duration_minutes)) {
            const duration = result.duration ?? result.actual_duration_minutes;
            alert(`Service completed in ${duration} minutes.`);
        }

        await refreshMerchantConsole();
    } catch (error) {
        console.error(error);
        alert(error.message || "Could not complete service.");
    }
};

// Background queue refresh; no full-page reload.
document.addEventListener("DOMContentLoaded", () => {
    const onboardingForm = document.getElementById("merchantOnboardingForm");
    onboardingForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorEl = document.getElementById("merchantOnboardingError");
        errorEl.hidden = true;
        const services = document.getElementById("onboardServices").value.split(",").map(value => value.trim()).filter(Boolean);
        try {
            const response = await fetch("/api/my-business", { method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: JSON.stringify({ name: document.getElementById("onboardBusinessName").value, city: document.getElementById("onboardCity").value, category: document.getElementById("onboardCategory").value, services }) });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.error || "Could not save business.");
            onboardingForm.reset(); CURRENT_BUSINESS_ID = null; await loadMerchantBusiness(); await refreshMerchantConsole();
            if (typeof window.toast === "function") window.toast(result.message || "Business profile saved.");
        } catch (error) { errorEl.textContent = error.message; errorEl.hidden = false; }
    });

    const walkInForm = document.getElementById("walkInForm");

    if (walkInForm) {
        walkInForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const nameField =
                document.getElementById("walkInCustomerName");

            const useNumber =
                document.getElementById("walkInUseNumber")?.checked;

            const enteredName = (nameField?.value || "").trim();

            const customerName = enteredName;

            const serviceId =
                document.getElementById("walkInServiceSelect")?.value || "1";

            const result = await requestAddWalkIn(
                CURRENT_BUSINESS_ID,
                serviceId,
                customerName,
                Boolean(useNumber || !enteredName)
            );

            if (result) {
                walkInForm.reset();

                if (nameField) nameField.disabled = false;

                const numberBtn =
                    document.getElementById("walkInNumberBtn");

                if (numberBtn) {
                    numberBtn.textContent = "Use #n";
                    numberBtn.setAttribute("aria-pressed", "false");
                }

                if (typeof window.toast === "function") {
                    window.toast(result.message || "Customer added to queue.");
                }

                await refreshMerchantConsole();
            }
        });
    }

    refreshCustomerBookings();
    window.setInterval(() => {
        if (window.cityPulseRole === "merchant") refreshMerchantConsole();
        if (window.cityPulseRole === "customer") refreshCustomerBookings();
    }, 5000);
});
