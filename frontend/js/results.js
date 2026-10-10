// File: frontend/js/results.js
// Result UI: ok / uncertain / hazard states, "Why?" panel, feedback, aria-live announcement.
// Needs in app.js: import "./results.js";   and in index.html: <link rel="stylesheet" href="css/results.css">
// All text is looked up by key via window.__i18n (M5); the key itself is shown until then.

import { store, getCategories, sendFeedback, ApiError } from "./api.js";
import { loadLabels, renderTags, loadSourceNames, sourceName } from "./labels.js";
import { getLang, plain, setRich, t } from "./i18n.js";

const HIGH = 0.8;   // confidence in words: >= HIGH -> high, >= MEDIUM -> medium, else not sure
const MEDIUM = 0.65;
const SVG_NS = "http://www.w3.org/2000/svg";
const TIP_KEYS = ["result.tip.background", "result.tip.single", "result.tip.light"];

const root = document.getElementById("result-root");
const live = document.createElement("p"); // single polite announcement instead of re-reading the whole card
live.className = "visually-hidden";
live.setAttribute("role", "status");
let catalog = [];
let catalogLang = null;
let whyOpen = false; // keeps the "Why?" panel state across re-renders

if (root) {
  root.before(live);
}

// ---------- small DOM helpers ----------

function el(tag, className, key) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (key) {
    node.dataset.i18n = key;
    node.textContent = t(key);
  }
  return node;
}

function txt(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  setRich(node, text);
  return node;
}

function setKey(node, key) {
  node.dataset.i18n = key;
  node.textContent = t(key);
}

function button(key, className) {
  const b = el("button", className, key);
  b.type = "button";
  return b;
}

function binChip(bin) {
  const chip = el("button", `bin bin--${bin}`); // opens the bin dialog (bininfo.js), like Home and Browse
  chip.type = "button";
  chip.dataset.binInfo = bin;
  chip.setAttribute("aria-haspopup", "dialog");
  chip.dataset.i18n = `bin.${bin}`;
  chip.textContent = t(`bin.${bin}`);
  return chip;
}

function iconNode(name) {
  if (!name) return null;
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "icon result__icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", "32");
  svg.setAttribute("height", "32");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `assets/category-icons.svg#${name}`);
  svg.append(use);
  return svg;
}

function confidenceLevel(value) {
  if (value >= HIGH) return "high";
  if (value >= MEDIUM) return "medium";
  return "low";
}

async function loadCatalog() {
  const lang = document.documentElement.lang || "en";
  if (catalogLang === lang && catalog.length) return catalog;
  try {
    const data = await getCategories(lang);
    catalog = Array.isArray(data.categories) ? data.categories : [];
    catalogLang = lang;
  } catch (err) {
    if (catalogLang !== lang) catalog = []; // never show a list in the wrong language
  }
  return catalog;
}

// ---------- content blocks ----------

function guidanceBlocks(g) {
  const frag = document.createDocumentFragment();
  if (!g) return frag;
  if (g.summary) frag.append(txt("p", "result__summary", g.summary));
  if (g.steps && g.steps.length) {
    frag.append(el("h3", "result__sub", "result.steps"));
    const ol = el("ol", "result__steps");
    g.steps.forEach((step) => ol.append(txt("li", null, step)));
    frag.append(ol);
  }
  return frag;
}

// Hazard results always show warnings, even at low confidence or with an empty list.
function warningsBlock(list, hazard) {
  const items = list || [];
  if (!items.length && !hazard) return null;
  const box = el("div", "result__warnings");
  box.setAttribute("role", "note");
  box.append(el("h3", "result__sub", "result.warnings"));
  const ul = el("ul", "result__list");
  if (items.length) items.forEach((w) => ul.append(txt("li", null, w)));
  else ul.append(el("li", null, "result.hazard_generic"));
  box.append(ul);
  return box;
}

function whyPanel(result) {
  const details = el("details", "result__why");
  details.open = whyOpen;
  details.addEventListener("toggle", () => { whyOpen = details.open; });
  details.append(el("summary", null, "result.why"));
  const dl = el("dl", "result__facts");
  dl.append(el("dt", null, "result.agreement"), el("dd", null, `agreement.${result.agreement}`));
  details.append(dl);
  const list = el("ul", "result__list");
  (result.sources || []).forEach((src) => {
    const li = el("li");
    const real = sourceName(src.name);
    const head = el("strong", null, real ? "" : `source.${src.name}`);
    if (real) setRich(head, `<bdi dir="ltr">${real}</bdi>`);
    li.append(head, " ");
    if (real) li.append(el("span", "muted", `source.${src.name}`), " ");
    if (src.ok && src.top && src.top.length) {
      const tags = el("span", "result__labels");
      tags.append(renderTags(src.top, getLang(), (id) => plain((catalog.find((c) => c.id === id) || {}).name || "")));
      li.append(tags);
    } else {
      li.append(el("span", "muted", "result.source_failed"));
    }
    list.append(li);
  });
  details.append(list);
  const ev = result.evidence;
  if (ev && typeof ev.cloud_share === "number") {
    details.append(el("p", "muted", ev.cloud_share >= 0.5 ? "why.strong_cloud" : "why.weak_cloud"));
  }
  return details;
}

