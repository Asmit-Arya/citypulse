
/* CityPulse queue API bridge. Existing Flask endpoints are preserved. */
const CURRENT_BUSINESS_ID = 1;

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
                  </div>
                  <div class="queue-ticket-actions">
                    <button type="button" class="btn btn-sm btn-success" data-decision="accept" data-ticket-id="${Number(ticket.id)}">Accept</button>
                    <button type="button" class="btn btn-sm btn-outline-danger" data-decision="decline" data-ticket-id="${Number(ticket.id)}">Decline</button>
                  </div>`;
                queueList.appendChild(item);
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
            button.addEventListener("click", () => decideBooking(
                Number(button.dataset.ticketId), button.dataset.decision, button
            ));
        });
        queueList.querySelectorAll("[data-seat-ticket]").forEach((button) => {
            button.addEventListener("click", () => window.handleSeatNextClick(Number(button.dataset.seatTicket)));
        });
    }

    async function decideBooking(ticketId, decision, button) {
        button.disabled = true;
        try {
            const response = await fetch(`/api/queue/${ticketId}/decision`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", "Accept": "application/json" },
                body: JSON.stringify({ decision })
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

    window.setInterval(() => {
        if (window.cityPulseRole === "merchant") {
            refreshMerchantConsole();
        }
    }, 10000);
});
