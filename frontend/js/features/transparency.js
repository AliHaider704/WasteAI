// File: frontend/js/features/transparency.js
// F25: Details mode. Adds what the server returned to the "Why?" panel. Missing fields are left out.
import { onCard } from "./card-hook.js";
import { loadSourceNames, sourceName } from "../labels.js";
export const styles = "explain";

export default function init(ctx) {
  const { t, store } = ctx;
  const host = ctx.slot("header-tools");
  if (!host) return;
  let on = store.get("details-mode", false) === true;

  const b = document.createElement("button");
  b.type = "button";
  b.className = "icon-btn";
  b.innerHTML = '<svg class="icon" aria-hidden="true"><use href="assets/icons.svg#check"></use></svg><span class="visually-hidden"></span>';
  const label = b.querySelector("span");

  async function decorate(card, result) {
    if (!card) return;
    card.querySelectorAll(".f-details").forEach((n) => n.remove());
    const why = card.querySelector(".result__why");
    if (!on || !why) return;
    await loadSourceNames();
    if (!card.isConnected) return;
    const box = document.createElement("div");
    box.className = "f-details";
    const h = document.createElement("h3");
    h.textContent = t("f.transparency.title");
    box.append(h);
    const list = document.createElement("ul");
    list.className = "f-list f-list--plain";
    const srcs = result.sources || [];
    srcs.forEach((s) => {
      const parts = [t(s.ok ? "f.transparency.ok" : "f.transparency.failed")];
      if (s.top && s.top[0] && typeof s.top[0].score === "number") parts.push(t("f.transparency.score", { n: Math.round(s.top[0].score * 100) }));
      if (typeof s.elapsed_ms === "number") parts.push(t("f.transparency.ms", { n: s.elapsed_ms }));
      const li = document.createElement("li");
      const bdi = document.createElement("bdi");
      bdi.dir = "ltr";
      bdi.translate = false;
      bdi.textContent = sourceName(s.name) || s.name;
      li.append(bdi, `: ${parts.join(", ")}`);
      list.append(li);
    });
    box.append(list);
    if (srcs.length && srcs[0].elapsed_ms === null) {
      const p = document.createElement("p");
      p.textContent = t("f.transparency.cache");
      box.append(p);
    }
    if (typeof result.elapsed_ms === "number") {
      const p = document.createElement("p");
      p.textContent = t("f.transparency.total", { n: result.elapsed_ms });
      box.append(p);
    }
    why.append(box);
  }

  function paint() {
    b.setAttribute("aria-pressed", String(on));
    label.textContent = t("f.transparency.toggle");
  }
  b.addEventListener("click", async () => {
    on = !on;
    if (on) store.set("details-mode", true);
    else store.remove("details-mode");
    paint();
    const { store: api } = await import("../api.js");
    decorate(document.querySelector(".result__card"), api.result || {});
  });
  host.append(b);
  ctx.on("i18n:change", paint);
  paint();
  onCard(decorate);
}
