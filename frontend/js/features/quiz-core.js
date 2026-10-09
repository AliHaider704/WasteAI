// File: frontend/js/features/quiz-core.js
// Shared question builder for the quick quiz and the daily question (M42). Hazard ids never appear.
import { catalog, plain, lang } from "./personal-data.js";
import { HAZARD } from "./play-data.js";

export const GROUPS = ["plastics", "paper", "glass", "metals", "organic", "other"];
const KEY = {
  plastics: "f.quiz.g.plastics",
  paper: "f.quiz.g.paper",
  glass: "f.quiz.g.glass",
  metals: "f.quiz.g.metals",
  organic: "f.quiz.g.organic",
  other: "f.quiz.g.other",
};
export const gKey = (g) => KEY[g];

/** All playable categories, sorted by id so a seed always gives the same question. */
export async function pool(ctx) {
  const cat = await catalog(lang(ctx));
  return [...cat.values()].filter((c) => c && !HAZARD.has(c.id) && GROUPS.includes(c.group)).sort((a, b) => (a.id < b.id ? -1 : 1));
}

/** Same seed, same question. Options are the right group plus three others, in a fixed order. */
export function build(list, seed) {
  if (!list.length) return null;
  const c = list[Math.abs(seed) % list.length];
  const at = GROUPS.indexOf(c.group);
  const wrong = [1, 2, 3].map((k) => GROUPS[(at + k * 2 + (Math.abs(seed) % 2)) % GROUPS.length]).filter((g, i, a) => g !== c.group && a.indexOf(g) === i);
  const opts = [c.group, ...wrong].slice(0, 4).sort((a, b) => GROUPS.indexOf(a) - GROUPS.indexOf(b));
  return { name: plain(c.name || c.id), answer: c.group, opts };
}

/** Renders one question into `body`. Calls done(correct) once after an answer. */
export function mount(ctx, body, q, done, nextLabel) {
  body.replaceChildren();
  const h = document.createElement("p");
  h.id = "q-" + Math.random().toString(36).slice(2, 8);
  h.textContent = ctx.t("f.quiz.ask").replace("{name}", q.name);
  const list = document.createElement("div");
  list.className = "f-quiz__opts";
  list.setAttribute("role", "group");
  list.setAttribute("aria-labelledby", h.id);
  const fb = document.createElement("p");
  fb.setAttribute("role", "status");
  const btns = q.opts.map((g) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn";
    b.textContent = ctx.t(gKey(g));
    b.addEventListener("click", () => {
      const ok = g === q.answer;
      btns.forEach((x) => (x.disabled = true));
      fb.textContent = ok ? ctx.t("f.quiz.right") : ctx.t("f.quiz.wrong").replace("{group}", ctx.t(gKey(q.answer)));
      if (nextLabel) {
        const n = document.createElement("button");
        n.type = "button";
        n.className = "btn";
        n.textContent = nextLabel;
        n.addEventListener("click", () => done(ok, true));
        body.append(n);
        n.focus();
      } else done(ok, false);
    });
    list.append(b);
    return b;
  });
  body.append(h, list, fb);
}
