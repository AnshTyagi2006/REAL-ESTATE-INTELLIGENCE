/* ==========================================================================
   Real Estate Intelligence — live property dossier
   Design: premium architectural dossier. Data: existing Flask property APIs.
   Property photography is intentionally disabled; the hero uses the SVG
   architectural illustration and comparable cards use line-art icons only.
   ========================================================================== */
(function () {
  "use strict";

  const root = document.documentElement;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[char]);

  const propertyId = decodeURIComponent(location.pathname.split("/").filter(Boolean).pop() || "");
  let currentProperty = null;
  let currentValuation = null;

  function text(id, value, fallback = "Not available") {
    const element = document.getElementById(id);
    if (element) element.textContent = value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function validNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function money(value) {
    const number = validNumber(value);
    if (number === null || number <= 0) return "Price on Request";
    if (number >= 10000000) return `₹${(number / 10000000).toFixed(2)} Cr`;
    if (number >= 100000) return `₹${(number / 100000).toFixed(2)} L`;
    return `₹${Math.round(number).toLocaleString("en-IN")}`;
  }

  function formattedArea(property) {
    if (property.area_formatted && property.area_formatted !== "Area unavailable") return property.area_formatted;
    const area = validNumber(property.valuation_area_sqft);
    return area !== null && area > 0 ? `${Math.round(area).toLocaleString("en-IN")} sqft` : "Not available";
  }

  function showError(message) {
    const loading = $("#property-loading");
    const content = $("#property-content");
    const error = $("#property-error");
    if (loading) loading.style.display = "none";
    if (content) content.hidden = true;
    if (error) {
      error.hidden = false;
      const paragraph = $("p", error);
      if (paragraph) paragraph.textContent = message || "This property could not be loaded. Return to search and choose another listing.";
    }
  }

  function applyTheme(theme, persist) {
    const dark = theme === "dark";
    root.classList.toggle("dark", dark);
    const toggle = $("#themeToggle");
    if (toggle) {
      toggle.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
      toggle.setAttribute("title", dark ? "Switch to light theme" : "Switch to dark theme");
    }
    if (persist) {
      try { localStorage.setItem("rei-theme", theme); } catch (_) { /* session-only theme */ }
    }
  }

  let storedTheme = null;
  try { storedTheme = localStorage.getItem("rei-theme"); } catch (_) { /* storage disabled */ }
  applyTheme(storedTheme === "light" ? "light" : "dark", false);
  $("#themeToggle")?.addEventListener("click", () => {
    applyTheme(root.classList.contains("dark") ? "light" : "dark", true);
  });

  function renderTags(property) {
    const area = formattedArea(property);
    const floor = validNumber(property.floor);
    const totalFloors = validNumber(property.total_floors);
    const parking = property.parking ?? (validNumber(property.parking_count) !== null ? `${property.parking_count} parking` : null);
    const status = property.status ?? (property.ready_to_move === true || property.ready_to_move === 1 ? "Ready to Move" : property.under_construction === true || property.under_construction === 1 ? "Under Construction" : null);
    const tags = {
      "tag-type": property.property_type,
      "tag-furnishing": property.furnishing,
      "tag-status": status,
      "tag-bedrooms": validNumber(property.bedrooms) !== null ? `${property.bedrooms} BHK` : null,
      "tag-bathrooms": validNumber(property.bathrooms) !== null ? `${property.bathrooms} Bathrooms` : null,
      "tag-area": area !== "Not available" ? area : null,
      "tag-floor": floor !== null ? `Floor ${floor}${totalFloors !== null ? `/${totalFloors}` : ""}` : null,
      "tag-parking": parking
    };
    Object.entries(tags).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) {
        if (!value) element.hidden = true;
        else { element.hidden = false; const icon = $("svg", element); element.replaceChildren(); if (icon) element.appendChild(icon); element.append(` ${value}`); }
      }
    });
  }

  function renderDetails(property) {
    const area = formattedArea(property);
    const floor = validNumber(property.floor);
    const totalFloors = validNumber(property.total_floors);
    const details = {
      "detail-type": property.property_type,
      "detail-bedrooms": validNumber(property.bedrooms) !== null ? `${property.bedrooms} BHK` : null,
      "detail-bathrooms": property.bathrooms,
      "detail-area": area !== "Not available" ? area : null,
      "detail-floor": floor !== null ? `${floor}${totalFloors !== null ? ` out of ${totalFloors}` : ""}` : null,
      "detail-furnishing": property.furnishing,
      "detail-parking": property.parking ?? (validNumber(property.parking_count) !== null ? `${property.parking_count} parking` : null),
      "detail-status": property.status ?? (property.ready_to_move === true || property.ready_to_move === 1 ? "Ready to Move" : property.under_construction === true || property.under_construction === 1 ? "Under Construction" : null)
    };
    Object.entries(details).forEach(([id, value]) => text(id, value));

    const description = property.description;
    text("property-description", typeof description === "string" && description.trim() ? description.trim() : null,
      "No description was supplied with this listing. Specifications shown here come from the available source record.");

    const amenitiesHost = $("#property-amenities");
    if (amenitiesHost) {
      const raw = property.amenities ?? property.features;
      const items = Array.isArray(raw) ? raw : (typeof raw === "string" ? raw.split(/[;,|]/).map(v => v.trim()).filter(Boolean) : []);
      amenitiesHost.innerHTML = items.length
        ? items.slice(0, 12).map(item => `<li><span class="chip">${esc(item)}</span></li>`).join("")
        : "";
    }
  }

  function renderCore(property) {
    currentProperty = property;
    $("#property-loading")?.setAttribute("hidden", "");
    const loading = $("#property-loading");
    if (loading) loading.style.display = "none";
    $("#property-content").hidden = false;

    const title = property.title || property.property_name || property.society || "Property";
    document.title = `${title} | Real Estate Intelligence`;
    text("property-title", title);
    text("property-location-value", [property.locality, property.city].filter(Boolean).join(", ") || null);
    text("property-id-value", property.property_id || propertyId);
    text("asking-price", property.price_formatted || money(property.price_inr));
    text("asking-psf", property.price_per_sqft_formatted || (validNumber(property.price_per_sqft) ? `₹${Math.round(property.price_per_sqft).toLocaleString("en-IN")}/sqft` : null));
    text("area", formattedArea(property));
    text("bedrooms", validNumber(property.bedrooms) !== null ? `${property.bedrooms} BHK` : null);
    text("bathrooms", property.bathrooms);
    text("property-type", property.property_type);
    renderTags(property);
    renderDetails(property);

    // Explicitly remove any legacy image elements so no curated stock photo is
    // ever presented as the actual property.
    $$(".property-image, .property-thumbs, .comparable-img-wrap img").forEach(element => element.remove());

    renderMap(property);
    const back = $(".back-link");
    if (back) back.href = "/search";
  }

  function renderMap(property) {
    const lat = validNumber(property.latitude);
    const lon = validNumber(property.longitude);
    const iframe = $("#property-map");
    const openLink = $("#open-google-map");
    const label = $("#map-location-label");
    const coords = lat !== null && lon !== null && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;

    if (coords) {
      const query = `${lat},${lon}`;
      if (iframe) iframe.src = `https://www.google.com/maps?q=${encodeURIComponent(query)}&z=15&output=embed`;
      if (openLink) { openLink.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`; openLink.hidden = false; }
      if (label) label.textContent = `${lat.toFixed(5)}, ${lon.toFixed(5)} · ${[property.locality, property.city].filter(Boolean).join(", ")}`;
    } else {
      if (iframe) { iframe.removeAttribute("src"); iframe.setAttribute("title", "Map unavailable because this listing has no verified coordinates"); }
      if (openLink) { openLink.removeAttribute("href"); openLink.hidden = true; }
      if (label) label.textContent = `Exact coordinates were not supplied for ${[property.locality, property.city].filter(Boolean).join(", ") || "this listing"}.`;
    }
  }

  function renderValuation(valuation) {
    if (!valuation) return;
    currentValuation = valuation;
    const asking = validNumber(valuation.asking_price_inr) ?? validNumber(currentProperty?.price_inr);
    const estimated = validNumber(valuation.final_estimated_value);
    const comparable = validNumber(valuation.comparable_value);
    const ml = validNumber(valuation.ml_value);
    const locality = validNumber(valuation.locality_value);
    const discount = asking !== null && estimated !== null && estimated > 0 ? ((asking - estimated) / estimated) * 100 : null;

    text("asking-price", money(asking));
    text("comparable-value", money(comparable));
    text("final-value", money(estimated));
    text("opportunity-pct", discount === null ? "—" : `${discount > 0 ? "+" : ""}${discount.toFixed(1)}%`);
    text("opportunity-label", discount === null ? "Comparison unavailable" : discount < 0 ? "Below estimated value" : discount > 0 ? "Above estimated value" : "Near estimated value");
    const askingPsf = validNumber(currentProperty?.price_per_sqft);
    const area = validNumber(currentProperty?.valuation_area_sqft);
    const compPsf = comparable !== null && area ? comparable / area : null;
    const estimatePsf = estimated !== null && area ? estimated / area : null;
    text("asking-psf", askingPsf !== null ? `₹${Math.round(askingPsf).toLocaleString("en-IN")}/sqft` : (asking !== null && area ? `₹${Math.round(asking / area).toLocaleString("en-IN")}/sqft` : null));
    text("comparable-psf", compPsf !== null ? `₹${Math.round(compPsf).toLocaleString("en-IN")}/sqft` : null);
    text("final-psf", estimatePsf !== null ? `₹${Math.round(estimatePsf).toLocaleString("en-IN")}/sqft` : null);

    text("analysis-asking-price", money(asking));
    text("analysis-estimated-value", money(estimated));
    text("analysis-premium", discount === null ? "—" : `${discount > 0 ? "+" : ""}${discount.toFixed(1)}%`);
    text("asking-price-analysis", asking !== null && estimated !== null ? `Asking price ${money(asking)} vs final estimated value ${money(estimated)}.` : "Asking-price analysis is unavailable because one or both values are missing.");
    text("analysis-note", discount === null ? "A value opportunity cannot be calculated without both an asking price and a final estimate." :
      discount < 0 ? `The asking price is ${Math.abs(discount).toFixed(1)}% below the model's final estimate. This is an analytical signal, not a guarantee of investment return.` :
      discount > 0 ? `The asking price is ${discount.toFixed(1)}% above the model's final estimate. Compare listing quality and local evidence before drawing a conclusion.` :
      "The asking price matches the model's final estimate.");

    const signal = $("#signal");
    if (signal) {
      signal.textContent = valuation.price_signal || (discount === null ? "Insufficient data" : discount < -5 ? "Below estimated value" : discount > 5 ? "Above estimated value" : "Near estimate");
      signal.className = "signal-badge " + (discount === null ? "signal-neutral" : discount < -5 ? "signal-positive" : discount > 5 ? "signal-negative" : "signal-neutral");
    }
    const track = $("#priceTrack");
    if (track && asking !== null && estimated !== null && Math.max(asking, estimated) > 0) {
      const max = Math.max(asking, estimated) * 1.12;
      const askPct = Math.max(0, Math.min(100, asking / max * 100));
      const estPct = Math.max(0, Math.min(100, estimated / max * 100));
      const askPoint = $(".asking-point", track);
      const estPoint = $(".estimated-point", track);
      if (askPoint) askPoint.style.left = `${askPct}%`;
      if (estPoint) estPoint.style.left = `${estPct}%`;
      const fill = $(".track-fill", track);
      if (fill) { fill.style.left = `${Math.min(askPct, estPct)}%`; fill.style.width = `${Math.abs(estPct - askPct)}%`; }
    }
  }

  function renderFactors(explanation) {
    const render = (items, kind) => {
      if (!Array.isArray(items) || !items.length) return '<li class="factor-empty">No source-backed factors were returned.</li>';
      return items.slice(0, 6).map(factor => {
        const impact = validNumber(factor.impact);
        const positive = kind === "positive";
        const impactText = impact === null ? "—" : `${positive ? "+" : "−"}${Math.abs(impact).toFixed(1)}%`;
        return `<li>
          <span class="factor-icon"><svg class="icon"><use href="#i-${positive ? "building" : "building"}"></use></svg></span>
          <div><strong>${esc(factor.label || "Model feature")}</strong><small>${esc(factor.detail || "Contribution returned by the valuation explainer")}</small></div>
          <b class="${positive ? "green-text" : "red-text"} tnum">${impactText}</b>
        </li>`;
      }).join("");
    };
    const positive = $("#positive-factors");
    const negative = $("#negative-factors");
    if (positive) positive.innerHTML = render(explanation?.positive_factors, "positive");
    if (negative) negative.innerHTML = render(explanation?.negative_factors, "negative");
  }

  function renderComparables(properties) {
    const host = $("#comparables-list");
    if (!host) return;
    if (!Array.isArray(properties) || !properties.length) {
      host.innerHTML = '<p class="comparable-empty">No comparable listings were returned by the backend for this property.</p>';
      return;
    }
    host.innerHTML = properties.map((property, index) => {
      const title = property.title || property.property_name || property.society || "Property listing";
      const price = validNumber(property.price_inr);
      const predicted = validNumber(property.predicted_value_inr) ?? validNumber(property.final_estimated_value);
      const difference = price !== null && predicted !== null && predicted > 0 ? ((price - predicted) / predicted) * 100 : null;
      const below = difference !== null && difference < 0;
      const locality = [property.locality, property.city].filter(Boolean).join(", ") || "Location unavailable";
      const beds = validNumber(property.bedrooms);
      const area = validNumber(property.valuation_area_sqft);
      const label = difference === null ? "Estimate unavailable" : below ? "Below predicted value" : difference > 0 ? "Above predicted value" : "Near predicted value";
      return `<article class="tile comparable-card property-card reveal" style="--delay:${index * 70}ms">
        <div class="property-card__topline">
          <span class="panel-icon"><svg class="icon"><use href="#i-building"></use></svg></span>
          <span class="property-card__badge ${difference !== null && below ? "is-below" : "is-above"}">Value comparison</span>
        </div>
        <div class="property-card__identity">
          <div class="property-card__copy">
            <h3 class="property-card__name">${esc(title)}</h3>
            <p class="property-card__locality"><svg class="icon gold"><use href="#i-pin"></use></svg>${esc(locality)}</p>
          </div>
          <svg class="property-card__figure" aria-hidden="true"><use href="#i-card-architecture"></use></svg>
        </div>
        <div class="property-card__divider"><span></span></div>
        <div class="property-card__valuation">
          <div><span class="property-card__price-label">Asking price</span><strong class="property-card__price tnum">${esc(property.price_formatted || money(price))}</strong></div>
          <div class="property-card__valuation-status ${difference !== null && below ? "is-below" : "is-above"}">
            <svg class="icon"><use href="${difference !== null && below ? "#i-arrow-down" : "#i-arrow-up"}"></use></svg>
            <span class="status-dot"></span>
            <strong class="property-card__percentage tnum">${difference === null ? "—" : `${difference > 0 ? "+" : ""}${difference.toFixed(1)}%`}</strong>
            <span class="property-card__difference-label">${esc(label)}</span>
          </div>
        </div>
        <footer class="property-card__specifications">
          <span class="property-card__spec"><svg class="icon"><use href="#i-bed"></use></svg>${beds !== null ? `${beds} BHK` : "Bedrooms N/A"}</span>
          <span class="property-card__spec"><svg class="icon"><use href="#i-ruler"></use></svg>${area !== null ? `${Math.round(area).toLocaleString("en-IN")} sqft` : "Area N/A"}</span>
          <a class="property-card__open" href="/property/${encodeURIComponent(property.property_id)}" aria-label="View ${esc(title)}"><svg class="icon"><use href="#i-arrow-right"></use></svg></a>
        </footer>
      </article>`;
    }).join("");
    $$(".reveal", host).forEach(element => element.classList.add("inview"));
  }

  async function trackActivity(eventType, payload = {}) {
    try {
      const response = await fetch("/api/user/activity-event", {
        method: "POST", headers: { "Content-Type": "application/json" },
        credentials: "same-origin", keepalive: true, cache: "no-store",
        body: JSON.stringify({ event_type: eventType, page: location.pathname, ...payload })
      });
      return response.ok;
    } catch (_) { return false; }
  }

  async function saveProperty() {
    const button = $("#saveProperty");
    if (!button || !currentProperty) return;
    const saved = button.getAttribute("aria-pressed") === "true";
    button.disabled = true;
    try {
      const response = await fetch("/api/user/shortlist", {
        method: "POST", headers: { "Content-Type": "application/json" },
        credentials: "same-origin", cache: "no-store",
        body: JSON.stringify({ property_id: currentProperty.property_id || propertyId, action: saved ? "remove" : "add" })
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || "Could not update saved properties");
      const nextSaved = Boolean(data.shortlisted);
      button.setAttribute("aria-pressed", String(nextSaved));
      const label = $("span", button);
      if (label) label.textContent = nextSaved ? "Property Saved" : "Save Property";
      const icon = $("svg", button);
      if (icon) icon.style.fill = nextSaved ? "currentColor" : "none";
      trackActivity(nextSaved ? "shortlist_add" : "shortlist_remove", { property_id: currentProperty.property_id || propertyId });
      try { localStorage.setItem("rei_activity_version", String(Date.now())); } catch (_) { /* optional */ }
    } catch (error) {
      console.error("Could not save property:", error);
      const label = $("span", button);
      if (label) label.textContent = "Try again";
      setTimeout(() => { if (label) label.textContent = button.getAttribute("aria-pressed") === "true" ? "Property Saved" : "Save Property"; }, 1400);
    } finally { button.disabled = false; }
  }

  function initInteractions() {
    const save = $("#saveProperty");
    if (save) {
      fetch(`/api/user/shortlist?property_id=${encodeURIComponent(propertyId)}`, { credentials: "same-origin", cache: "no-store" })
        .then(response => response.json())
        .then(data => {
          if (data.success && data.shortlisted) {
            save.setAttribute("aria-pressed", "true");
            const label = $("span", save);
            if (label) label.textContent = "Property Saved";
            const icon = $("svg", save);
            if (icon) icon.style.fill = "currentColor";
          }
        }).catch(() => {});
      save.addEventListener("click", saveProperty);
    }

    const revealTargets = $$(".reveal, #priceTrack");
    if (reduceMotion.matches || !("IntersectionObserver" in window)) {
      revealTargets.forEach(element => element.classList.add("inview"));
    } else {
      const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add("inview");
            observer.unobserve(entry.target);
          }
        });
      }, { rootMargin: "-40px 0px", threshold: 0.05 });
      revealTargets.forEach(element => observer.observe(element));
    }

    const progressBar = $("#scrollProgressBar");
    let ticking = false;
    const updateProgress = () => {
      ticking = false;
      if (!progressBar) return;
      const max = root.scrollHeight - window.innerHeight;
      progressBar.style.width = `${max > 0 ? Math.min(1, window.scrollY / max) * 100 : 0}%`;
    };
    window.addEventListener("scroll", () => {
      if (!ticking) { ticking = true; window.requestAnimationFrame(updateProgress); }
    }, { passive: true });
    window.addEventListener("resize", updateProgress);
    updateProgress();
  }

  async function init() {
    if (!propertyId) { showError("No property ID was provided in the URL."); return; }
    try {
      const authResponse = await fetch("/api/auth/me", { credentials: "same-origin", cache: "no-store" });
      const auth = await authResponse.json();
      if (!auth.authenticated) { location.replace("/"); return; }

      const response = await fetch(`/api/property/${encodeURIComponent(propertyId)}`, { credentials: "same-origin", cache: "no-store" });
      const data = await response.json();
      if (!response.ok || !data.success || !data.property) throw new Error(data.error || "Property not found.");
      renderCore(data.property);
      initInteractions();
      trackActivity("property_view", { property_id: propertyId, metadata: { title: data.property.title, city: data.property.city, locality: data.property.locality } });
      fetch("/api/user/recently-viewed", {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", cache: "no-store",
        body: JSON.stringify({ property_id: propertyId })
      }).catch(() => {});

      const requests = [
        fetch(`/api/property/${encodeURIComponent(propertyId)}/intelligence`, { credentials: "same-origin", cache: "no-store" })
          .then(r => r.json()).then(result => {
            if (result.success) {
              renderValuation(result.valuation);
              renderComparables(result.comparable_properties || []);
            } else throw new Error(result.error || "Valuation unavailable");
          }).catch(error => {
            console.warn("Valuation data unavailable:", error);
            text("comparable-value", null, "Estimate unavailable");
            text("final-value", null, "Estimate unavailable");
            text("opportunity-pct", "—");
            text("opportunity-label", "Prediction could not be calculated");
            text("asking-price-analysis", "Valuation service could not calculate an estimate for this listing.");
            text("analysis-note", "No estimated value was returned. Check the listing features and valuation API logs.");
            renderComparables([]);
          }),
        fetch(`/api/property/${encodeURIComponent(propertyId)}/explanation`, { credentials: "same-origin", cache: "no-store" })
          .then(r => r.json()).then(result => {
            if (result.success) renderFactors(result.explanation);
            else renderFactors(null);
          }).catch(() => renderFactors(null))
      ];
      await Promise.allSettled(requests);
    } catch (error) {
      console.error("Property page could not load:", error);
      showError(error.message || "Unable to load property details.");
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();