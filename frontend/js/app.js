// File: frontend/js/app.js
import "./errors.js";
import { guard } from "./errors.js";
import { getCategories } from "./api.js";
import "./i18n.js";
import "./theme.js";
import "./upload.js";
import "./results.js";
import "./audio.js";
// Hash routing (#/, #/browse, #/result) and the browse view over mock categories.
// M3 wires scan/upload, M4 fills #result-root, M5 provides window.__i18n and lang/theme, M6 sound.

const ROUTES = ["home", "browse", "result"];
const state = { categories: [], group: "all", query: "", loaded: false };

const $ = (sel, root = document) => root.querySelector(sel);
// Text lookup hook for M5 (i18n.js sets window.__i18n). Falls back to the given default.
const t = (key, fallback) => (window.__i18n && window.__i18n[key]) || fallback;

function currentRoute() {
  const name = location.hash.replace(/^#\/?/, "") || "home";
  return ROUTES.includes(name) ? name : "home";
}

let firstRender = true;
function renderRouteUnsafe() {
  const name = currentRoute();
  document.querySelectorAll(".view").forEach((view) => {
    view.hidden = view.dataset.view !== name;
  });
  if (name === "browse" && !state.loaded) loadCategories();
  if (!firstRender) {
    const heading = $(`.view[data-view="${name}"] h1`);
    if (heading) heading.focus();
    window.scrollTo(0, 0);
  }
  firstRender = false;
}

function renderRoute() {
  guard(currentRoute(), renderRouteUnsafe);
}

async function loadCategories() {
  try {
    const data = await getCategories(document.documentElement.lang || "en"); // retries with backoff
    state.categories = Array.isArray(data.categories) ? data.categories : [];
    state.loaded = true;
    $("#browse-error").hidden = true;
    renderGroups();
    renderList();
  } catch (err) {
    $("#browse-error").hidden = false;
  }
}

function groupsInOrder() {
  return [...new Set(state.categories.map((c) => c.group))];
}

function renderGroups() {
  const box = $("#browse-groups");
  box.replaceChildren();
  ["all", ...groupsInOrder()].forEach((group) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.dataset.group = group;
    btn.textContent = t(`group.${group}`, group);
    btn.setAttribute("aria-pressed", String(group === state.group));
    box.append(btn);
  });
}

function matches(cat) {
  if (state.group !== "all" && cat.group !== state.group) return false;
  if (!state.query) return true;
  const hay = `${cat.name} ${cat.summary || ""} ${cat.id}`.toLowerCase();
  return hay.includes(state.query);
}

function renderList() {
  const list = $("#browse-list");
  const items = state.categories.filter(matches);
  list.replaceChildren();
  items.forEach((cat) => {
    const li = document.createElement("li");
    li.className = "card";
    const title = document.createElement("h2");
    title.className = "card__title";
    title.textContent = cat.name;
    li.append(title);
    if (cat.summary) {
      const p = document.createElement("p");
      p.className = "card__summary";
      p.textContent = cat.summary;
      li.append(p);
    }
    const meta = document.createElement("div");
    meta.className = "card__meta";
    const chip = document.createElement("span");
    chip.className = `bin bin--${cat.bin}`;
    chip.textContent = t(`bin.${cat.bin}`, cat.bin);
    meta.append(chip);
    li.append(meta);
    list.append(li);
  });
  $("#browse-empty").hidden = items.length !== 0 || !state.loaded;
  $("#browse-count").textContent = t("browse.count", "{n}").replace("{n}", String(items.length));
}

function bindEvents() {
  $("#browse-groups").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-group]");
    if (!btn) return;
    state.group = btn.dataset.group;
    document.querySelectorAll("#browse-groups .chip").forEach((chip) => {
      chip.setAttribute("aria-pressed", String(chip.dataset.group === state.group));
    });
    renderList();
  });
  $("#browse-search").addEventListener("input", (e) => {
    state.query = e.target.value.trim().toLowerCase();
    renderList();
  });
  window.addEventListener("hashchange", renderRoute);
}

bindEvents();
renderRoute();
