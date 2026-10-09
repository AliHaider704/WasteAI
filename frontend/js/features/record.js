// File: frontend/js/features/record.js
import { catalog, plain, lang, slotEl, resultOf, card, confirmDialog } from "./personal-data.js";
import { HAZARD, noteResult } from "./play-data.js";

export default function init(ctx) {
  const host = slotEl(ctx, "home");
  if (!host) return;
  const c = card(host, "f-record");

  async function render() {
    const d = ctx.store.get("record", null) || { cats: {} };
    const cat = await catalog(lang(ctx));
    c.sum.textContent = ctx.t("f.record.title");
    c.body.replaceChildren();
    const ids = Object.keys(d.cats).sort((a, b) => d.cats[a].first - d.cats[b].first);
    if (!ids.length) {
      const p = document.createElement("p");
      p.textContent = ctx.t("f.record.empty");
      c.body.append(p);
      return;
    }
    const all = [...cat.keys()].filter((id) => !HAZARD.has(id)).length;
    const count = document.createElement("p");
    count.textContent = ctx.t("f.record.count").replace("{n}", String(ids.length)).replace("{m}", String(all || ids.length));
    const ul = document.createElement("ul");
    ul.className = "f-stamps";
    for (const id of ids) {
      const li = document.createElement("li");
      const s = document.createElement("span");
      s.className = `bin bin--${cat.get(id)?.bin || "grey"} f-stamp`;
      s.textContent = plain(cat.get(id)?.name) || ctx.t("f.record.unknown");
      li.append(s);
      ul.append(li);
    }
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "btn";
    reset.textContent = ctx.t("f.record.reset");
    reset.addEventListener("click", () =>
      confirmDialog(reset, ctx.t("f.record.confirm"), ctx.t("f.record.yes"), ctx.t("f.record.no"), () => {
        ctx.store.remove("record");
        render();
      }));
    c.body.append(count, ul, reset);
  }

  document.addEventListener("wasteai:result", (ev) => {
    if (noteResult(ctx, resultOf(ev))) render();
  });
  document.addEventListener("i18n:change", render);
  render();
}
