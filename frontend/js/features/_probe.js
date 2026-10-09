// File: frontend/js/features/_probe.js
// Dev probe (M30). Removed in M48. Proves lazy loading and namespaces.
export default function init(ctx) {
  const el = document.createElement("p");
  el.className = "muted";
  el.textContent = ctx.t("f._probe.hello");
  const host = ctx.slot("home");
  if (host) host.append(el);
  ctx.on("i18n:change", () => { el.textContent = ctx.t("f._probe.hello"); });
}
