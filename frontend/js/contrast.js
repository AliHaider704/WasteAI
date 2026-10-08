// File: frontend/js/contrast.js
// High-contrast option: data-contrast="high" on <html> (tokens.css). No saved choice follows prefers-contrast: more.

const STORAGE_KEY = "wasteai.contrast";
const root = document.documentElement;
const media = window.matchMedia ? window.matchMedia("(prefers-contrast: more)") : null;

function readSaved() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "high" || value === "off" ? value : null;
  } catch (err) {
    return null;
  }
}

function save(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch (err) {
    // storage may be blocked; the choice just won't persist
  }
}

export function isHighContrast() {
  return root.dataset.contrast === "high";
}

function apply(high) {
  if (high) root.dataset.contrast = "high";
  else delete root.dataset.contrast;
  document.querySelectorAll('[data-action="contrast"]').forEach((btn) => {
    btn.setAttribute("aria-pressed", String(high));
  });
}

export function toggleContrast() {
  const high = !isHighContrast();
  save(high ? "high" : "off");
  apply(high);
}

const saved = readSaved();
apply(saved ? saved === "high" : Boolean(media && media.matches));

document.addEventListener("click", (event) => {
  if (event.target.closest('[data-action="contrast"]')) toggleContrast();
});
if (media && media.addEventListener) {
  media.addEventListener("change", () => {
    if (!readSaved()) apply(media.matches);
  });
}
