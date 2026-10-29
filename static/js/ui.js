
/* CityPulse UI controller. This original Flask version uses demo sign-in. */
let allLoadedBusinesses = [];
let currentUser = null;
let selectedRole = "customer";
let toastTimer = null;

const $ = (id) => document.getElementById(id);

function safeText(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;",
        '"': "&quot;", "'": "&#39;"
    })[char]);
}

function setPage(pageId) {
    ["landingView", "loginView", "appShell"].forEach((id) => {
        const el = $(id);
        if (el) el.hidden = id !== pageId;
    });
    window.scrollTo({ top: 0, behavior: "auto" });
}

function toast(message) {
    let el = $("cityPulseToast");
    if (!el) {
        el = document.createElement("div");
        el.id = "cityPulseToast";
        el.className = "toast-like";
        el.setAttribute("role", "status");
        document.body.appendChild(el);
    }
    el.textContent = message;
    el.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => { el.hidden = true; }, 3300);
}
window.toast = toast;

function chooseRole(role) {
    selectedRole = role === "merchant" ? "merchant" : "customer";
    document.querySelectorAll(".role-btn").forEach((button) => {
        const active = button.dataset.role === selectedRole;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
    });
}

function showLogin() {
    if ($("loginError")) {
        $("loginError").hidden = true;
        $("loginError").textContent = "";
    }
    setPage("loginView");
    window.setTimeout(() => $("loginUsername")?.focus(), 40);
}

function showApp(user) {
    currentUser = user;
    window.cityPulseCurrentUser = user;
    window.cityPulseRole = user.role;
    setPage("appShell");

    const displayName = user.name ||
        (user.role === "merchant" ? "Merchant" : "Customer");

    if ($("userNameLabel")) $("userNameLabel").textContent = displayName;
    if ($("dropdownUserName")) $("dropdownUserName").textContent = displayName;
    if ($("dropdownUserRole")) $("dropdownUserRole").textContent = user.role;
    if ($("userAvatar")) {
        $("userAvatar").textContent = displayName.trim().charAt(0).toUpperCase() || "U";
    }
    if ($("customerGreeting")) {
        $("customerGreeting").textContent = `Hello, ${displayName}.`;
    }

    closeUserMenu();
    renderWorkspace(user.role);

    if (user.role === "customer") loadBusinesses();
}

// This function only renders a workspace after the server has confirmed the role.
function renderWorkspace(viewName) {
    const view = viewName === "merchant" ? "merchant" : "customer";
    const customerView = $("viewCustomer");
    const merchantView = $("viewMerchant");

    if (customerView) customerView.hidden = view !== "customer";
    if (merchantView) merchantView.hidden = view !== "merchant";
    window.cityPulseRole = view;

    if (view === "merchant" && typeof window.refreshMerchantConsole === "function") {
        window.refreshMerchantConsole();
    }
}

