// File: frontend/js/errors.js
// Global error boundary: window "error", "unhandledrejection", and guard(view, fn).
// guard shows a localized "something went wrong, reload" panel instead of a blank view.

import { log } from "./log.js";

const t = (key, fallback) => (window.__i18n && window.__i18n[key]) || fallback;

function describe(err) {
  if (!err) return "unknown";
  if (typeof err === "string") return err;
  return `${err.name || "Error"}: ${err.message || ""}`;
}

function panel() {
  const box = document.createElement("div");
  box.className = "card error-boundary";
  box.setAttribute("role", "alert");
  const title = document.createElement("h2");
  title.className = "card__title";
  title.dataset.i18n = "error.boundary";
  title.textContent = t("error.boundary", "Something went wrong. Please reload the page.");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn btn--primary";
  btn.dataset.i18n = "error.reload";
  btn.textContent = t("error.reload", "Reload");
  btn.addEventListener("click", () => location.reload());
  box.append(title, btn);
  return box;
}

function showPanel(view) {
  const node = document.querySelector(`.view[data-view="${view}"]`);
  if (!node) return;
  node.hidden = false;
  node.replaceChildren(panel());
}

function fail(view, err) {
  log("view_error", { detail: `${view} ${describe(err)}` });
  showPanel(view);
}

/** Run fn for a view. Sync throws and rejected promises both end in the fallback panel. */
export function guard(view, fn) {
  try {
    const out = fn();
    if (out && typeof out.then === "function") out.catch((err) => fail(view, err));
    return out;
  } catch (err) {
    fail(view, err);
    return undefined;
  }
}

let installed = false;
export function installErrorBoundary() {
  if (installed) return;
  installed = true;
  window.addEventListener("error", (e) => {
    if (!e.error && !e.message) return; // resource load errors carry neither
    log("js_error", { detail: e.error ? describe(e.error) : e.message });
  });
  window.addEventListener("unhandledrejection", (e) => {
    log("unhandled_rejection", { detail: describe(e.reason) });
  });
}

installErrorBoundary();
