// File: frontend/js/bininfo.js
// Bin details dialog: tap a bin chip on Home to read what goes in, what stays out and how to prepare it.
// Texts come from i18n/bins.<lang>.json (static, ar + en); category names come from /categories.

import { getCategories } from "./api.js";
import { getLang, setRich, t, whenReady } from "./i18n.js";
import { log } from "./log.js";

const NS = "http://www.w3.org/2000/svg";
const cache = {};
let dialog = null;
let openBin = null;
let token = 0;

async function loadBins(lang) {
  if (cache[lang]) return cache[lang];
  try {
    const res = await fetch(`i18n/bins.${lang}.json`);
    cache[lang] = res.ok ? (await res.json()).bins || {} : {};
  } catch (err) {
    cache[lang] = {};
  }
  return cache[lang];
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) setRich(node, text);
  return node;
}

function icon(href, className = "icon") {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", className);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(NS, "use");
  use.setAttribute("href", href);
  svg.append(use);
  return svg;
}

function list(tag, items, className) {
  const node = el(tag, className);
  (items || []).forEach((item) => node.append(el("li", "", item)));
  return node;
}

function panel(kind, titleKey, items) {
  const box = el("section", `bininfo__panel bininfo__panel--${kind}`);
  const head = el("h3", "bininfo__h");
  head.append(icon(`assets/icons.svg#${kind === "yes" ? "check" : "x"}`), el("span", "", t(titleKey)));
  box.append(head, list("ul", items, "bininfo__list"));
  return box;
}

function ensureDialog() {
  if (dialog) return dialog;
  dialog = document.createElement("dialog");
  dialog.className = "bininfo";
  dialog.setAttribute("aria-labelledby", "bininfo-title");
  // A click on the backdrop lands on the dialog element itself.
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close();
    const link = e.target.closest("a[href]");
    if (link) dialog.close();
  });
  dialog.addEventListener("close", () => {
    openBin = null;
  });
  document.body.append(dialog);
  return dialog;
}

function categoryLinks(cats) {
  const box = el("section", "bininfo__covers");
  box.append(el("h3", "bininfo__h", t("bininfo.covers")));
  const ul = el("ul", "bininfo__cats");
  cats.forEach((cat) => {
    const li = el("li");
    const a = document.createElement("a");
    a.className = "bininfo__cat";
    a.href = `#/browse?q=${encodeURIComponent(cat.name)}`;
    if (cat.icon) {
      const svg = icon(`assets/category-icons.svg#${cat.icon}`, "icon bininfo__cat-icon");
      svg.setAttribute("width", "20");
      svg.setAttribute("height", "20");
      a.append(svg);
    }
    a.append(el("span", "", cat.name));
    li.append(a);
    ul.append(li);
  });
  box.append(ul);
  return box;
}

async function render(bin) {
  const mine = ++token;
  const lang = getLang();
  const [bins, catalog] = await Promise.all([
    loadBins(lang),
    getCategories(lang).catch(() => null),
  ]);
  if (mine !== token || openBin !== bin) return;
  const data = bins[bin];
  const root = ensureDialog();
  root.replaceChildren();
  root.className = `bininfo bininfo--${bin}`;

  const head = el("div", "bininfo__head");
  const stamp = el("h2", `bin bin--${bin} bininfo__stamp`, t(`bin.${bin}`));
  stamp.id = "bininfo-title";
  const close = el("button", "icon-btn bininfo__close");
  close.type = "button";
  close.setAttribute("aria-label", t("bininfo.close"));
  close.append(icon("assets/icons.svg#x"));
  close.addEventListener("click", () => root.close());
  head.append(stamp, close);
  root.append(head);

  if (!data) {
    root.append(el("p", "bininfo__lead", t("bininfo.error")));
    return;
  }

  const body = el("div", "bininfo__body");
  body.append(el("p", "bininfo__tagline", data.tagline), el("p", "bininfo__lead", data.definition));

  const cols = el("div", "bininfo__cols");
  cols.append(panel("yes", "bininfo.accepts", data.accepts), panel("no", "bininfo.rejects", data.rejects));
  body.append(cols);

  const prep = el("section", "bininfo__prep");
  prep.append(el("h3", "bininfo__h", t("bininfo.prepare")), list("ol", data.prepare, "bininfo__steps"));
  body.append(prep);

  const cats = ((catalog && catalog.categories) || []).filter((c) => c.bin === bin);
  if (cats.length) body.append(categoryLinks(cats));

  const why = el("aside", "bininfo__why");
  why.append(el("h3", "bininfo__h", t("bininfo.why")), el("p", "", data.why));
  body.append(why, el("p", "bininfo__note muted", t("bininfo.note")));

  const done = el("button", "btn bininfo__done", t("bininfo.close"));
  done.type = "button";
  done.addEventListener("click", () => root.close());
  body.append(done);
  root.append(body);
}

export async function showBin(bin) {
  await whenReady();
  openBin = bin;
  const root = ensureDialog();
  if (!root.open) root.showModal();
  try {
    await render(bin);
  } catch (err) {
    log("bininfo_failed", { level: "warning", detail: String(bin) });
  }
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-bin-info]");
  if (btn) showBin(btn.dataset.binInfo);
});

// Language switch while the dialog is open: redraw it in the new language.
document.addEventListener("i18n:change", () => {
  if (openBin && dialog && dialog.open) render(openBin);
});