// Keep the browser workspace and Flask session in sync. The API remains the
// authority for merchant access; a client-side role change alone is not enough.
async function switchView(viewName) {
    const requestedRole = viewName === "merchant" ? "merchant" : "customer";
    if (!currentUser) {
        showLogin();
        return false;
    }
    if (currentUser.role === requestedRole) {
        renderWorkspace(requestedRole);
        return true;
    }

    try {
        const response = await fetch("/api/auth/role", {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({ role: requestedRole })
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.error || "You are not authorized for that workspace.");
        currentUser = result.user;
        window.cityPulseCurrentUser = currentUser;
        if ($("dropdownUserRole")) $("dropdownUserRole").textContent = currentUser.role;
        renderWorkspace(currentUser.role);
        if (currentUser.role === "customer") loadBusinesses();
        return true;
    } catch (error) {
        toast(error.message || "You are not authorized for that workspace.");
        renderWorkspace(currentUser.role);
        return false;
    }
}
window.switchView = switchView;

function closeUserMenu() {
    const menu = $("userMenuDropdown");
    const button = $("userMenuBtn");
    if (menu) menu.hidden = true;
    if (button) button.setAttribute("aria-expanded", "false");
}

async function logout() {
    try {
        await fetch("/api/auth/logout", { method: "POST", headers: { "Accept": "application/json" } });
    } catch (error) {
        console.warn("Server sign-out request did not complete.", error);
    }
    currentUser = null;
    window.cityPulseCurrentUser = null;
    window.cityPulseRole = null;
    closeUserMenu();
    if ($("loginForm")) $("loginForm").reset();
    chooseRole("customer");
    setPage("landingView");
    toast("You have signed out.");
}

async function postJSON(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
    return result;
}

function showLoginError(message) {
    const error = $("loginError");
    if (!error) return;
    error.textContent = message;
    error.hidden = false;
}

async function loginAsDemo() {
    const displayName = ($("loginUsername")?.value || "").trim();
    try {
        const result = await postJSON("/api/auth/guest", {
            role: selectedRole,
            name: displayName,
            remember: Boolean($("rememberMe")?.checked)
        });
        showApp(result.user);
        toast(`Demo ${selectedRole} session started.`);
    } catch (error) {
        showLoginError(error.message);
    }
}

async function handleGoogleCredential(response) {
    if (!response || !response.credential) {
        showLoginError("Google did not return a sign-in credential. Please try again.");
        return;
    }
    try {
        const result = await postJSON("/api/auth/google", {
            credential: response.credential,
            remember: Boolean($("rememberMe")?.checked)
        });
        let user = result.user;
        if (selectedRole === "merchant") {
            const roleResponse = await fetch("/api/auth/role", {
                method: "PUT",
                headers: { "Content-Type": "application/json", "Accept": "application/json" },
                body: JSON.stringify({ role: "merchant" })
            });
            const roleResult = await roleResponse.json().catch(() => ({}));
            if (!roleResponse.ok) {
                await fetch("/api/auth/logout", { method: "POST" });
                throw new Error(roleResult.error || "This Google account is not authorized for the merchant workspace.");
            }
            user = roleResult.user;
        }
        showApp(user);
        toast(`Welcome, ${user.name}.`);
    } catch (error) {
        showLoginError(error.message);
    }
}
window.handleGoogleCredential = handleGoogleCredential;

function initializeGoogleSignIn() {
    const host = $("googleSignInBtn");
    const clientId = window.CITYPULSE_GOOGLE_CLIENT_ID || "";
    if (!host) return;
    if (!clientId) {
        host.innerHTML = '<button type="button" class="google-btn google-disabled" disabled><span class="google-g">G</span> Google sign-in needs setup</button>';
        return;
    }
    if (!window.google?.accounts?.id || host.dataset.initialized === "true") return;
    host.dataset.initialized = "true";
    window.google.accounts.id.initialize({
        client_id: clientId,
        callback: handleGoogleCredential,
        auto_select: false
    });
    const buttonWidth = Math.min(340, Math.max(240, (document.documentElement.clientWidth || 380) - 80));
    window.google.accounts.id.renderButton(host, {
        type: "standard", theme: "outline", size: "large",
        text: "continue_with", shape: "rectangular", width: buttonWidth
    });
}
window.initializeGoogleSignIn = initializeGoogleSignIn;

function titleCaseName(value) {
    const trimmed = String(value || "").trim();
    if (!trimmed.includes("@")) return trimmed;

    const localPart = trimmed.split("@")[0]
        .replace(/[._+-]+/g, " ")
        .trim();

    return localPart.replace(/\b\p{L}/gu, (letter) =>
        letter.toUpperCase()
    ) || "Customer";
}

function waitWindow(queueCount) {
    const wait = Math.max(0, Number(queueCount) || 0) * 15;
    return wait === 0 ? "0–5 min" :
        `${Math.max(5, wait - 5)}–${wait + 10} min`;
}

function renderCustomerCards(businesses) {
    const container = $("businessCardsGrid");
    if (!container) return;

    container.innerHTML = "";
    const countLabel = $("businessCount");

    if (countLabel) countLabel.textContent = `${(businesses || []).length} services`;

    if (!businesses || businesses.length === 0) {
        container.innerHTML =
            '<div class="col-12"><div class="empty-state">No businesses match those filters yet. Try another city or category.</div></div>';
        return;
    }

    businesses.forEach((business) => {
        const status = String(business.status || "open").toLowerCase();
        const badgeClass = status === "busy"
            ? "badge-status-busy"
            : (status === "closed"
                ? "badge-status-closed"
                : "badge-status-open");

        const count = Number(business.current_queue) || 0;
        const col = document.createElement("div");
        col.className = "col-sm-6 col-lg-4";

        col.innerHTML = `
          <article class="cp-card d-flex flex-column">
            <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
              <h5 class="fw-bold mb-0">${safeText(business.name || "Local business")}</h5>
              <span class="badge ${badgeClass} rounded-pill text-uppercase px-2 py-2">${safeText(status)}</span>
            </div>
            <p class="business-card-meta mb-3">${safeText(business.category || "Local service")} <span aria-hidden="true">·</span> ${safeText(business.city || "Nearby")}</p>
            <div class="business-stat-row"><span>Current line</span><strong>${count} ${count === 1 ? "person" : "people"}</strong></div>
            <div class="business-stat-row mb-4"><span>Estimated wait</span><strong>${waitWindow(count)}</strong></div>
            <button type="button" class="btn btn-cp-outline w-100 mt-auto book-business-btn" data-business-id="${Number(business.id) || 0}">Book Now <span aria-hidden="true">→</span></button>
          </article>`;

        container.appendChild(col);

        const bookButton = col.querySelector(".book-business-btn");
        bookButton.addEventListener("click", () => {
            openCustomerBookingModal(
                Number(business.id) || 0,
                business.name || "Local business"
            );
        });
    });
}

async function loadBusinesses() {
    const container = $("businessCardsGrid");

    if (container && !allLoadedBusinesses.length) {
        container.innerHTML =
            '<div class="col-12"><div class="empty-state">Loading local services…</div></div>';
    }

    try {
        const response = await fetch("/api/businesses", {
            headers: { "Accept": "application/json" }
        });

        if (!response.ok) {
            throw new Error(`Business list returned ${response.status}`);
        }

        allLoadedBusinesses = await response.json();
        handleFilterChange();
    } catch (error) {
        console.error("Could not load CityPulse businesses:", error);
        if (container) {
            container.innerHTML =
                '<div class="col-12"><div class="empty-state">Could not load services. Check that the Flask server is running and the database is initialized.</div></div>';
        }
    }
}

function handleFilterChange() {
    const query = ($("searchInput")?.value || "").trim().toLowerCase();
    const city = $("cityFilter")?.value || "";
    const category = $("categoryFilter")?.value || "";

    const filtered = allLoadedBusinesses.filter((business) => {
        const name = String(business.name || "").toLowerCase();
        const businessCity = String(business.city || "");
        const businessCategory = String(business.category || "");

        return name.includes(query) &&
            (!city || businessCity === city) &&
            (!category || businessCategory === category ||
                businessCategory.toLowerCase().includes(category.toLowerCase()));
    });

    renderCustomerCards(filtered);
}

function openCustomerBookingModal(businessId, businessName) {
    if (!(window.bootstrap && bootstrap.Modal)) {
        toast("Booking dialog could not open. Please reload the page.");
        return;
    }

    $("modalBusinessId").value = String(businessId);
    $("customerBookingModalTitle").textContent = `Book at ${businessName}`;
    $("onlineCustomerName").value = currentUser?.name || "";

    const modalEl = $("customerBookingModal");
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
}
window.openCustomerBookingModal = openCustomerBookingModal;

async function handleLoginSubmit(event) {
    event.preventDefault();
    if ($("loginError")) { $("loginError").hidden = true; $("loginError").textContent = ""; }
    const email = ($("loginUsername")?.value || "").trim();
    const password = $("loginPassword")?.value || "";
    if (!email || !password) {
        showLoginError("Enter the email and password for your CityPulse account. For a demo session, use Continue as demo.");
        return;
    }
    try {
        const result = await postJSON("/api/auth/login", {
            email, password, role: selectedRole,
            remember: Boolean($("rememberMe")?.checked)
        });
        showApp(result.user);
        toast(`Welcome back, ${result.user.name}.`);
    } catch (error) {
        showLoginError(error.message);
    }
}

async function handleRegisterSubmit(event) {
    event.preventDefault();
    const name = ($("registerName")?.value || "").trim();
    const email = ($("registerEmail")?.value || "").trim();
    const password = $("registerPassword")?.value || "";
    const confirm = $("registerPasswordConfirm")?.value || "";
    const error = $("registerError");
    if (password !== confirm) {
        error.textContent = "The passwords do not match."; error.hidden = false; return;
    }
    try {
        const result = await postJSON("/api/auth/register", {
            name, email, password,
            remember: Boolean($("rememberMe")?.checked), role: "customer"
        });
        bootstrap.Modal.getOrCreateInstance($("signupModal")).hide();
        $("registerForm").reset();
        showApp(result.user);
        toast("Your CityPulse account has been created.");
    } catch (err) {
        error.textContent = err.message; error.hidden = false;
    }
}

async function handleForgotPasswordSubmit(event) {
    event.preventDefault();
    const error = $("forgotPasswordError");
    const email = ($("forgotPasswordEmail")?.value || "").trim();
    error.hidden = true;
    try {
        const result = await postJSON("/api/auth/forgot-password", { email });
        bootstrap.Modal.getOrCreateInstance($("forgotPasswordModal")).hide();
        $("forgotPasswordForm").reset();
        toast(result.message || "If an account exists, a reset email has been sent.");
    } catch (err) {
        error.textContent = err.message; error.hidden = false;
    }
}

async function handleResetPasswordSubmit(event) {
    event.preventDefault();
    const params = new URLSearchParams(window.location.search);
    const token = params.get("reset_token") || "";
    const email = params.get("email") || "";
    const password = $("resetNewPassword")?.value || "";
    const confirm = $("resetConfirmPassword")?.value || "";
    const error = $("resetPasswordError");
    if (password !== confirm) { error.textContent = "The passwords do not match."; error.hidden = false; return; }
    try {
        const result = await postJSON("/api/auth/reset-password", { email, token, password });
        bootstrap.Modal.getOrCreateInstance($("resetPasswordModal")).hide();
        window.history.replaceState({}, "", window.location.pathname);
        $("resetPasswordForm").reset();
        showLogin();
        toast(result.message || "Password reset. Please sign in.");
    } catch (err) { error.textContent = err.message; error.hidden = false; }
}

async function submitBooking(event) {
    event.preventDefault();

    const name = ($("onlineCustomerName").value || "").trim();
    if (!name) {
        toast("Please enter a name for this booking.");
        return;
    }

    const submit = event.submitter;
    if (submit) submit.disabled = true;

    const payload = {
        business_id: Number($("modalBusinessId").value),
        service_id: Number($("onlineServiceSelect").value),
        customer_name: name,
        notes: ($("onlineCustomerNotes").value || "").trim()
    };

    try {
        const response = await fetch("/api/appointments", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || "Booking could not be created.");
        }

        const modal = bootstrap.Modal.getInstance($("customerBookingModal"));
        if (modal) modal.hide();

        $("onlineBookingForm").reset();
        toast(result.message || "Your booking was created.");
        await loadBusinesses();
    } catch (error) {
        toast(error.message || "Booking failed. Please try again.");
    } finally {
        if (submit) submit.disabled = false;
    }
}

