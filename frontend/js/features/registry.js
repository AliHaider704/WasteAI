// File: frontend/js/features/registry.js
// Lazy feature loader (M30). Reads data/features.json, loads a module on its first trigger
// when enabled and in the active profile. With every flag off it requests only features.json.
import { t, getLang, loadNamespace } from "../i18n.js";
import { log } from "../log.js";

const TRIGGERS = ["home", "capture", "result", "browse", "header", "footer", "idle", "command"];
const state = { flags: {}, profiles: {}, profile: "public", loaded: new Map(), commands: [] };
const listeners = [];
// Remember the latest route: the first wasteai:route fires before features.json has loaded.
let lastView = null;
document.addEventListener("wasteai:route", (e) => { lastView = e.detail && e.detail.view; });

function flagsFor(trigger) {
  return Object.entries(state.flags).filter(([slug, f]) => {
    if (!f || f.enabled !== true || f.trigger !== trigger) return false;
    if (slug.startsWith("_")) return true; // dev probes ignore profiles
    return (state.profiles[state.profile] || []).includes(slug);
  });
}

export function on(type, fn) {
  document.addEventListener(type, fn);
  listeners.push([type, fn]);
}

export function slot(id) {
  return document.getElementById(`slot-${id}`);
}

export function registerCommand(cmd) {
  if (cmd && cmd.id) state.commands.push(cmd);
}

export function commands() {
  return state.commands.slice();
}

let storePromise = null;
function getStore() {
  // store.js arrives in M31; until then features get a no-op store.
  storePromise = storePromise || import("./store.js").catch(() => ({ get: (n, d) => d, set() {}, remove() {}, clearAll: () => 0 }));
  return storePromise;
}

function addStyles(slug) {
  if (document.querySelector(`link[data-feature-css="${slug}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.dataset.featureCss = slug;
  link.href = `css/features/${slug}.css`;
  document.head.append(link);
}

async function load(slug) {
  if (state.loaded.has(slug)) return state.loaded.get(slug);
  const job = (async () => {
    try {
      const flag = state.flags[slug];
      const mod = await import(`./${flag.module || slug}.js`);
      if (mod.styles) addStyles(typeof mod.styles === "string" ? mod.styles : slug);
      await loadNamespace(slug);
      const store = await getStore();
      await mod.default({ slot, t, store, on, flags: state.flags, lang: getLang() });
      return true;
    } catch (err) {
      log("feature_load_failed", { level: "warning", detail: `${slug} ${err && err.message ? err.message : err}` });
      return false; // a broken feature never breaks the page
    }
  })();
  state.loaded.set(slug, job);
  return job;
}

export function fire(trigger) {
  if (!TRIGGERS.includes(trigger)) return Promise.resolve();
  return Promise.all(flagsFor(trigger).map(([slug]) => load(slug)));
}

function viewTrigger(view) {
  return ["home", "browse", "result"].includes(view) ? view : null;
}

export async function startRegistry() {
  try {
    const res = await fetch("data/features.json", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    state.flags = data.features || {};
    state.profiles = data.profiles || {};
  } catch (err) {
    return; // no flags, no features
  }
  const asked = new URLSearchParams(location.search).get("profile");
  state.profile = asked && state.profiles[asked] ? asked : "public";
  on("wasteai:route", (e) => {
    const trigger = viewTrigger(e.detail && e.detail.view);
    if (trigger) fire(trigger);
  });
  // Home cards live in #slot-home, which always exists in the page: load them at startup,
  // whatever the first route is, so they never depend on a later navigation.
  fire("home");
  const first = viewTrigger(lastView);
  if (first && first !== "home") fire(first);
  on("wasteai:capture", () => fire("capture"));
  on("wasteai:result", () => fire("result"));
  fire("header");
  fire("footer");
  const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 1500));
  idle(() => fire("idle"));
}

startRegistry();
