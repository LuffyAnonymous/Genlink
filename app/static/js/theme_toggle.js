const THEME_SUN_ICON = `<svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41"></path></svg>`;

const THEME_MOON_ICON = `<svg viewBox="0 0 24 24" aria-hidden="true" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"></path></svg>`;

function applyThemeToggleButtons(theme) {
  const isDark = theme === "dark";
  document.querySelectorAll(".theme-toggle").forEach((button) => {
    button.setAttribute("aria-pressed", String(isDark));
    const label = isDark ? "Switch to light mode" : "Switch to dark mode";
    button.setAttribute("aria-label", label);
    button.title = label;
    button.innerHTML = isDark ? THEME_SUN_ICON : THEME_MOON_ICON;
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  applyThemeToggleButtons(current);

  document.querySelectorAll(".theme-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("genlinklab-theme", next);
      } catch (err) {
        /* localStorage unavailable (private mode, etc.) - theme just won't persist */
      }
      applyThemeToggleButtons(next);
    });
  });
});
