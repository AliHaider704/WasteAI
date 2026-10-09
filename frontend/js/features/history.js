// File: frontend/js/features/history.js
import { catalog, plain, lang, slotEl, resultOf, when, confirmDialog, card } from "./personal-data.js";

const MAX = 10;

export default function init(ctx) {
  const host = slotEl(ctx, "browse");
  if (!host) return;
  const { sum, body } = card(host, "f-history");

  async function render() {
    const items = ctx.store.get("history", []);
    const cat = await catalog(lang(ctx));
    sum.textContent = ctx.t("f.history.title");
    body.replaceChildren();
    if (!items.length) {
      const p = document.createElement("p");
      p.textContent = ctx.t("f.history.empty");
      body.append(p);
      return;
    }
    const ol = document.createElement("ol");
    ol.className = "f-list";
    for (const it of items) {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = plain(cat.get(it.id)?.name) || ctx.t("f.history.unknown");
      const time = document.createElement("time");
      time.dateTime = new Date(it.ts).toISOString();
      time.textContent = when(ctx, it.ts);
      li.append(name, " ", time);
      ol.append(li);
    }
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "btn";
    clear.textContent = ctx.t("f.history.clear");
    clear.addEventListener("click", () =>
      confirmDialog(clear, ctx.t("f.history.confirm"), ctx.t("f.history.clear_yes"), ctx.t("f.history.cancel"), () => {
        ctx.store.set("history", []);
        render();
      }));
    body.append(ol, clear);
  }

  document.addEventListener("wasteai:result", (ev) => {
    const r = resultOf(ev);
    if (!r) return;
    const items = ctx.store.get("history", []);
    if (r.rid && items[0]?.rid === r.rid) return;
    ctx.store.set("history", [{ id: r.id, rid: r.rid, ts: Date.now() }, ...items].slice(0, MAX));
    render();
  });
  document.addEventListener("i18n:change", render);
  render();
}
