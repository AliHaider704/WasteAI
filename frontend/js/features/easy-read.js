// File: frontend/js/features/easy-read.js
// F29: header toggle, data-readable="on" on <html> (comfort.css). Saved through the store.
export const styles = "comfort";

export default function init(ctx) {
  const { t, store } = ctx;
  const host = ctx.slot("header-tools");
  if (!host) return;
  const root = document.documentElement;
  let on = store.get("easy-read", false) === true;

  const b = document.createElement("button");
  b.type = "button";
  b.className = "icon-btn";
  const NS = "http://www.w3.org/2000/svg";
  // Three reading lines: the mode is about line length and spacing.
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", "M5 7h14M5 12h14M5 17h9");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linecap", "round");
  svg.append(path);
  const label = document.createElement("span");
  label.className = "visually-hidden";
  b.append(svg, label);

  function apply() {
    if (on) root.dataset.readable = "on";
    else delete root.dataset.readable;
    b.setAttribute("aria-pressed", String(on));
    label.textContent = t("f.easy-read.toggle");
  }
  b.addEventListener("click", () => {
    on = !on;
    if (on) store.set("easy-read", true);
    else store.remove("easy-read");
    apply();
  });
  host.append(b);
  ctx.on("i18n:change", apply);
  apply();
}
