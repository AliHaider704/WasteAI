// File: frontend/js/features/quiz.js
// Quick quiz (M42, F03): which group does an item belong to. No score kept, no ranking.
import { slotEl, card } from "./personal-data.js";
import { pool, build, mount } from "./quiz-core.js";
export const styles = "quiz";

export default function init(ctx) {
  const host = slotEl(ctx, "home");
  if (!host) return;
  const c = card(host, "f-quiz");
  let n = Math.floor(Date.now() / 864e5);

  async function show() {
    c.sum.textContent = ctx.t("f.quiz.title");
    const q = build(await pool(ctx), n);
    c.box.hidden = !q; // no categories loaded: nothing shown
    if (!q) return;
    mount(ctx, c.body, q, () => { n += 1; show(); c.body.querySelector("button")?.focus(); }, ctx.t("f.quiz.next"));
  }
  c.box.addEventListener("toggle", () => { if (c.box.open && !c.body.hasChildNodes()) show(); });
  document.addEventListener("i18n:change", () => { c.sum.textContent = ctx.t("f.quiz.title"); if (c.box.open) show(); });
  c.sum.textContent = ctx.t("f.quiz.title");
}
