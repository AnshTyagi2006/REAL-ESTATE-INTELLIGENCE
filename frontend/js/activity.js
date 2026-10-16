(function () {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => document.querySelectorAll(selector);
  const content = () => $("#activity-content");
  let data = null;
  let active = new URLSearchParams(location.search).get("tab") || "overview";
  const validTabs = new Set(["overview", "searches", "viewed", "shortlisted", "profile", "password"]);
  if (!validTabs.has(active)) active = "overview";

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function setStatus(message = "") {
    const el = $("#activity-status");
    if (el) el.textContent = message;
  }

  function money(value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return "Price unavailable";
    if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
    if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
    return `₹${Math.round(n).toLocaleString("en-IN")}`;
  }

  function dateLabel(value) {
    if (!value) return "Time unavailable";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat("en-IN", {
      day: "numeric", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit"
    }).format(date);
  }

  function applyTheme(theme) {
    const safe = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = safe;
    try { localStorage.setItem("theme", safe); } catch (_) {}
    const button = $("#activity-theme-toggle");
    if (button) {
      button.setAttribute("aria-pressed", String(safe === "dark"));
      button.setAttribute("aria-label", safe === "dark" ? "Switch to light mode" : "Switch to dark mode");
    }
  }

  function initTheme() {
    let saved = "light";
    try { saved = localStorage.getItem("theme") || "light"; } catch (_) {}
    applyTheme(saved);
    $("#activity-theme-toggle")?.addEventListener("click", () => {
      applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    });
  }

  async function requestJSON(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      cache: "no-store",
      ...options,
      headers: { ...(options.headers || {}) }
    });
    const result = await response.json().catch(() => ({}));
    if (response.status === 401) {
      location.replace("/");
      throw new Error("Your session has expired. Please sign in again.");
    }
    if (!response.ok || result.success === false) {
      throw new Error(result.error || `Request failed (${response.status})`);
    }
    return result;
  }

  async function load({ keepTab = true } = {}) {
    setStatus("Refreshing your activity…");
    try {
      const auth = await requestJSON("/api/auth/me");
      if (!auth.authenticated) {
        location.replace("/");
        return;
      }
      data = await requestJSON("/api/user/activity");
      render(keepTab ? active : "overview");
      setStatus(`Synced just now · ${data.user?.name ? `Signed in as ${data.user.name}` : "Your account activity"}`);
    } catch (error) {
      setStatus("We couldn't sync your activity. Please try again.");
      if (!data) {
        content().innerHTML = emptyState("Activity could not be loaded", error.message || "Check your connection and try again.", true);
      }
      console.error("Activity page load failed:", error);
    }
  }

  function tabs() {
    $$("[data-tab]").forEach((button) => {
      const selected = button.dataset.tab === active;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
      button.onclick = () => {
        active = button.dataset.tab;
        history.replaceState(null, "", `/activity?tab=${encodeURIComponent(active)}`);
        render();
      };
    });
  }

  function emptyState(title, message, showRetry = false) {
    return `<div class="activity-empty"><span class="activity-empty-mark" aria-hidden="true">⌂</span><h3>${esc(title)}</h3><p>${esc(message)}</p>${showRetry ? '<a href="#" data-retry>Try again ↻</a>' : '<a href="/search">Explore properties ↗</a>'}</div>`;
  }

  function propertyCards(list, type) {
    if (!Array.isArray(list) || !list.length) {
      const copy = type === "shortlisted"
        ? ["Your shortlist is ready to grow", "Save a property you like and it will be stored here for your next visit."]
        : ["No recently viewed properties", "Open a property listing and it will appear here automatically."];
      return emptyState(copy[0], copy[1]);
    }

    const stableHash = (value) => {
      let hash = 0;
      for (const ch of String(value || "")) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0;
      return Math.abs(hash);
    };
    const figure = (seed) => {
      const figures = [
        '<svg viewBox="0 0 88 72" fill="none" aria-hidden="true"><path d="M15 65V14l29-7 29 7v51M9 65h70M22 19l22-5 22 5M22 28h8m8-2h8m8 2h8M22 38h8m8-2h8m8 2h8M22 48h8m8-2h8m8 2h8M22 58h8m8-2h8m8 2h8M39 65V52h12v13"/></svg>',
        '<svg viewBox="0 0 88 72" fill="none" aria-hidden="true"><path d="m8 35 36-27 36 27M15 32v33h58V32M10 65h68M24 65V43h15v22m8-22h16v12H47zM48 56h15v9M19 37h50"/></svg>',
        '<svg viewBox="0 0 88 72" fill="none" aria-hidden="true"><path d="M9 65h70M15 65V28l18-13 18 13v37M51 65V36l13-9 12 9v29M19 33h8m-8 9h8m-8 9h8m11-18h7m-7 9h7m-7 9h7m10-9h7m-7 9h7m-7 9h7M30 65V54h8v11"/></svg>',
        '<svg viewBox="0 0 88 72" fill="none" aria-hidden="true"><path d="M12 65h64M18 19h52v46M13 19h62M23 26h12v12H23zm18 0h12v12H41zm18 0h5v12h-5zM23 43h12v12H23zm18 0h12v12H41zm18 0h5v12h-5zM32 65V58h24v7M27 19v-6h34v6M39 13V7h10v6"/></svg>'
      ];
      return figures[stableHash(seed) % figures.length];
    };
    const price = (property) => property.price_formatted || money(
      property.asking_price_inr ?? property.price_inr ?? property.price
    );
    const predicted = (property) => {
      const value = Number(property.predicted_value_inr ?? property.final_estimated_value ?? property.estimated_value_inr ?? property.predicted_valuation_inr);
      if (!Number.isFinite(value) || value <= 0) return null;
      return money(value);
    };
    const cardEdgeStyle = (seed) => {
      const hash = stableHash(seed);
      const shades = ["#F59A00", "#E9A414", "#F8C65A"];
      const pct = (offset) => `${12 + ((hash + offset * 17) % 72)}%`;
      const len = (offset) => `${18 + ((hash + offset * 11) % 28)}px`;
      const shade = (offset) => shades[(hash + offset) % shades.length];
      return `--edge-top-x:${pct(1)};--edge-top-length:${len(1)};--edge-top-gold:${shade(1)};--edge-right-y:${pct(2)};--edge-right-length:${len(2)};--edge-right-gold:${shade(2)};--edge-bottom-x:${pct(3)};--edge-bottom-length:${len(3)};--edge-bottom-gold:${shade(0)};--edge-left-y:${pct(4)};--edge-left-length:${len(4)};--edge-left-gold:${shade(2)};`;
    };

    return `<div class="activity-grid activity-property-grid">${list.map((property, index) => {
      const id = String(property.property_id || property.id || "");
      const seed = id || property.title || property.property_name || String(index);
      const title = property.title || property.property_name || property.name || "Property";
      const locationText = [property.locality, property.city].filter(Boolean).join(", ") || "Location unavailable";
      const timestamp = property.viewed_at || property.created_at || property.timestamp;
      const asking = Number(property.asking_price_inr ?? property.price_inr ?? property.price);
      const estimate = Number(property.predicted_value_inr ?? property.final_estimated_value ?? property.estimated_value_inr ?? property.predicted_valuation_inr);
      const hasDifference = Number.isFinite(asking) && asking > 0 && Number.isFinite(estimate) && estimate > 0;
      const diff = hasDifference ? Math.abs((estimate - asking) / asking * 100) : null;
      const below = hasDifference && asking < estimate;
      const above = hasDifference && asking > estimate;
      const status = below ? "is-below-value" : above ? "is-above-value" : hasDifference ? "is-at-value" : "is-unavailable";
      const directionLabel = below ? "below predicted value" : above ? "above predicted value" : hasDifference ? "at predicted value" : "Valuation unavailable";
      const typeLabel = property.property_type || property.type || "Property listing";
      const bedrooms = property.bedrooms ?? property.bhk;
      const area = property.valuation_area_sqft ?? property.area_sqft ?? property.area;
      const iconPath = '<path d="M8 41V17l16-9 16 9v24M4 41h40M15 22h6m6 0h6M15 30h6m6 0h6M20 41V34h8v7"/>';
      return `<article class="property-card activity-property-card" data-property-id="${esc(id)}" style="${cardEdgeStyle(seed)}">
        <div class="property-card__brand-row">
          <span class="property-card__logo" aria-hidden="true"><span class="activity-property-logo"><svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">${iconPath}</svg></span></span>
          <span class="property-card__badge ${below ? "property-card__badge--opportunity" : above ? "property-card__badge--overpriced" : "property-card__badge--fair"}">${esc(below ? "Value Opportunity" : above ? "Above Valuation" : hasDifference ? "Fair Value" : typeLabel)}</span>
          ${type === "shortlisted" ? `<button type="button" class="property-card__favorite is-active" data-remove-shortlist="${esc(id)}" aria-label="Remove ${esc(title)} from saved properties" title="Remove saved">♥</button>` : `<button type="button" class="property-card__favorite" data-save-property="${esc(id)}" aria-label="Save ${esc(title)}" title="Save property">♡</button>`}
        </div>
        <header class="property-card__header">
          <div class="property-card__identity"><h3 class="property-card__name" title="${esc(title)}"><a href="/property/${encodeURIComponent(id)}">${esc(title)}</a></h3><p class="property-card__locality">${esc(locationText)}</p></div>
          <span class="property-card__figure" aria-hidden="true">${figure(seed)}</span>
        </header>
        <div class="property-card__divider" aria-hidden="true"><span></span></div>
        <div class="property-card__valuation">
          <div class="property-card__price"><span class="property-card__price-label">Asking Price</span><strong class="property-card__asking-price">${esc(price(property))}</strong></div>
          <div class="property-card__price property-card__predicted-price"><span class="property-card__price-label">Predicted Price</span><strong class="property-card__asking-price">${esc(predicted(property) || "Unavailable")}</strong></div>
        </div>
        <div class="property-card__valuation-status"><strong class="property-card__percentage ${status}">${diff === null ? "—" : `${below ? "↑" : above ? "↓" : "•"} <span class="status-dot"></span>${diff.toFixed(1)}%`}</strong><span class="property-card__difference-label">${esc(hasDifference ? `${diff.toFixed(1)}% ${directionLabel}` : directionLabel)}</span></div>
        <footer class="property-card__specifications">
          <span class="property-card__spec">⌂ ${bedrooms != null && bedrooms !== "" ? `${esc(bedrooms)} BHK` : "Bedrooms N/A"}</span>
          <span class="property-card__spec">▧ ${area != null && area !== "" ? `${esc(Number(area).toLocaleString("en-IN"))} sqft` : "Area N/A"}</span>
          <a class="property-card__open" href="/property/${encodeURIComponent(id)}" aria-label="View ${esc(title)}">→</a>
        </footer>
        <div class="activity-property-card__meta">${esc(type === "shortlisted" ? "Saved property" : "Recently viewed")}${timestamp ? ` · ${esc(dateLabel(timestamp))}` : ""}</div>
      </article>`;
    }).join("")}</div>`;
  }

  function searchList(list, limit = 20) {
    if (!Array.isArray(list) || !list.length) {
      return emptyState("No saved searches yet", "Your searches will appear here after you search by city, locality, or property filters.");
    }
    return `<div class="activity-list">${list.slice(0, limit).map((item) => {
      const filters = item.filters || {};
      const details = [filters.city, filters.locality, filters.bedrooms ? `${filters.bedrooms} BHK` : "", filters.property_type].filter(Boolean).join(" · ");
      return `<article class="activity-list-item"><div class="activity-list-main"><strong>${esc(item.query || item.search_query || "Property search")}</strong><small>${esc(details || "Search history")}</small></div><time>${esc(dateLabel(item.created_at))}</time></article>`;
    }).join("")}</div>`;
  }

  function overview() {
    const stats = data.stats || {};
    const searches = data.searches || [];
    const viewed = data.viewed || [];
    const shortlisted = data.shortlisted || [];
    return `<div class="activity-overview-grid">
      <article class="activity-stat"><span class="activity-stat-label">Searches</span><strong>${Number(stats.total_searches || 0)}</strong><p>Recent saved search actions</p></article>
      <article class="activity-stat"><span class="activity-stat-label">Viewed</span><strong>${Number(stats.total_viewed || 0)}</strong><p>Properties you recently explored</p></article>
      <article class="activity-stat"><span class="activity-stat-label">Shortlisted</span><strong>${Number(stats.total_shortlisted || 0)}</strong><p>Properties saved for later</p></article>
    </div>
    <div class="activity-subgrid">
      <section class="activity-panel"><h3>Recent searches</h3><p>Your latest market and locality searches.</p>${searches.length ? `<div class="activity-mini-list">${searches.slice(0, 4).map((x) => `<div class="activity-mini-item"><strong>${esc(x.query || x.search_query || "Property search")}</strong><time>${esc(dateLabel(x.created_at))}</time></div>`).join("")}</div>` : '<div class="activity-mini-list"><div class="activity-mini-item"><strong>No searches yet</strong><a href="/search">Start exploring ↗</a></div></div>'}<div class="activity-card-actions"><a href="/activity?tab=searches">View search history ↗</a></div></section>
      <section class="activity-panel"><h3>Recently viewed</h3><p>Pick up where you left off.</p>${viewed.length ? `<div class="activity-mini-list">${viewed.slice(0, 4).map((x) => `<div class="activity-mini-item"><strong>${esc(x.title || x.property_name || "Property")}</strong><time>${esc(dateLabel(x.viewed_at))}</time></div>`).join("")}</div>` : '<div class="activity-mini-list"><div class="activity-mini-item"><strong>No viewed properties yet</strong><a href="/search">Find a property ↗</a></div></div>'}<div class="activity-card-actions"><a href="/activity?tab=viewed">View history ↗</a><a href="/activity?tab=shortlisted">Shortlist (${shortlisted.length})</a></div></section>
    </div>`;
  }

  function profileForm() {
    const user = data.user || {};
    return `<div class="profile-layout"><aside class="profile-intro"><div class="profile-avatar-large">${esc((user.name || "U").trim().charAt(0).toUpperCase())}</div><h2>Account details</h2><p>Keep your account information current. Your property searches, views and saved listings remain attached to your account.</p><p><strong>${esc(user.email || "")}</strong></p></aside><form id="profile-form" class="profile-form"><h3>Modify profile</h3><label for="profile-name">Full name<input id="profile-name" name="name" autocomplete="name" value="${esc(user.name || "")}" required maxlength="100"></label><label for="profile-email">Email address<input id="profile-email" name="email" type="email" autocomplete="email" value="${esc(user.email || "")}" required maxlength="254"></label><button type="submit">Save changes ↗</button><div id="profile-msg" class="activity-form-message" role="status"></div></form></div>`;
  }

  function passwordForm() {
    return `<div class="profile-layout"><aside class="profile-intro"><div class="profile-avatar-large">⌑</div><h2>Security settings</h2><p>Change your password securely. Your current password is required before the new password can be saved.</p><p>Use at least 6 characters.</p></aside><form id="password-form" class="profile-form"><h3>Change password</h3><label for="current-password">Current password<input id="current-password" name="current_password" type="password" autocomplete="current-password" required></label><label for="new-password">New password<input id="new-password" name="new_password" type="password" autocomplete="new-password" minlength="6" required></label><label for="confirm-password">Confirm new password<input id="confirm-password" name="confirm_password" type="password" autocomplete="new-password" minlength="6" required></label><button type="submit">Update password ↗</button><div id="password-msg" class="activity-form-message" role="status"></div></form></div>`;
  }

  function render(tab = active) {
    if (!data) return;
    active = tab;
    tabs();
    const c = content();
    if (active === "overview") c.innerHTML = overview();
    else if (active === "searches") c.innerHTML = `<div class="activity-section-head"><div><h2>Recent searches</h2><p>Your latest search queries and filters, saved to this account.</p></div><a class="activity-explore" href="/search">New search ↗</a></div>${searchList(data.searches || [])}`;
    else if (active === "viewed") c.innerHTML = `<div class="activity-section-head"><div><h2>Recently viewed</h2><p>Listings you opened while signed in to this account.</p></div><a class="activity-explore" href="/search">Explore homes ↗</a></div>${propertyCards(data.viewed || [], "viewed")}`;
    else if (active === "shortlisted") c.innerHTML = `<div class="activity-section-head"><div><h2>Your shortlist</h2><p>Saved properties stay here until you remove them.</p></div><a class="activity-explore" href="/search">Find properties ↗</a></div>${propertyCards(data.shortlisted || [], "shortlisted")}`;
    else if (active === "profile") c.innerHTML = profileForm();
    else if (active === "password") c.innerHTML = passwordForm();
    bindActions();
  }

  function showMessage(selector, message, type = "") {
    const el = $(selector);
    if (!el) return;
    el.textContent = message;
    el.className = `activity-form-message ${type}`.trim();
  }

  function bindActions() {
    $("[data-retry]")?.addEventListener("click", (event) => { event.preventDefault(); load(); });
    $$('[data-remove-shortlist]').forEach((button) => button.addEventListener("click", async () => {
      const id = button.dataset.removeShortlist;
      button.disabled = true;
      try {
        await requestJSON("/api/user/shortlist", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ property_id: id }) });
        await load();
        active = "shortlisted";
        history.replaceState(null, "", "/activity?tab=shortlisted");
        render("shortlisted");
        setStatus("Property removed from your shortlist.");
        try { localStorage.setItem("rei_activity_version", String(Date.now())); } catch (_) {}
      } catch (error) {
        button.disabled = false;
        setStatus(error.message || "Unable to remove property.");
      }
    }));
    $$('[data-save-property]').forEach((button) => button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await requestJSON("/api/user/shortlist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ property_id: button.dataset.saveProperty, action: "add" }) });
        await load();
        setStatus("Property saved to your shortlist.");
        try { localStorage.setItem("rei_activity_version", String(Date.now())); } catch (_) {}
      } catch (error) {
        button.disabled = false;
        setStatus(error.message || "Unable to save property.");
      }
    }));

    $("#profile-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.currentTarget.querySelector("button[type=submit]");
      button.disabled = true;
      showMessage("#profile-msg", "Saving profile…");
      const payload = Object.fromEntries(new FormData(event.currentTarget));
      try {
        const result = await requestJSON("/api/user/profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        data.user = { ...data.user, ...result.user };
        showMessage("#profile-msg", "Profile updated successfully.", "success");
        setStatus("Your profile was saved.");
      } catch (error) {
        showMessage("#profile-msg", error.message || "Unable to update profile.", "error");
      } finally { button.disabled = false; }
    });

    $("#password-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const payload = Object.fromEntries(new FormData(form));
      if (payload.new_password !== payload.confirm_password) {
        showMessage("#password-msg", "The new passwords do not match.", "error");
        return;
      }
      delete payload.confirm_password;
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      showMessage("#password-msg", "Updating password…");
      try {
        const result = await requestJSON("/api/user/change-password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        form.reset();
        showMessage("#password-msg", result.message || "Password updated successfully.", "success");
        setStatus("Your password was changed.");
      } catch (error) {
        showMessage("#password-msg", error.message || "Unable to change password.", "error");
      } finally { button.disabled = false; }
    });
  }

  document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });
  window.addEventListener("focus", () => load());
  window.addEventListener("storage", (event) => { if (event.key === "rei_activity_version") load(); });
  document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", () => { initTheme(); load(); })
    : (initTheme(), load());
})();
