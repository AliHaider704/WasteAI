// File: frontend/js/labels.js
// Static label dictionary: raw model labels shown in the user's language (no live translation).

import { getLang, t } from "./i18n.js";

const cache = {};

export async function loadLabels(lang = getLang()) {
  if (cache[lang]) return cache[lang];
  try {
    const res = await fetch(`i18n/labels.${lang}.json`);
    cache[lang] = res.ok ? await res.json() : {};
  } catch {
    cache[lang] = {};
  }
  return cache[lang];
}

// Dictionary hit, else the raw tag (shown in <bdi dir="ltr">); the generic text only for an empty tag (D-053).
export function labelFor(raw, lang = getLang()) {
  const dict = cache[lang] || {};
  const text = String(raw || "").trim();
  const key = text.toLowerCase();
  if (!text) return t("why.other_label");
  return Object.prototype.hasOwnProperty.call(dict, key) && key[0] !== "_" ? dict[key] : text;
}

function isKnown(raw, lang) {
  const dict = cache[lang] || {};
  const key = String(raw || "").trim().toLowerCase();
  return Object.prototype.hasOwnProperty.call(dict, key) && key[0] !== "_";
}

/** One tag as a node: name (raw tags in bdi), score, "used" marker; unmapped tags are dimmed. */
export function renderTag(item, lang = getLang(), catName = "") {
  const node = document.createElement("span");
  node.className = "why-tag" + (item.mapped === false ? " why-tag--unused" : "");
  const name = document.createElement(isKnown(item.label, lang) ? "span" : "bdi");
  if (name.tagName === "BDI") { name.dir = "ltr"; name.translate = false; }
  name.textContent = labelFor(item.label, lang);
  node.append(name, ` ${Math.round((item.score || 0) * 100)}%`);
  if (item.mapped === true) {
    const used = document.createElement("span");
    used.className = "why-tag__used";
    used.dataset.i18n = "why.used";
    used.textContent = ` (${t("why.used")}${catName ? ": " + catName : ""})`;
    node.append(used);
  } else if (item.mapped === false) {
    node.title = t("why.unused");
  }
  return node;
}

/** A comma-separated list of tags; every renderer uses this so they cannot drift. */
export function renderTags(items, lang = getLang(), catNameOf = () => "") {
  const frag = document.createDocumentFragment();
  items.forEach((it, n) => {
    if (n) frag.append(", ");
    frag.append(renderTag(it, lang, it.cat ? catNameOf(it.cat) : ""));
  });
  return frag;
}

let names = null;

/** Real service and model names (D-030): proper nouns, same in both languages. */
export async function loadSourceNames() {
  if (names) return names;
  try {
    const res = await fetch("i18n/source_names.json");
    names = res.ok ? await res.json() : {};
  } catch {
    names = {};
  }
  return names;
}

export function sourceName(id) {
  const v = names && names[id];
  return typeof v === "string" && id[0] !== "_" ? v : "";
}
