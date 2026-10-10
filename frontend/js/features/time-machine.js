// File: frontend/js/features/time-machine.js
// P05: time slider with a sourced range. The slider and the bar share one log scale, and the readout
// computes the item's condition at the chosen time. No range for a category, or a hazard category: nothing is shown.
import { getCategories } from "../api.js";
import { getLang } from "../i18n.js";
import { mount, put, heading, sourceLine } from "./knowledge.js";

export const styles = "lifecycle";

const MIN_Y = 1 / 12; // one month
const MAX_Y = 1000000;
const SPAN = Math.log10(MAX_Y) - Math.log10(MIN_Y);
const HAZARD = /^(battery|hazardous_chemical|medical|ewaste_)/;
const NS = "http://www.w3.org/2000/svg";
const TICKS = [MIN_Y, 1, 100, 1000, MAX_Y];
let icons = null;

function iconName(id) {
  icons = icons || getCategories(getLang()).then((d) => Object.fromEntries((d.categories || []).map((c) => [c.id, c.icon]))).catch(() => ({}));
  return icons.then((map) => map[id]);
}

// 0..100 position on the shared log scale, and its inverse.
const pos = (y) => Math.min(100, Math.max(0, ((Math.log10(Math.max(y, MIN_Y)) - Math.log10(MIN_Y)) / SPAN) * 100));
const yearsAt = (p) => 10 ** (Math.log10(MIN_Y) + (p / 100) * SPAN);

/** Round for display: whole months below a year, two significant figures above 100 years. */
function tidy(y) {
  if (y < 1) return Math.max(1, Math.round(y * 12)) / 12;
  if (y < 100) return Math.round(y);
  const mag = 10 ** (Math.floor(Math.log10(y)) - 1);
  return Math.round(y / mag) * mag;
}

/** Share of the item left after `t` years: whole before the range, a log-scaled decline inside it, gone after. */
function remaining(t, min, max) {
  if (t < min) return 1;
  if (t >= max) return 0;
  return 1 - (Math.log(t) - Math.log(min)) / (Math.log(max) - Math.log(min));
}

export default function init(ctx) {
  const { t } = ctx;
  const rules = () => new Intl.PluralRules(getLang());
  const word = (unit, n) => {
    const cat = rules().select(n);
    return t(`f.time-machine.unit_${unit}_${cat}`) || t(`f.time-machine.unit_${unit}_other`);
  };
  /** "3 years", "2 months"; Arabic dual stands alone ("سنتان"). */
  const fmt = (y) => {
    const months = y < 1 || Math.round(y * 12) < 12;
    const n = months ? Math.max(1, Math.round(y * 12)) : Math.round(y);
    const unit = word(months ? "month" : "year", n);
    return n === 2 && rules().select(2) === "two" ? unit : `${n.toLocaleString("en")} ${unit}`;
  };
  const tick = (y) => {
    if (y >= MAX_Y) return t("f.time-machine.tick_million");
    if (y < 1) return word("month", 1);
    if (y === 1) return word("year", 1);
    return y.toLocaleString("en");
  };

  mount(ctx, "time-machine", (cat, entries) => {
    const entry = entries.find((e) => e.id === cat.id);
    if (!entry || HAZARD.test(cat.id) || cat.hazard) return null;
    const { years_min: min, years_max: max } = entry;
    const wrap = document.createElement("div");
    wrap.className = "f-time";

    const icon = document.createElementNS(NS, "svg");
    icon.setAttribute("class", "icon f-time__icon");
    icon.setAttribute("aria-hidden", "true");
    icon.setAttribute("width", "32");
    icon.setAttribute("height", "32");
    iconName(cat.id).then((name) => {
      if (!name) return;
      const use = document.createElementNS(NS, "use");
      use.setAttribute("href", `assets/category-icons.svg#${name}`);
      icon.append(use);
    });

    const what = document.createElement("span");
    put(what, entry);
    const item = document.createElement("p");
    item.className = "f-time__item";
    item.append(icon, `${t("f.time-machine.item")} `, what);

    const label = document.createElement("label");
    label.htmlFor = "f-time-range";
    label.className = "f-time__label";
    label.textContent = t("f.time-machine.label");

    const slider = document.createElement("input");
    slider.type = "range";
    slider.id = "f-time-range";
    slider.className = "f-time__slider";
    slider.min = "0";
    slider.max = "100";
    slider.step = "0.5";
    slider.value = "0";
    slider.style.setProperty("--f-from", pos(min).toFixed(2));
    slider.style.setProperty("--f-to", Math.max(pos(max), pos(min) + 1.5).toFixed(2));

    const ticks = document.createElement("div");
    ticks.className = "f-time__ticks";
    ticks.setAttribute("aria-hidden", "true");
    TICKS.forEach((y) => {
      const s = document.createElement("span");
      s.style.setProperty("--f-at", pos(y).toFixed(2));
      s.textContent = tick(y);
      ticks.append(s);
    });

    const out = document.createElement("output");
    out.className = "f-time__out";
    out.htmlFor = slider.id;
    out.setAttribute("aria-live", "polite");
    const when = document.createElement("strong");
    const state = document.createElement("span");
    out.append(when, state);

    function sync() {
      const p = Number(slider.value);
      const years = p === 0 ? 0 : tidy(yearsAt(p));
      const left = years === 0 ? 1 : remaining(years, min, max);
      const text = years === 0 ? t("f.time-machine.today") : t("f.time-machine.after", { value: fmt(years) });
      const key = left >= 0.995 ? "intact" : left <= 0.005 ? "gone" : "partial";
      when.textContent = text;
      state.textContent = t(`f.time-machine.state_${key}`, { pct: Math.round(left * 100) });
      out.dataset.state = key;
      slider.setAttribute("aria-valuetext", `${text}: ${state.textContent}`);
      wrap.style.setProperty("--f-fade", String(Math.max(0.12, left)));
    }
    slider.addEventListener("input", sync);
    sync();

    const estimate = document.createElement("p");
    estimate.className = "f-time__estimate";
    const a = fmt(tidy(min));
    const b = fmt(tidy(max));
    estimate.textContent = a === b ? t("f.time-machine.one", { a }) : t("f.time-machine.range", { a, b });
    const vary = document.createElement("small");
    vary.className = "muted f-time__vary";
    vary.textContent = t("f.time-machine.vary");

    wrap.append(heading(t("f.time-machine.title")), item, label, slider, ticks, out, estimate, vary, sourceLine(ctx, "time-machine", entry.source));
    return wrap;
  });
}
