(function () {
  "use strict";

  async function init() {
    const actions = document.querySelector(
      ".header-actions, .nav-actions, .activity-header-actions"
    );
    if (!actions) return;

    try {
      const response = await fetch("/api/auth/me", {
        credentials: "same-origin",
        cache: "no-store"
      });
      const data = await response.json();
      if (!data.authenticated || !data.user) return;

      document.querySelectorAll(".rei-account").forEach((node) => node.remove());
      // Replace page-specific static initials with the same functional account menu
      // used by the search page. Do not leave a dead duplicate avatar behind.
      actions.querySelectorAll(".avatar, .activity-avatar").forEach((node) => node.remove());
      const wrap = document.createElement("div");
      wrap.className = "rei-account";
      const initial = (data.user.name || "A").trim().charAt(0).toUpperCase() || "A";
      wrap.innerHTML = `<button class="rei-profile-trigger" type="button" aria-label="Open profile menu" aria-expanded="false" aria-controls="reiProfileMenu">${escapeHTML(initial)}</button><div class="rei-profile-menu" id="reiProfileMenu" role="menu"><div class="rei-profile-header"><div class="rei-profile-name">${escapeHTML(data.user.name || "User")}</div><div class="rei-profile-email">${escapeHTML(data.user.email || "")}</div></div><a class="rei-profile-link" role="menuitem" href="/activity">Profile</a><a class="rei-profile-link" role="menuitem" href="/activity">Saved Properties</a><a class="rei-profile-link" role="menuitem" href="/activity?tab=searches">Recently Searched</a><a class="rei-profile-link" role="menuitem" href="/activity?tab=viewed">Recently Viewed</a><div class="rei-profile-divider"></div><a class="rei-profile-link" role="menuitem" href="/activity?tab=profile">Settings</a><button class="rei-profile-action rei-profile-logout" type="button" role="menuitem">Sign Out</button></div>`;
      actions.appendChild(wrap);

      const trigger = wrap.querySelector(".rei-profile-trigger");
      const menu = wrap.querySelector(".rei-profile-menu");
      const closeMenu = () => {
        menu.classList.remove("open");
        trigger.setAttribute("aria-expanded", "false");
      };

      trigger.addEventListener("click", (event) => {
        event.stopPropagation();
        const isOpen = menu.classList.toggle("open");
        trigger.setAttribute("aria-expanded", String(isOpen));
      });
      menu.addEventListener("click", (event) => event.stopPropagation());
      document.addEventListener("click", closeMenu);
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          closeMenu();
          trigger.focus();
        }
      });
      wrap.querySelectorAll(".rei-profile-link").forEach((link) => link.addEventListener("click", closeMenu));
      wrap.querySelector(".rei-profile-logout").addEventListener("click", async () => {
        closeMenu();
        try {
          await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
        } finally {
          location.replace("/");
        }
      });
    } catch (error) {
      console.debug("Account menu unavailable", error);
    }
  }

  function escapeHTML(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", init)
    : init();
})();