function closeHomeLinks() {
    setPage("landingView");
    $("top")?.scrollIntoView({ behavior: "smooth" });
}

document.addEventListener("DOMContentLoaded", () => {
    // Landing-to-login navigation.
    ["navGetStarted", "heroGetStarted", "bottomGetStarted"].forEach((id) =>
        $(id)?.addEventListener("click", showLogin)
    );

    $("backToHomeBtn")?.addEventListener("click", closeHomeLinks);
    $("brandHomeLink")?.addEventListener("click", (event) => {
        event.preventDefault();
        closeHomeLinks();
    });
    $("loginBrandLink")?.addEventListener("click", (event) => {
        event.preventDefault();
        closeHomeLinks();
    });
    $("appBrandLink")?.addEventListener("click", (event) => {
        event.preventDefault();
        logout();
    });

    document.querySelectorAll(".role-btn").forEach((button) => {
        button.addEventListener("click", () => chooseRole(button.dataset.role));
    });

    $("loginForm")?.addEventListener("submit", handleLoginSubmit);
    $("demoSignInBtn")?.addEventListener("click", loginAsDemo);
    $("registerForm")?.addEventListener("submit", handleRegisterSubmit);
    $("forgotPasswordForm")?.addEventListener("submit", handleForgotPasswordSubmit);
    $("resetPasswordForm")?.addEventListener("submit", handleResetPasswordSubmit);

    $("forgotPasswordBtn")?.addEventListener("click", () => {
        if ($("loginUsername")?.value.includes("@")) $("forgotPasswordEmail").value = $("loginUsername").value.trim();
        bootstrap.Modal.getOrCreateInstance($("forgotPasswordModal")).show();
    });

    $("signUpBtn")?.addEventListener("click", () => {
        if (selectedRole === "merchant") {
            toast("Merchant access must be assigned by the administrator. Create a customer account or use an authorized merchant login.");
            return;
        }
        bootstrap.Modal.getOrCreateInstance($("signupModal")).show();
    });

    $("togglePasswordBtn")?.addEventListener("click", () => {
        const field = $("loginPassword");
        const showing = field.type === "text";
        field.type = showing ? "password" : "text";
        $("togglePasswordBtn").setAttribute(
            "aria-label",
            showing ? "Show password" : "Hide password"
        );
    });

    $("userMenuBtn")?.addEventListener("click", (event) => {
        event.stopPropagation();
        const menu = $("userMenuDropdown");
        const open = menu.hidden;
        menu.hidden = !open;
        $("userMenuBtn").setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("click", (event) => {
        if (!event.target.closest(".user-menu-wrap")) closeUserMenu();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeUserMenu();
    });

    $("logoutBtn")?.addEventListener("click", logout);

    $("profileMenuBtn")?.addEventListener("click", () => {
        closeUserMenu();
        toast("Profile settings are not configured in this prototype.");
    });

    $("settingsMenuBtn")?.addEventListener("click", () => {
        closeUserMenu();
        toast("Settings are not configured in this prototype.");
    });

    $("searchInput")?.addEventListener("input", handleFilterChange);
    $("cityFilter")?.addEventListener("change", handleFilterChange);
    $("categoryFilter")?.addEventListener("change", handleFilterChange);
    $("onlineBookingForm")?.addEventListener("submit", submitBooking);

    // Optional name / #n walk-in control.
    const walkInName = $("walkInCustomerName");
    const numberBtn = $("walkInNumberBtn");

    numberBtn?.addEventListener("click", () => {
        const checkbox = $("walkInUseNumber");
        checkbox.checked = !checkbox.checked;
        numberBtn.setAttribute("aria-pressed", String(checkbox.checked));
        numberBtn.textContent = checkbox.checked ? "Using #n ✓" : "Use #n";

        if (checkbox.checked && walkInName) {
            walkInName.value = "";
            walkInName.disabled = true;
        } else if (walkInName) {
            walkInName.disabled = false;
            walkInName.focus();
        }
    });

    walkInName?.addEventListener("input", () => {
        if ($("walkInUseNumber")?.checked) {
            $("walkInUseNumber").checked = false;
            numberBtn?.setAttribute("aria-pressed", "false");
            if (numberBtn) numberBtn.textContent = "Use #n";
        }
    });

    // Render the real Google Identity button only when an OAuth client ID is configured.
    window.addEventListener("load", initializeGoogleSignIn, { once: true });
    if (document.readyState === "complete") initializeGoogleSignIn();

    // Restore the server session (not a client-only role) after reload.
    fetch("/api/me", { headers: { "Accept": "application/json" } })
        .then((response) => response.json())
        .then((state) => {
            if (state.authenticated && state.user) showApp(state.user);
            else setPage("landingView");
        })
        .catch(() => setPage("landingView"));

    // Password-reset links arrive as /?reset_token=...&email=...
    const query = new URLSearchParams(window.location.search);
    if (query.has("reset_token") && query.has("email")) {
        window.setTimeout(() => bootstrap.Modal.getOrCreateInstance($("resetPasswordModal")).show(), 150);
    }
});
