// File: frontend/js/i18n.js
// Language detection, persistence, <html lang/dir>, and text translation.
// Translates every [data-i18n="key"] node and [data-i18n-attr="attr:key;attr2:key2"] attributes.
// Other modules read text through window.__i18n[key] (set here) and re-render on "i18n:change".

import { log } from "./log.js";

const SUPPORTED = ["ar", "en"];
const DEFAULT_LANG = "en";
const RTL_LANGS = new Set(["ar"]);
const STORAGE_KEY = "wasteai.lang";
const cache = {};
let current = null;

function readSaved() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return SUPPORTED.includes(value) ? value : null;
  } catch (err) {
    return null;
  }
}

function save(lang) {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch (err) {
    // storage may be blocked (private mode); the choice just won't persist
  }
}

function detect() {
  const list = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language];
  for (const tag of list) {
    const code = String(tag || "").slice(0, 2).toLowerCase();
    if (SUPPORTED.includes(code)) return code;
  }
  return DEFAULT_LANG;
}

async function loadDictionary(lang) {
  if (cache[lang]) return cache[lang];
  const res = await fetch(`i18n/${lang}.json`);
  if (!res.ok) throw new Error(`i18n ${lang}: ${res.status}`);
  cache[lang] = await res.json();
  return cache[lang];
}

function setDirection(lang) {
  const root = document.documentElement;
  root.lang = lang;
  root.dir = RTL_LANGS.has(lang) ? "rtl" : "ltr";
}

export function getLang() {
  return current || document.documentElement.lang || DEFAULT_LANG;
}

const missing = new Set();

/** Looks up a key; "{n}"-style placeholders are filled from `vars`. A missing key returns "" (never the raw id) and is logged once. */
export function t(key, vars) {
  const dict = window.__i18n || {};
  let text = dict[key];
  if (text === undefined) {
    if (window.__i18n && !missing.has(key)) {
      missing.add(key);
      log("i18n_missing_key", { level: "warning", detail: String(key) });
    }
    return "";
  }
  if (vars) Object.keys(vars).forEach((name) => (text = text.split(`{${name}}`).join(String(vars[name]))));
  return text;
}

export function translateDocument(scope = document) {
  const dict = window.__i18n || {};
  scope.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    if (key && dict[key] !== undefined) node.textContent = dict[key];
  });
  scope.querySelectorAll("[data-i18n-attr]").forEach((node) => {
    node.dataset.i18nAttr.split(";").forEach((pair) => {
      const [attr, key] = pair.split(":");
      if (attr && key && dict[key] !== undefined) node.setAttribute(attr.trim(), dict[key]);
    });
  });
}

/** Switches language: loads the dictionary, sets lang/dir, saves, translates, notifies listeners. */
export async function setLanguage(lang, { persist = true } = {}) {
  const target = SUPPORTED.includes(lang) ? lang : DEFAULT_LANG;
  setDirection(target); // immediate, so layout flips before the dictionary arrives
  try {
    window.__i18n = await loadDictionary(target);
  } catch (err) {
    window.__i18n = window.__i18n || {};
  }
  current = target;
  if (persist) save(target);
  translateDocument();
  document.dispatchEvent(new CustomEvent("i18n:change", { detail: { lang: target, dir: document.documentElement.dir } }));
}

const BDI = /<bdi dir="ltr">(.*?)<\/bdi>/g;

/** Sets server text on a node; only <bdi dir="ltr">...</bdi> becomes an element, everything else stays plain text. */
export function setRich(node, text) {
  const s = String(text ?? "");
  node.replaceChildren();
  let last = 0;
  for (const m of s.matchAll(BDI)) {
    if (m.index > last) node.append(s.slice(last, m.index));
    const b = document.createElement("bdi");
    b.dir = "ltr";
    b.textContent = m[1];
    node.append(b);
    last = m.index + m[0].length;
  }
  if (last < s.length) node.append(s.slice(last));
}

/** Same text without the bdi markup (for <option> and attributes). */
export function plain(text) {
  return String(text ?? "").replace(BDI, "$1");
}

const namespaces = new Set();

async function mergeNamespace(slug, lang) {
  try {
    const res = await fetch(`i18n/features/${slug}.${lang}.json`);
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    Object.keys(data).filter((k) => k.startsWith("f.")).forEach((k) => (window.__i18n[k] = data[k]));
  } catch (err) {
    log("i18n_missing_key", { level: "warning", detail: `namespace ${slug} ${lang}` });
  }
}

/** Loads i18n/features/<slug>.<lang>.json into the dictionary; reloads it on language change. */
export async function loadNamespace(slug) {
  await ready;
  window.__i18n = window.__i18n || {};
  namespaces.add(slug);
  await mergeNamespace(slug, getLang());
  translateDocument();
}

document.addEventListener("i18n:change", async (event) => {
  await Promise.all([...namespaces].map((slug) => mergeNamespace(slug, event.detail.lang)));
  if (namespaces.size) translateDocument();
});

/** Promise that resolves after the first dictionary is applied. */
export function whenReady() {
  return ready;
}

export function toggleLanguage() {
  return setLanguage(getLang() === "ar" ? "en" : "ar");
}

document.addEventListener("click", (event) => {
  if (event.target.closest('[data-action="lang"]')) toggleLanguage();
});

const initial = readSaved() || detect();
setDirection(initial);
export const ready = setLanguage(initial, { persist: false });
