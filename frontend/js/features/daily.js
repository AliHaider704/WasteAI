// File: frontend/js/features/daily.js
// Daily question (M42, P10): one question per calendar day, same for everyone. No streak, no penalty (D-044).
import { slotEl, card } from "./personal-data.js";
import { pool, build, mount } from "./quiz-core.js";
import { loadNamespace } from "../i18n.js";
export const styles = "quiz";

export default async function init(ctx) {
  const host = slotEl(ctx, "home");
  if (!host) return;
  await loadNamespace("quiz"); // question wording and group names live there
  const c = card(host, "f-quiz f-daily");
  const day = Math.floor((Date.now() - new Date().getTimezoneOffset() * 6e4) / 864e5);

  async function show() {
    c.sum.textContent = ctx.t("f.daily.title");
    const q = build(await pool(ctx), day);
    c.box.hidden = !q;
    if (!q) return;
    const s = ctx.store.get("daily", null);
    if (s && s.day === day) {
      c.body.replaceChildren();
      const p = document.createElement("p");
      p.textContent = ctx.t("f.daily.done");
      c.body.append(p);
      return;
    }
    mount(ctx, c.body, q, (ok) => {
      ctx.store.set("daily", { day, ok });
      const p = document.createElement("p");
      p.textContent = ctx.t("f.daily.done");
      c.body.append(p);
    });
  }
  c.box.addEventListener("toggle", () => { if (c.box.open && !c.body.hasChildNodes()) show(); });
  document.addEventListener("i18n:change", () => { c.sum.textContent = ctx.t("f.daily.title"); if (c.box.open) show(); });
  c.sum.textContent = ctx.t("f.daily.title");
}
