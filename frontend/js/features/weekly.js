// File: frontend/js/features/weekly.js
// One goal per week, set by the calendar week (no randomness). No streak, no penalty, no ranking (D-044).
import { catalog, lang, slotEl, resultOf, card } from "./personal-data.js";
import { HAZARD, weekInfo } from "./play-data.js";
export const styles = "weekly";

const GOAL = 3;
const GROUP_KEY = {
  plastics: "f.weekly.g.plastics",
  paper: "f.weekly.g.paper",
  glass: "f.weekly.g.glass",
  metals: "f.weekly.g.metals",
  organic: "f.weekly.g.organic",
  other: "f.weekly.g.other",
};

export default function init(ctx) {
  const host = slotEl(ctx, "home");
  if (!host) return;
  const c = card(host, "f-weekly");

  async function targetGroup() {
    const cat = await catalog(lang(ctx));
    const groups = [...new Set([...cat.values()].filter((x) => !HAZARD.has(x.id)).map((x) => x.group))].filter((g) => GROUP_KEY[g]).sort();
    return { cat, group: groups.length ? groups[weekInfo().index % groups.length] : null };
  }

  function state() {
    const w = weekInfo().key;
    const s = ctx.store.get("weekly", null);
    return s && s.week === w ? s : { week: w, n: 0, rids: [] };
  }

  async function render() {
    const { group } = await targetGroup();
    c.box.hidden = !group;
    if (!group) return;
    const s = state();
    c.sum.textContent = ctx.t("f.weekly.title");
    c.body.replaceChildren();
    const goal = document.createElement("p");
    goal.textContent = ctx.t("f.weekly.goal").replace("{n}", String(GOAL));
    const name = document.createElement("strong");
    name.textContent = ctx.t(GROUP_KEY[group]);
    const bar = document.createElement("progress");
    bar.max = GOAL;
    bar.value = Math.min(s.n, GOAL);
    bar.setAttribute("aria-label", ctx.t("f.weekly.label"));
    const note = document.createElement("p");
    note.textContent = s.n >= GOAL ? ctx.t("f.weekly.done") : ctx.t("f.weekly.progress").replace("{n}", String(s.n));
    c.body.append(goal, name, bar, note);
  }

  document.addEventListener("wasteai:result", async (ev) => {
    const r = resultOf(ev);
    if (!r || !r.rid || HAZARD.has(r.id)) return;
    const { cat, group } = await targetGroup();
    const s = state();
    if (group && cat.get(r.id)?.group === group && !s.rids.includes(r.rid)) {
      s.rids = [r.rid, ...s.rids].slice(0, 10);
      s.n += 1;
      ctx.store.set("weekly", s);
    }
    render();
  });
  document.addEventListener("i18n:change", render);
  render();
}
