// File: frontend/js/features/store.js
// The one safe place for on-device data (M31). Keys wasteai.v1.<name>; plain JSON only; never photos.
const PREFIX = "wasteai.v1.";
const MAX_VALUE = 20 * 1024;
const MAX_TOTAL = 100 * 1024;

function storage() {
  try {
    return window.localStorage;
  } catch (err) {
    return null;
  }
}

function hasBinary(value) {
  if (typeof value === "string") return value.startsWith("data:");
  if (typeof Blob !== "undefined" && value instanceof Blob) return true;
  if (value && typeof value === "object") return Object.values(value).some(hasBinary);
  return false;
}

function usedBytes(ls, skip) {
  let total = 0;
  for (let i = 0; i < ls.length; i += 1) {
    const key = ls.key(i);
    if (key && key.startsWith(PREFIX) && key !== skip) total += key.length + (ls.getItem(key) || "").length;
  }
  return total;
}

export function get(name, fallback = null) {
  try {
    const ls = storage();
    const raw = ls && ls.getItem(PREFIX + name);
    return raw === null || raw === undefined ? fallback : JSON.parse(raw);
  } catch (err) {
    return fallback;
  }
}

/** Returns true when saved. Refuses photos, binary data and anything over the size limits. */
export function set(name, value) {
  try {
    const ls = storage();
    if (!ls || hasBinary(value)) return false;
    const raw = JSON.stringify(value);
    if (raw === undefined || raw.length > MAX_VALUE) return false;
    if (usedBytes(ls, PREFIX + name) + raw.length > MAX_TOTAL) return false;
    ls.setItem(PREFIX + name, raw);
    return true;
  } catch (err) {
    return false;
  }
}

export function remove(name) {
  try {
    const ls = storage();
    if (ls) ls.removeItem(PREFIX + name);
  } catch (err) {
    // storage blocked: nothing to remove
  }
}

/** Removes every key that starts with "wasteai." (settings too). Returns how many were removed. */
export function clearAll() {
  try {
    const ls = storage();
    if (!ls) return 0;
    const keys = [];
    for (let i = 0; i < ls.length; i += 1) {
      const key = ls.key(i);
      if (key && key.startsWith("wasteai.")) keys.push(key);
    }
    keys.forEach((key) => ls.removeItem(key));
    return keys.length;
  } catch (err) {
    return 0;
  }
}
