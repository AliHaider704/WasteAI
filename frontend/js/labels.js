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

// Unknown or not-yet-loaded labels return the localized generic text, never the raw string.
export function labelFor(raw, lang = getLang()) {
  const dict = cache[lang] || {};
  const key = String(raw || "").trim().toLowerCase();
  return Object.prototype.hasOwnProperty.call(dict, key) && key[0] !== "_" ? dict[key] : t("why.other_label");
}
