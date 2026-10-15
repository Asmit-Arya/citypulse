/*
=============================================================================
FILE: static/js/ui.js
ROLE: Client-Side UI Controller & View State Manager (Teammate 1)
-----------------------------------------------------------------------------
PURPOSE:
Manages DOM view transitions (Customer View <-> Merchant Console),
instant search filtering across business cards, and modal dialog helpers.
=============================================================================
*/

let allLoadedBusinesses = [];

// 1. Toggle between Customer Discovery View and Merchant Console
function switchView(viewName) {
    const customerView = document.getElementById("viewCustomer");
    const merchantView = document.getElementById("viewMerchant");
    const btnCustomer = document.getElementById("btnViewCustomer");
    const btnMerchant = document.getElementById("btnViewMerchant");

    if (viewName === "customer") {
        customerView.classList.remove("d-none");
        merchantView.classList.add("d-none");
        btnCustomer.classList.add("active");
        btnMerchant.classList.remove("active");
    } else {
        merchantView.classList.remove("d-none");
        customerView.classList.add("d-none");
        btnMerchant.classList.add("active");
        btnCustomer.classList.remove("active");
    }
}

// 2. Render businesses as dark glassmorphic cards
function renderCustomerCards(businesses) {
    const container = document.getElementById("businessCardsGrid");
    if (!container) return;
    container.innerHTML = "";

    if (!businesses || businesses.length === 0) {
        container.innerHTML = `
            <div class="col-12 text-center py-5">
                <p class="text-muted mb-0">No operating businesses match your selected criteria.</p>
            </div>`;
        return;
    }

    businesses.forEach(b => {
        let badgeClass = "badge-status-open";
        if (b.status === "busy") badgeClass = "badge-status-busy";
        if (b.status === "closed") badgeClass = "badge-status-closed";

        const baseWait = (b.current_queue || 0) * 15;
        const waitWindow = baseWait === 0 ? "0–5 mins" : `${baseWait - 5}–${baseWait + 10} mins`;

        const col = document.createElement("div");
        col.className = "col-md-4";
        col.innerHTML = `
            <div class="cp-card p-3 h-100 d-flex flex-column justify-content-between">
                <div>
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h5 class="fw-bold mb-0 text-white">${b.name}</h5>
                        <span class="badge ${badgeClass} text-uppercase px-2 py-1 small">${b.status}</span>
                    </div>
                    <p class="text-muted small mb-3">${b.category} • ${b.city}</p>
                    
                    <div class="d-flex justify-content-between small text-secondary mb-1">
                        <span>Current Line:</span>
                        <strong class="text-white">${b.current_queue || 0} patrons</strong>
                    </div>
                    <div class="d-flex justify-content-between small text-secondary mb-3">
                        <span>Projected Wait:</span>
                        <strong class="text-white">${waitWindow}</strong>
                    </div>
                </div>

                <button class="btn btn-cp-outline w-100 btn-sm" onclick="openCustomerBookingModal(${b.id}, '${b.name}')">
                    Join Virtual Queue
                </button>
            </div>`;
        container.appendChild(col);
    });
}

// 3. Open the booking modal and assign business ID
function openCustomerBookingModal(businessId, businessName) {
    document.getElementById("modalBusinessId").value = businessId;
    document.getElementById("customerBookingModalTitle").innerText = `Join Queue: ${businessName}`;
    const modalEl = document.getElementById("customerBookingModal");
    new bootstrap.Modal(modalEl).show();
}

// 4. Instant search and dropdown filters
function handleFilterChange() {
    const query = document.getElementById("searchInput").value.toLowerCase();
    const city = document.getElementById("cityFilter").value;
    const category = document.getElementById("categoryFilter").value;

    const filtered = allLoadedBusinesses.filter(b => {
        const matchesName = b.name.toLowerCase().includes(query);
        const matchesCity = !city || b.city === city;
        const matchesCategory = !category || b.category === category;
        return matchesName && matchesCity && matchesCategory;
    });

    renderCustomerCards(filtered);
}

// 5. Initial Load & Form Submissions
document.addEventListener("DOMContentLoaded", async () => {
    const searchInput = document.getElementById("searchInput");
    const cityFilter = document.getElementById("cityFilter");
    const categoryFilter = document.getElementById("categoryFilter");

    if (searchInput) searchInput.addEventListener("input", handleFilterChange);
    if (cityFilter) cityFilter.addEventListener("change", handleFilterChange);
    if (categoryFilter) categoryFilter.addEventListener("change", handleFilterChange);

    // Initial business data fetch
    try {
        const response = await fetch("/api/businesses");
        if (response.ok) {
            allLoadedBusinesses = await response.json();
            renderCustomerCards(allLoadedBusinesses);
        }
    } catch (err) {
        console.error("Could not fetch discovery businesses:", err);
    }

    // Handle online queue booking submission
    const bookingForm = document.getElementById("onlineBookingForm");
    if (bookingForm) {
        bookingForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const payload = {
                business_id: document.getElementById("modalBusinessId").value,
                service_id: document.getElementById("onlineServiceSelect").value,
                customer_name: document.getElementById("onlineCustomerName").value.trim(),
                notes: document.getElementById("onlineCustomerNotes").value.trim()
            };

            try {
                const res = await fetch("/api/appointments", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const result = await res.json();
                alert(result.message || "Enrolled in virtual queue!");
                
                const modal = bootstrap.Modal.getInstance(document.getElementById("customerBookingModal"));
                if (modal) modal.hide();
                bookingForm.reset();

                // Refresh cards to reflect updated line counts
                const fresh = await fetch("/api/businesses");
                if (fresh.ok) {
                    allLoadedBusinesses = await fresh.json();
                    renderCustomerCards(allLoadedBusinesses);
                }
            } catch (error) {
                console.error("Booking error:", error);
            }
        });
    }
});