function feedbackBlock(result, selectedId) {
  const wrap = el("div", "result__feedback");
  const open = button("result.wrong", "btn");
  open.setAttribute("aria-expanded", "false");
  const form = el("div", "result__form");
  form.hidden = true;
  const label = el("label", "result__label", "result.correct_label");
  const select = document.createElement("select");
  select.className = "input";
  select.id = "feedback-select";
  select.name = "correct_category_id";
  label.htmlFor = select.id;
  const send = button("result.send", "btn btn--primary");
  const retry = button("browse.retry", "btn");
  retry.hidden = true;
  const msg = el("p", "muted");
  msg.setAttribute("role", "status");
  let pending = false;

  async function fill() {
    await loadCatalog();
    select.replaceChildren();
    if (!catalog.length) {
      setKey(msg, "feedback.catalog_error");
      retry.hidden = false;
      send.disabled = true;
      return;
    }
    msg.textContent = "";
    msg.removeAttribute("data-i18n");
    retry.hidden = true;
    send.disabled = pending;
    if (!selectedId) {
      const ph = document.createElement("option");
      ph.value = "";
      ph.dataset.i18n = "feedback.choose";
      ph.textContent = t("feedback.choose");
      ph.selected = true;
      select.append(ph);
    }
    const groups = new Map();
    catalog.forEach((c) => {
      if (!groups.has(c.group)) {
        const og = document.createElement("optgroup");
        og.label = t(`group.${c.group}`);
        groups.set(c.group, og);
        select.append(og);
      }
      const option = document.createElement("option");
      option.value = c.id;
      option.textContent = plain(c.name);
      option.selected = c.id === selectedId;
      groups.get(c.group).append(option);
    });
  }

  open.addEventListener("click", () => {
    form.hidden = !form.hidden;
    open.setAttribute("aria-expanded", String(!form.hidden));
    if (!form.hidden) select.focus();
  });
  retry.addEventListener("click", fill);
  send.addEventListener("click", async () => {
    if (pending || !select.value) return;
    pending = true;
    send.disabled = true;
    try {
      await sendFeedback(result.request_id, select.value);
      setKey(msg, "feedback.thanks");
    } catch (err) {
      pending = false;
      send.disabled = false;
      setKey(msg, err instanceof ApiError ? err.i18nKey : "error.unknown");
    }
  });
  form.append(label, select, send, retry, msg);
  wrap.append(open, form);
  fill();
  return wrap;
}

function photoColumn() {
  const col = el("div", "result__media");
  if (store.photoUrl) {
    const img = document.createElement("img");
    img.className = "result__photo";
    img.src = store.photoUrl;
    img.alt = t("result.photo_alt");
    img.width = 4; // intrinsic ratio hint; CSS sets aspect-ratio (no layout shift)
    img.height = 3;
    col.append(img);
  }
  return col;
}

// ---------- states ----------

function buildOk(result) {
  const cat = result.category;
  const meta = catalog.find((c) => c.id === cat.id);
  const g = meta ? { ...result.guidance, summary: meta.summary, steps: meta.steps, warnings: meta.warnings } : result.guidance;
  const card = el("article", "result__card");
  if (g && g.bin) {
    const stamp = el("div", "result__meta result__stamp");
    stamp.append(binChip(g.bin));
    card.append(stamp);
  }
  const head = el("div", "result__head");
  const icon = iconNode(meta && meta.icon);
  if (icon) head.append(icon);
  head.append(txt("h2", "result__name", meta ? meta.name : cat.name));
  const level = confidenceLevel(cat.confidence);
  const conf = el("span", "result__confidence", `result.confidence.${level}`);
  conf.dataset.level = level;
  head.append(conf);
  card.append(head);
  const warn = warningsBlock(g && g.warnings, result.hazard);
  if (warn && result.hazard) card.append(warn); // hazard: warnings come first (values filter 7)
  card.append(guidanceBlocks(g));
  if (warn && !result.hazard) card.append(warn);
  card.append(whyPanel(result));
  card.append(feedbackBlock(result, cat.id));
  return card;
}

