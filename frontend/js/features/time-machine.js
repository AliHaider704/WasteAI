// File: frontend/js/features/time-machine.js
// P05: time slider with a sourced range. No range for a category, or a hazard category: nothing is shown.
import { getCategories } from "../api.js";
import { getLang } from "../i18n.js";
import { mount, put, heading, sourceLine } from "./knowledge.js";

export const styles = "lifecycle";

const STEPS = [0, 1 / 12, 1, 10, 100, 1000, 1000000];
const HAZARD = /^(battery|hazardous_chemical|medical|ewaste_)/;
const NS = "http://www.w3.org/2000/svg";
let icons = null;

function iconName(id) {
  icons = icons || getCategories(getLang()).then((d) => Object.fromEntries((d.categories || []).map((c) => [c.id, c.icon]))).catch(() => ({}));
  return icons.then((map) => map[id]);
}

const num = (n) => (n >= 10 ? Math.round(n) : Math.round(n * 10) / 10).toLocaleString("en");
const pos = (y) => Math.min(100, Math.max(0, ((Math.log10(Math.max(y, 1e-3)) + 1.08) / 7.08) * 100));

function fade(t, min, max) {
  if (t < min) return 1;
  if (t >= max) return 0;
  return 1 - (Math.log(t) - Math.log(min)) / (Math.log(max) - Math.log(min));
}

export default function init(ctx) {
  const { t } = ctx;
  const unit = (y, n) => t(`f.time-machine.unit_${y < 1 ? "month" : "year"}${n === 1 ? "" : "s"}`);
  const fmt = (y) => {
    const n = y < 1 ? Math.round(y * 12) : Math.round(y);
    return `${n.toLocaleString("en")} ${unit(y, n)}`;
  };

  mount(ctx, "time-machine", (cat, entries) => {
    const entry = entries.find((e) => e.id === cat.id);
    if (!entry || HAZARD.test(cat.id) || cat.hazard) return null;
    const { years_min: min, years_max: max } = entry;
    const wrap = document.createElement("div");

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

    const scale = document.createElement("div");
    scale.className = "f-time__scale";
    scale.setAttribute("aria-hidden", "true");
    scale.style.setProperty("--f-from", String(pos(min)));
    scale.style.setProperty("--f-to", String(pos(max)));
    const mark = document.createElement("span");
    mark.className = "f-time__range";
    scale.append(mark);
    const ends = document.createElement("div");
    ends.className = "f-time__ends";
    ends.setAttribute("aria-hidden", "true");
    ends.append(Object.assign(document.createElement("span"), { textContent: fmt(STEPS[1]) }), Object.assign(document.createElement("span"), { textContent: fmt(STEPS[6]) }));

    const label = document.createElement("label");
    label.htmlFor = "f-time-range";
    label.textContent = t("f.time-machine.label");
    const slider = document.createElement("input");
    slider.type = "range";
    slider.id = "f-time-range";
    slider.min = "0";
    slider.max = String(STEPS.length - 1);
    slider.step = "1";
    slider.value = "0";
    const out = document.createElement("output");
    out.className = "f-time__out";
    out.htmlFor = slider.id;

    function sync() {
      const years = STEPS[Number(slider.value)];
      const text = years === 0 ? t("f.time-machine.today") : fmt(years);
      out.textContent = text;
      slider.setAttribute("aria-valuetext", text);
      wrap.style.setProperty("--f-fade", String(years === 0 ? 1 : fade(years, min, max)));
    }
    slider.addEventListener("input", sync);
    sync();

    const mo = max < 1;
    const a = num(mo ? min * 12 : min);
    const b = num(mo ? max * 12 : max);
    const estimate = document.createElement("p");
    estimate.textContent = a === b ? t("f.time-machine.one", { a, unit: unit(max, Number(a)) }) : t("f.time-machine.range", { a, b, unit: unit(max, 2) });
    const item = document.createElement("small");
    item.className = "muted";
    const what = document.createElement("span");
    put(what, entry);
    item.append(`${t("f.time-machine.item")} `, what);
    const vary = document.createElement("small");
    vary.className = "muted";
    vary.textContent = t("f.time-machine.vary");

    const row = document.createElement("div");
    row.className = "f-time__row";
    row.append(icon, label, slider, out);
    wrap.append(heading(t("f.time-machine.title")), row, scale, ends, estimate, item, vary, sourceLine(ctx, "time-machine", entry.source));
    return wrap;
  });
}
