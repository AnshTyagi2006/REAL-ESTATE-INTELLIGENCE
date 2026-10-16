(function () {

  "use strict";



  // Shared helpers: select the first matching element and escape API values before HTML insertion.

  const $ = (selector) => document.querySelector(selector);

  const esc = (value) => String(value ?? "")

    .replaceAll("&", "&amp;")

    .replaceAll("<", "&lt;")

    .replaceAll(">", "&gt;")

    .replaceAll('"', "&quot;")

    .replaceAll("'", "&#039;");



  // Applies a normalized theme, persists it, and synchronizes the toggle's accessibility state.

  function applyTheme(theme) {

    const safeTheme = theme === "dark" ? "dark" : "light";

    document.documentElement.dataset.theme = safeTheme;

    localStorage.setItem("theme", safeTheme);



    const toggle = $("#theme-toggle");

    if (toggle) {

      toggle.setAttribute("aria-pressed", String(safeTheme === "dark"));

      toggle.setAttribute(

        "aria-label",

        safeTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"

      );

    }

  }



  // Chooses the saved/system theme on startup and connects the button to theme switching.

  function initTheme() {

    const savedTheme = localStorage.getItem("theme");

    const initial = savedTheme || "light";

    applyTheme(initial);



    const toggle = $("#theme-toggle");

    if (toggle) {

      toggle.addEventListener("click", () => {

        applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

      });

    }

  }



  // Rotating example searches shown in the search field while it is empty and unfocused.

  const placeholders = [

    "Search city, locality or property type...",

    "Explore properties in Gurgaon",

    "Find homes in Delhi NCR",

    "Compare properties by locality",

    "Search properties by value",

    "Explore market prices"

  ];

  let placeholderIndex = 0;

  let characterIndex = 0;

  let deleting = false;

  let placeholderTimer = null;

  let placeholderPaused = false;



  // Types and erases one example phrase at a time; stops when the field is active or populated.

  function animatePlaceholder() {

    const input = $("#hero-search-input");

    if (!input || placeholderPaused || document.activeElement === input || input.value) return;



    const phrase = placeholders[placeholderIndex];

    characterIndex += deleting ? -1 : 1;

    input.placeholder = phrase.slice(0, characterIndex);



    let delay = deleting ? 42 : 68;

    if (!deleting && characterIndex >= phrase.length) {

      deleting = true;

      delay = 1700;

    } else if (deleting && characterIndex <= 0) {

      deleting = false;

      placeholderIndex = (placeholderIndex + 1) % placeholders.length;

      delay = 400;

    }



    placeholderTimer = window.setTimeout(animatePlaceholder, delay);

  }



  // Cancels the current typing timer while the user interacts with the search input.

  function pausePlaceholder() {

    placeholderPaused = true;

    if (placeholderTimer) window.clearTimeout(placeholderTimer);

  }



  // Restarts placeholder animation after focus leaves an empty search field.

  function resumePlaceholder() {

    const input = $("#hero-search-input");

    if (!input || input.value || document.activeElement === input) return;



    placeholderPaused = false;

    if (placeholderTimer) window.clearTimeout(placeholderTimer);

    placeholderTimer = window.setTimeout(animatePlaceholder, 400);

  }



  // Attaches focus/input/blur handlers so placeholder animation never competes with user typing.

  function initPlaceholder() {

    const input = $("#hero-search-input");

    if (!input) return;



    input.addEventListener("focus", pausePlaceholder);

    input.addEventListener("input", () => {

      pausePlaceholder();

      input.placeholder = "";

    });

    input.addEventListener("blur", () => {

      if (!input.value.trim()) resumePlaceholder();

    });

    animatePlaceholder();

  }



  // Validates the hero search and routes non-empty queries to the property search page.

  function initHeroSearch() {

    const form = $("#hero-search-form");

    const input = $("#hero-search-input");

    if (!form || !input) return;



    form.addEventListener("submit", (event) => {

      const value = input.value.trim();

      if (!value) {

        event.preventDefault();

        input.focus();

        return;

      }

      event.preventDefault();

      window.location.href = "/search?city=" + encodeURIComponent(value);

    });

  }



  // Formats numeric INR listing prices as crore, lakh, or localized rupee amounts.

  function price(value) {

    const number = Number(value);

    if (!Number.isFinite(number) || number <= 0) return "Price on Request";

    if (number >= 1e7) return `₹${(number / 1e7).toFixed(2)} Cr`;

    if (number >= 1e5) return `₹${(number / 1e5).toFixed(2)} L`;

    return `₹${Math.round(number).toLocaleString("en-IN")}`;

  }



  // Reads numeric prices/percentages supplied by the API without treating missing values as zero.

  function numericValue(value) {

    if (value == null || value === "") return null;

    const number = typeof value === "number" ? value : Number(String(value).replace(/[₹,%\s,]/g, ""));

    return Number.isFinite(number) ? number : null;

  }



  // Returns prediction premium/discount percentage, preferring the backend's explicit comparison.

  function predictionDifference(property) {

    const percentageFields = [

      "predicted_vs_asking_percent",

      "prediction_vs_asking_percent",

      "prediction_difference_percent",

      "prediction_percentage_difference",

      "predicted_value_difference_percent",

      "predicted_price_difference_percent",

      "predicted_price_vs_asking_percent",

      "valuation_difference_percent",

      "valuation_vs_asking_percent",

      "estimate_vs_asking_percent",

      "asking_price_difference_percent",

      "price_difference_percent",

      "prediction_diff_percent",

      "prediction_diff_pct",

      "price_difference_pct",

      "prediction_vs_asking_pct",

      "predicted_vs_asking_pct"

    ];



    for (const field of percentageFields) {

      const value = numericValue(property[field]);

      if (value !== null) return value;

    }



    const predicted = numericValue(

      property.predicted_value_inr ?? property.predicted_price_inr ?? property.predicted_valuation_inr ??

      property.predicted_value ?? property.predicted_price ?? property.predicted_valuation ??

      property.estimated_value_inr ?? property.estimated_value

    );

    const asking = numericValue(

      property.asking_price_inr ?? property.asking_price ?? property.listing_price_inr ??

      property.listing_price ?? property.price_inr

    );

    return predicted !== null && asking > 0 ? ((predicted - asking) / asking) * 100 : null;

  }



  // Builds an escaped property-card template from one activity or recommendation record.

  function card(property) {

    const id = property.property_id || property.id || property.listing_id || "";
    const areaValue = property.valuation_area_sqft ?? property.area_sqft ?? property.area ?? null;
    const area = property.area_formatted || (
      numericValue(areaValue) !== null
        ? `${Math.round(numericValue(areaValue)).toLocaleString("en-IN")} sqft`
        : "—"
    );
    const title = property.title || property.property_name || property.name || property.locality || "Property";
    const city = [property.locality, property.city || property.city_name].filter(Boolean).join(", ") || "India";
    const bedrooms = property.bedrooms ?? property.bhk ?? property.bedroom_count ?? "—";
    const askingPrice = numericValue(
      property.asking_price_inr ?? property.asking_price ?? property.listing_price_inr ??
      property.listing_price ?? property.price_inr ?? property.price
    );
    const priceValue = property.price_formatted || property.asking_price_formatted || price(askingPrice);
    const predicted = numericValue(
      property.predicted_value_inr ?? property.predicted_price_inr ?? property.predicted_valuation_inr ??
      property.predicted_value ?? property.predicted_price ?? property.predicted_valuation ??
      property.estimated_value_inr ?? property.estimated_value
    );

    // Compare asking price directly with the model valuation. Positive display values are intentional.
    let comparisonDirection = "unavailable";
    let comparisonValue = "—";
    let comparisonLabel = "prediction unavailable";
    let comparisonArrow = "";

    if (askingPrice !== null && askingPrice > 0 && predicted !== null && predicted > 0) {
      const percentage = Math.abs((askingPrice - predicted) / predicted * 100);
      comparisonValue = `${percentage.toFixed(1)}%`;
      if (askingPrice < predicted) {
        comparisonDirection = "below_valuation";
        comparisonLabel = "below predicted value";
        comparisonArrow = "↗";
      } else if (askingPrice > predicted) {
        comparisonDirection = "above_valuation";
        comparisonLabel = "above predicted value";
        comparisonArrow = "↘";
      } else {
        comparisonDirection = "equal";
        comparisonLabel = "at predicted value";
      }
    } else {
      // Use a backend-provided comparison only when the underlying values are not included.
      const supplied = numericValue(
        property.asking_vs_predicted_percent ?? property.predicted_vs_asking_percent ??
        property.prediction_difference_percent ?? property.valuation_difference_percent
      );
      const direction = String(property.prediction_direction || property.valuation_direction || "").toLowerCase();
      if (supplied !== null && direction) {
        comparisonValue = `${Math.abs(supplied).toFixed(1)}%`;
        if (["below_valuation", "below_predicted", "potential_upside", "under_valuation"].includes(direction)) {
          comparisonDirection = "below_valuation";
          comparisonLabel = "below predicted value";
          comparisonArrow = "↗";
        } else if (["above_valuation", "above_predicted", "over_valuation"].includes(direction)) {
          comparisonDirection = "above_valuation";
          comparisonLabel = "above predicted value";
          comparisonArrow = "↘";
        }
      }
    }



    return `



      <article class="property-card">

        <div class="property-card-top">

          <div class="location-icon" aria-hidden="true">

            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" focusable="false">

              <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"></path>

              <circle cx="12" cy="10" r="2.5"></circle>

            </svg>

          </div>

          <div class="property-name-wrap">

            <h3>${esc(title)}</h3>

            <span>${esc(city)}</span>

          </div>

        </div>

        <svg class="property-architecture" viewBox="0 0 100 100" fill="none" aria-hidden="true" focusable="false">

          <path d="M10 90V58L23 48V90"></path>

          <path d="M23 90V36L39 23V90"></path>

          <path d="M39 90V12L53 4V90"></path>

          <path d="M53 90V28L68 17V90"></path>

          <path d="M68 90V45L82 35V90"></path>

          <path d="M4 90H90"></path>

          <path d="M16 65H25"></path>

          <path d="M16 73H25"></path>

          <path d="M30 52H38"></path>

          <path d="M30 61H38"></path>

          <path d="M45 31H52"></path>

          <path d="M45 40H52"></path>

          <path d="M59 45H67"></path>

          <path d="M59 54H67"></path>

          <path d="M73 59H81"></path>

          <path d="M73 68H81"></path>

        </svg>

        <div class="card-divider"><span></span></div>

        <div class="property-price-growth">

          <div class="property-price">

            <strong>${esc(priceValue)}</strong>

            <span>Asking price</span>

          </div>

          <div class="property-growth property-comparison ${comparisonDirection}" aria-label="${esc(comparisonValue)} ${esc(comparisonLabel)}">

            <strong><span class="comparison-dot" aria-hidden="true"></span>${esc(comparisonValue)}</strong>

            <span>${esc(comparisonLabel)}</span>

          </div>

        </div>

        <div class="property-card-bottom">

          <div class="property-meta">

            <div class="property-meta-item">

              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true" focusable="false">

                <path d="M4 18V8h16v10"></path><path d="M4 21h16"></path><path d="M8 8V5h8v3"></path>

                <path d="M8 12h.01"></path><path d="M12 12h.01"></path><path d="M16 12h.01"></path>

              </svg>

              <span>${esc(bedrooms)} BHK</span>

            </div>

            <div class="property-meta-item">

              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true" focusable="false">

                <rect x="4" y="4" width="16" height="16" rx="1"></rect><path d="M8 8h8"></path><path d="M8 12h8"></path><path d="M8 16h8"></path>

              </svg>

              <span>${esc(area)}</span>

            </div>

          </div>

          <button class="property-arrow" type="button" aria-label="Open ${esc(title)}" data-open-property="${esc(id)}">→</button>

        </div>

      </article>`;

  }



  // Checks the current session and redirects unauthenticated visitors to the entry page.

  async function currentUser() {

    const response = await fetch("/api/auth/me", {

      credentials: "same-origin",

      cache: "no-store"

    });

    const data = await response.json();

    if (!data.authenticated) {

      window.location.replace("/");

      return null;

    }

    return data.user;

  }



  // Loads the current user's activity without relying on cached responses.
  async function activity() {
    try {
      const response = await fetch("/api/user/activity", {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error(`Activity request failed (${response.status})`);
      return await response.json();
    } catch (error) {
      console.error("Could not load user activity", error);
      return null;
    }
  }

  function getViewed(data) {
    return data?.viewed || data?.recently_viewed || data?.recently_viewed_properties || data?.recent_views || [];
  }

  // Always show the activity section for signed-in users; new accounts get a clear empty state.
  function showActivity(data) {
    const viewed = getViewed(data);
    const section = $("#personalized-activity");
    const grid = $("#home-recently-viewed");
    if (!section || !grid) return;

    section.classList.remove("activity-hidden");
    grid.innerHTML = viewed.length
      ? viewed.slice(0, 4).map(card).join("")
      : `
        <div class="activity-empty-state">
          <span class="activity-empty-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false">
              <path d="M4 10.5 12 4l8 6.5V20H4z"></path>
              <path d="M9 20v-6h6v6"></path>
            </svg>
          </span>
          <span class="activity-empty-copy">
            <span>No recently viewed properties</span>
            <span>yet. <a href="/search">Explore properties →</a></span>
          </span>
        </div>`;
  }

  // Recommendations must be requested even for a new account with no searches or views.
  async function recommendations(data) {
    const section = $("#recommendations-section");
    const grid = $("#home-recommendations");
    if (!section || !grid) return;
    section.classList.remove("activity-hidden");
    grid.innerHTML = `<div class="activity-loading-state" role="status">Finding properties with strong value...</div>`;

    try {
      const response = await fetch("/api/user/recommendations", {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error(`Recommendations request failed (${response.status})`);
      const result = await response.json();
      let list = result.recommendations || result.properties || result.items || [];

      // If the endpoint has no candidates for an existing user, use their viewed properties rather than hide the section.
      if (!list.length) list = getViewed(data);
      if (list.length) {
        grid.innerHTML = list.slice(0, 4).map(card).join("");
      } else {
        grid.innerHTML = `
          <div class="activity-empty-state recommendation-empty-state">
            <span class="activity-empty-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false"><path d="M3 20h18M5 20V9l7-5 7 5v11M9 20v-6h6v6"></path></svg>
            </span>
            <span class="activity-empty-copy">
              <span>We're finding the best available properties</span>
              <span>Start with a city or locality to personalize your results. <a href="/search">Explore properties →</a></span>
            </span>
          </div>`;
      }
    } catch (error) {
      console.error("Could not load recommendations", error);
      const fallback = getViewed(data);
      grid.innerHTML = fallback.length
        ? fallback.slice(0, 4).map(card).join("")
        : `<div class="activity-empty-state recommendation-empty-state"><span class="activity-empty-copy"><span>Recommendations are temporarily unavailable.</span><span><a href="/search">Explore properties →</a></span></span></div>`;
    }
  }

  // Delegated handler routes any dynamically rendered property-card button to its detail page.

  document.addEventListener("click", (event) => {

    const button = event.target.closest("[data-open-property]");

    if (button && button.dataset.openProperty) {

      window.location.href = "/property/" + encodeURIComponent(button.dataset.openProperty);

    }

  });



  // Adds reveal-on-scroll behavior, with a fallback for browsers without IntersectionObserver.

  function motion() {

    const elements = document.querySelectorAll(".reveal");

    if (!("IntersectionObserver" in window)) {

      elements.forEach((element) => element.classList.add("is-visible"));

      return;

    }



    const observer = new IntersectionObserver((entries) => {

      entries.forEach((entry) => {

        if (entry.isIntersecting) {

          entry.target.classList.add("is-visible");

          observer.unobserve(entry.target);

        }

      });

    }, { threshold: 0.12 });

    elements.forEach((element) => observer.observe(element));

  }



  // Controls the compact navigation dropdown on small screens.

  function initMobileMenu() {

    const toggle = $("#mobile-menu-toggle");

    const panel = $("#header-menu-panel");

    if (!toggle || !panel) return;



    const close = () => {

      panel.classList.remove("open");

      toggle.setAttribute("aria-expanded", "false");

      toggle.setAttribute("aria-label", "Open navigation menu");

    };



    toggle.addEventListener("click", (event) => {

      event.stopPropagation();

      const isOpen = panel.classList.toggle("open");

      toggle.setAttribute("aria-expanded", String(isOpen));

      toggle.setAttribute("aria-label", isOpen ? "Close navigation menu" : "Open navigation menu");

    });

    panel.addEventListener("click", (event) => {

      if (event.target.closest("a")) close();

      event.stopPropagation();

    });

    document.addEventListener("click", close);

    document.addEventListener("keydown", (event) => {

      if (event.key === "Escape") {

        close();

        toggle.focus();

      }

    });

  }



  // Page startup: initialize local UI first, then load authenticated content and reveal effects.

  function initActivityRoute() {

    const path = window.location.pathname.replace(/\/+$/, "") || "/";

    if (path === "/activity") {

      document.body.classList.add("activity-page");

      document.title = "My Activity | Real Estate Intelligence";

    }

  }



  async function init() {

    initActivityRoute();

    initTheme();

    initMobileMenu();

    initPlaceholder();

    initHeroSearch();



    try {

      const user = await currentUser();

      if (!user) return;

      const data = (await activity()) || { viewed: [], searches: [], shortlisted: [] };
      showActivity(data);
      await recommendations(data);

    } catch (error) {

      console.error("Home initialization", error);

    } finally {

      motion();

    }

  }



  // Defer initialization until the page markup exists; initialize immediately if it is already ready.

  document.readyState === "loading"

    ? document.addEventListener("DOMContentLoaded", init)

    : init();

})();