function tipKeyFor(result) {
  if (result.agreement === "none") return "result.tip.single";
  if (result.agreement === "partial") return "result.tip.closer";
  if (result.agreement === "single_source") return "result.tip.light";
  return "result.tip.background";
}

function buildUncertain(result) {
  const card = el("article", "result__card");
  const head = el("div", "result__head");
  head.append(el("h2", "result__name", "result.not_sure")); // the heading already says it; no second "Not sure" chip
  card.append(head);
  const g = result.guidance;
  const warn = warningsBlock(g && g.warnings, result.hazard);
  if (warn) card.append(warn);

  const alts = result.alternatives || [];
  if (alts.length) {
    card.append(el("p", "result__summary", "result.pick"));
    const list = el("ul", "result__alts");
    const chosen = el("div", "result__chosen");
    chosen.setAttribute("aria-live", "polite");
    alts.forEach((alt, n) => {
      const li = el("li");
      const altMeta = catalog.find((c) => c.id === alt.id);
      const b = el("button", "btn result__guess");
      b.type = "button";
      b.append(el("span", "result__guess-rank", n === 0 ? "result.possible" : "result.less_likely"));
      b.append(txt("span", "result__guess-name", altMeta ? altMeta.name : alt.name));
      if (altMeta) {
        b.append(el("span", "muted", `group.${altMeta.group}`));
        const stamp = el("span", `bin bin--${altMeta.bin}`);
        stamp.dataset.i18n = `bin.${altMeta.bin}`;
        stamp.textContent = t(`bin.${altMeta.bin}`);
        b.append(stamp);
      }
      b.addEventListener("click", () => chooseAlternative(result, alt, chosen, list));
      li.append(b);
      list.append(li);
    });
    card.append(list, chosen);
  }

  card.append(el("h3", "result__sub", "result.tips"));
  const tips = el("ul", "result__list");
  tips.append(el("li", null, tipKeyFor(result))); // one specific tip, chosen by agreement
  card.append(tips);
  card.append(el("p", "muted", "result.second_photo"));
  const again = button("result.retake", "btn btn--primary");
  again.addEventListener("click", () => {
    location.hash = "#/";
    setTimeout(() => { const scan = document.querySelector('[data-action="scan"]'); if (scan) scan.click(); }, 100);
  });
  card.append(again, whyPanel(result), feedbackBlock(result, null));
  return card;
}

async function chooseAlternative(result, alt, chosen, list) {
  list.querySelectorAll("button").forEach((b) => (b.disabled = true));
  const meta = catalog.find((c) => c.id === alt.id);
  chosen.replaceChildren();
  if (meta) {
    chosen.append(txt("h3", "result__sub", meta.name), guidanceBlocks(meta));
    const warn = warningsBlock(meta.warnings, false);
    if (warn) chosen.append(warn);
  }
  const msg = el("p", "muted");
  chosen.append(msg);
  try {
    await sendFeedback(result.request_id, alt.id);
    setKey(msg, "feedback.thanks");
  } catch (err) {
    list.querySelectorAll("button").forEach((b) => (b.disabled = false));
    setKey(msg, err instanceof ApiError ? err.i18nKey : "error.unknown");
  }
}

function announcement(result) {
  const parts = [];
  if (result.status === "uncertain" || !result.category) {
    parts.push(t("result.not_sure"));
  } else {
    parts.push(result.category.name, t(`result.confidence.${confidenceLevel(result.category.confidence)}`));
    if (result.guidance && result.guidance.bin) parts.push(t(`bin.${result.guidance.bin}`));
  }
  if (result.hazard) parts.push(t("result.hazard_notice"));
  return parts.join(". ");
}

// ---------- entry point ----------

async function show() {
  if (!root) return;
  const result = store.result;
  if (!result) {
    root.replaceChildren(el("p", "muted", "result.none"));
    live.textContent = "";
    return;
  }
  await Promise.all([loadCatalog(), loadLabels(), loadSourceNames()]);
  const prev = root.querySelector(".result__why");
  if (prev) whyOpen = prev.open;
  const layout = el("div", "result result--reveal");
  layout.append(photoColumn(), result.status === "uncertain" || !result.category ? buildUncertain(result) : buildOk(result));
  root.replaceChildren(layout);
  live.textContent = announcement(result);
}

document.addEventListener("wasteai:result", show);
document.addEventListener("i18n:change", () => {
  if (store.result && root && root.firstChild) show(); // re-render from the catalog, no new /classify call
});
window.addEventListener("hashchange", () => {
  if (/^#\/?result/.test(location.hash) && root && !root.firstChild) show();
});
if (/^#\/?result/.test(location.hash)) show();
