// File: frontend/js/features/kids.js
// F30: header toggle, data-kids="on" on <html> (kids.css). Turns easy-read on while active; hazard warnings stay visible.
export const styles = true;

export default function init(ctx) {
  const { t, store } = ctx;
  const host = ctx.slot("header-tools");
  if (!host) return;
  const root = document.documentElement;
  let on = store.get("kids", false) === true;
  let hadReadable = false;

  const b = document.createElement("button");
  b.type = "button";
  b.className = "icon-btn";
  const NS = "http://www.w3.org/2000/svg";
  // An open book: the mode is about simple reading and learning.
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", "M4 5h6a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4zM20 5h-6a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2h6z");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  const label = document.createElement("span");
  label.className = "visually-hidden";
  b.append(svg, label);

  function apply() {
    if (on) {
      hadReadable = root.dataset.readable === "on";
      root.dataset.kids = "on";
      root.dataset.readable = "on";
    } else {
      delete root.dataset.kids;
      if (!hadReadable) delete root.dataset.readable;
    }
    b.setAttribute("aria-pressed", String(on));
    label.textContent = t("f.kids.toggle");
  }
  b.addEventListener("click", () => {
    on = !on;
    if (on) store.set("kids", true);
    else store.remove("kids");
    apply();
  });
  host.append(b);
  ctx.on("i18n:change", apply);
  apply();
}
