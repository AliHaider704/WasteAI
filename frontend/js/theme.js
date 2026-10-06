// PATH: waste-ai/frontend/js/theme.js
// Theme: follows prefers-color-scheme until the user toggles; the choice is then saved.
// tokens.css: no data-theme = follow the system; data-theme="light" or "dark" forces that theme.

const STORAGE_KEY = "wasteai.theme";
const root = document.documentElement;
const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function readSaved() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch (err) {
    return null;
  }
}

function save(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (err) {
    // storage may be blocked; the choice just won't persist
  }
}

/** The theme currently shown: the forced one, otherwise the system preference. */
export function effectiveTheme() {
  const forced = root.dataset.theme;
  if (forced === "light" || forced === "dark") return forced;
  return media && media.matches ? "dark" : "light";
}

// The button shows the icon of the theme it will switch to.
function syncButtons() {
  const dark = effectiveTheme() === "dark";
  document.querySelectorAll('[data-action="theme"]').forEach((btn) => {
    btn.setAttribute("aria-pressed", String(dark));
    const use = btn.querySelector("use");
    if (use) use.setAttribute("href", `assets/icons.svg#${dark ? "sun" : "moon"}`);
  });
}

export function setTheme(theme) {
  root.dataset.theme = theme;
  save(theme);
  syncButtons();
  document.dispatchEvent(new CustomEvent("theme:change", { detail: { theme } }));
}

export function toggleTheme() {
  setTheme(effectiveTheme() === "dark" ? "light" : "dark");
}

const saved = readSaved();
if (saved) root.dataset.theme = saved;
syncButtons();

document.addEventListener("click", (event) => {
  if (event.target.closest('[data-action="theme"]')) toggleTheme();
});
if (media && media.addEventListener) media.addEventListener("change", syncButtons);
