
/* Customer city selection for CityPulse.
   The selected city is stored in this browser and applied to the existing city filter. */
(() => {
    "use strict";

    const STORAGE_KEY = "citypulse_customer_city";
    const $ = (id) => document.getElementById(id);

    function activeRole() {
        return document.querySelector(".role-btn.active")?.dataset.role || "customer";
    }

    function selectedCity() {
        return ($("customerCityInput")?.value || "")
            .trim()
            .replace(/\s+/g, " ");
    }

    function showCityField() {
        const field = $("customerCityField");
        const input = $("customerCityInput");
        const isCustomer = activeRole() === "customer";

        if (field) field.hidden = !isCustomer;
        if (input) input.required = isCustomer;
    }

    function applyCity(city, notify = true) {
        const cleanCity = String(city || "")
            .trim()
            .replace(/\s+/g, " ");

        if (!cleanCity) return false;

        try {
            localStorage.setItem(STORAGE_KEY, cleanCity);
        } catch (_) {}

        const filter = $("cityFilter");

        if (filter) {
            let option = Array.from(filter.options).find(
                (item) => item.value.toLowerCase() === cleanCity.toLowerCase()
            );

            if (!option) {
                option = document.createElement("option");
                option.value = cleanCity;
                option.textContent = cleanCity;
                filter.appendChild(option);
            }

            filter.value = option.value;

            if (notify) {
                filter.dispatchEvent(
                    new Event("change", { bubbles: true })
                );
            }
        }

        const chip = $("customerCityChipLabel");

        if (chip) {
            chip.textContent = cleanCity;
        }

        return true;
    }

    function requireCustomerCity(event) {
        // Merchants do not need to provide a city to sign in.
        if (activeRole() !== "customer") return true;

        const city = selectedCity();

        if (!city) {
            if (event) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }

            const input = $("customerCityInput");

            input?.focus();

            input?.setCustomValidity(
                "Please enter your city to continue as a customer."
            );

            input?.reportValidity();

            input?.addEventListener(
                "input",
                () => input.setCustomValidity(""),
                { once: true }
            );

            return false;
        }

        applyCity(city, false);
        return true;
    }

    function restoreCity() {
        let saved = "";

        try {
            saved = localStorage.getItem(STORAGE_KEY) || "";
        } catch (_) {}

        if (saved) {
            if ($("customerCityInput")) {
                $("customerCityInput").value = saved;
            }

            applyCity(saved, false);
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        restoreCity();
        showCityField();

        // Show or hide the city field when the account type changes.
        document.querySelectorAll(".role-btn").forEach((button) => {
            button.addEventListener("click", () => {
                window.setTimeout(showCityField, 0);
            });
        });

        // Clear any previous validation message when the user starts typing.
        $("customerCityInput")?.addEventListener("input", () => {
            $("customerCityInput").setCustomValidity("");
        });

        // Capture-phase validation runs before the existing UI handlers.
        $("loginForm")?.addEventListener(
            "submit",
            requireCustomerCity,
            true
        );

        $("demoSignInBtn")?.addEventListener(
            "click",
            requireCustomerCity,
            true
        );

        $("registerForm")?.addEventListener(
            "submit",
            requireCustomerCity,
            true
        );

        // Validate before the customer uses Google sign-in.
        $("googleSignInBtn")?.addEventListener(
            "click",
            requireCustomerCity,
            true
        );

        $("googleSignInBtn")?.addEventListener(
            "pointerdown",
            requireCustomerCity,
            true
        );

        // Keep the saved city selected when an existing session is restored.
        const saved = selectedCity() || (() => {
            try {
                return localStorage.getItem(STORAGE_KEY) || "";
            } catch (_) {
                return "";
            }
        })();

        if (saved) {
            applyCity(saved, false);
        }
    });

    // Helpers available to other CityPulse scripts if needed later.
    window.getCityPulseCustomerCity = selectedCity;
    window.applyCityPulseCustomerCity = applyCity;
})();
