// File: frontend/js/features/stats.js
import { catalog, plain, lang, slotEl, resultOf, confirmDialog, card } from "./personal-data.js";

export default function init(ctx) {
  const host = slotEl(ctx, "browse");
  if (!host) return;
  const { sum, body } = card(host, "f-stats");
  const read = () => ctx.store.get("stats", { total: 0, by: {}, last: "" });

  async function render() {
    const s = read();
    const cat = await catalog(lang(ctx));
    sum.textContent = ctx.t("f.stats.title");
    body.replaceChildren();
    if (!s.total) {
      const p = document.createElement("p");
      p.textContent = ctx.t("f.stats.empty");
      body.append(p);
      return;
    }
    const p = document.createElement("p");
    p.textContent = ctx.t("f.stats.total").replace("{n}", String(s.total));
    const ol = document.createElement("ol");
    ol.className = "f-list";
    Object.entries(s.by).sort((a, b) => b[1] - a[1]).slice(0, 3).forEach(([id, n]) => {
      const li = document.createElement("li");
      li.textContent = `${plain(cat.get(id)?.name) || ctx.t("f.stats.unknown")}: ${n}`;
      ol.append(li);
    });
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "btn";
    reset.textContent = ctx.t("f.stats.reset");
    reset.addEventListener("click", () =>
      confirmDialog(reset, ctx.t("f.stats.confirm"), ctx.t("f.stats.reset_yes"), ctx.t("f.stats.cancel"), () => {
        ctx.store.set("stats", { total: 0, by: {}, last: "" });
        render();
      }));
    body.append(p, ol, reset);
  }

  document.addEventListener("wasteai:result", (ev) => {
    const r = resultOf(ev);
    const s = read();
    if (!r || (r.rid && s.last === r.rid)) return;
    s.total += 1;
    s.by[r.id] = (s.by[r.id] || 0) + 1;
    s.last = r.rid;
    ctx.store.set("stats", s);
    render();
  });
  document.addEventListener("i18n:change", render);
  render();
}
