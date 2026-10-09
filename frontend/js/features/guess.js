// File: frontend/js/features/guess.js
// Guess before the result (M43, P07). Optional, never scored, never shown for hazard results.
import { catalog, lang, slotEl, resultOf } from "./personal-data.js";
import { GROUPS, gKey } from "./quiz-core.js";
import { HAZARD } from "./play-data.js";
import { loadNamespace } from "../i18n.js";
export const styles = "guess";

export default async function init(ctx) {
  await loadNamespace("quiz"); // group names
  let guess = null;
  let panel = null;

  function clear() { guess = null; panel?.remove(); panel = null; }

  function open() {
    const host = slotEl(ctx, "capture");
    if (!host || panel) return;
    panel = document.createElement("fieldset");
    panel.className = "f-guess";
    const lg = document.createElement("legend");
    lg.textContent = ctx.t("f.guess.ask");
    panel.append(lg);
    GROUPS.forEach((g) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn";
      b.setAttribute("aria-pressed", "false");
      b.textContent = ctx.t(gKey(g));
      b.addEventListener("click", () => {
        guess = guess === g ? null : g;
        panel.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b && guess === g)));
      });
      panel.append(b);
    });
    host.append(panel);
  }

  document.addEventListener("wasteai:capture", (ev) => {
    const s = ev.detail && ev.detail.stage;
    if (s === "ready") open();
    if (s === "cancel") clear();
  });

  document.addEventListener("wasteai:result", async (ev) => {
    const mine = guess;
    clear();
    const r = resultOf(ev);
    const out = slotEl(ctx, "result");
    out?.querySelector(".f-guess-result")?.remove();
    if (!mine || !r || HAZARD.has(r.id) || !out) return;
    const cat = (await catalog(lang(ctx))).get(r.id);
    if (!cat || !GROUPS.includes(cat.group)) return;
    const p = document.createElement("p");
    p.className = "f-guess-result";
    p.setAttribute("role", "status");
    p.textContent = ctx.t(mine === cat.group ? "f.guess.same" : "f.guess.diff").replace("{guess}", ctx.t(gKey(mine))).replace("{group}", ctx.t(gKey(cat.group)));
    out.append(p);
  });
}
