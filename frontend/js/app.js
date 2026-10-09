// File: frontend/js/app.js
import "./errors.js";
import { guard } from "./errors.js";
import { getCategories } from "./api.js";
import { getLang, plain, setRich, t, whenReady } from "./i18n.js";
import "./theme.js";
import "./header-scroll.js";
import "./contrast.js";
import "./upload.js";
import "./dropzone.js";
import "./results.js";
import "./bininfo.js";
import "./audio.js";
import "./features/registry.js";
// Hash routing (#/, #/browse, #/result) and the Browse view (M11 spec, restored in M18a).
// Filters live in the hash: #/browse?group=glass&q=bottle (written with history.replaceState).

const ROUTES = ["home", "browse", "result"];
const state = { categories: [], group: "all", query: "", loaded: false, lang: null, token: 0 };

const $ = (sel, root = document) => root.querySelector(sel);

function parseHash() {
  const [path, qs = ""] = location.hash.replace(/^#\/?/, "").split("?");
  return { name: ROUTES.includes(path) ? path : "home", params: new URLSearchParams(qs) };
}

function currentRoute() {
  return parseHash().name;
}

function readFilters() {
  const { name, params } = parseHash();
  if (name !== "browse") return;
  state.group = params.get("group") || "all";
  const q = plain(params.get("q") || "").replace(/<[^>]*>/g, "").trim();
  state.query = q.toLowerCase();
  $("#browse-search").value = q;
}

function writeFilters() {
  const params = new URLSearchParams();
  if (state.group !== "all") params.set("group", state.group);
  if (state.query) params.set("q", state.query);
  const qs = params.toString();
  history.replaceState(null, "", `#/browse${qs ? `?${qs}` : ""}`);
}

function iconNode(name) {
  if (!name) return null;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "icon card__icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", "32");
  svg.setAttribute("height", "32");
  const use = document.createElementNS(NS, "use");
  use.setAttribute("href", `assets/category-icons.svg#${name}`);
  svg.append(use);
  return svg;
}

let firstRender = true;
function renderRouteUnsafe() {
  const name = currentRoute();
  document.querySelectorAll(".view").forEach((view) => {
    view.hidden = view.dataset.view !== name;
  });
  if (name === "browse") {
    readFilters();
    if (!state.loaded || state.lang !== getLang()) loadCategories();
    else {
      renderGroups();
      renderList();
    }
  }
  if (!firstRender) {
    const heading = $(`.view[data-view="${name}"] h1`);
    if (heading) heading.focus();
    window.scrollTo(0, 0);
  }
  firstRender = false;
}

function renderRoute() {
  document.dispatchEvent(new CustomEvent("wasteai:route", { detail: { view: currentRoute() } }));
  guard(currentRoute(), renderRouteUnsafe);
}

async function loadCategories() {
  const token = ++state.token;
  const lang = getLang();
  try {
    await whenReady();
    const data = await getCategories(lang); // retries with backoff
    if (token !== state.token) return; // a newer load (language change) wins
    state.categories = Array.isArray(data.categories) ? data.categories : [];
    state.loaded = true;
    state.lang = lang;
    $("#browse-error").hidden = true;
    renderGroups();
    renderList();
  } catch (err) {
    if (token !== state.token) return;
    state.loaded = false;
    $("#browse-error").hidden = false;
    $("#browse-empty").hidden = true;
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
    btn.textContent = t(`group.${group}`);
    btn.setAttribute("aria-pressed", String(group === state.group));
    box.append(btn);
  });
}

function matches(cat) {
  if (state.group !== "all" && cat.group !== state.group) return false;
  if (!state.query) return true;
  const hay = plain(`${cat.name} ${cat.summary || ""} ${cat.id}`).toLowerCase();
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
    setRich(title, cat.name);
    const icon = iconNode(cat.icon);
    if (icon) li.append(icon);
    li.append(title);
    if (cat.summary) {
      const p = document.createElement("p");
      p.className = "card__summary";
      setRich(p, cat.summary);
      li.append(p);
    }
    const meta = document.createElement("div");
    meta.className = "card__meta";
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `bin bin--${cat.bin}`;
    chip.dataset.binInfo = cat.bin; // opens the same bin dialog as on Home (handled in bininfo.js)
    chip.setAttribute("aria-haspopup", "dialog");
    chip.textContent = t(`bin.${cat.bin}`);
    meta.append(chip);
    li.append(meta);
    list.append(li);
  });
  $("#browse-empty").hidden = items.length !== 0 || !state.loaded;
  $("#browse-count").textContent = state.loaded ? t("browse.count", { n: items.length }) : "";
}

function applyFilters() {
  writeFilters();
  document.querySelectorAll("#browse-groups .chip").forEach((chip) => {
    chip.setAttribute("aria-pressed", String(chip.dataset.group === state.group));
  });
  renderList();
}

function bindEvents() {
  $("#browse-groups").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-group]");
    if (!btn) return;
    state.group = btn.dataset.group;
    applyFilters();
  });
  $("#browse-search").addEventListener("input", (e) => {
    state.query = e.target.value.trim().toLowerCase();
    applyFilters();
  });
  $("#browse-clear").addEventListener("click", () => {
    state.group = "all";
    state.query = "";
    $("#browse-search").value = "";
    applyFilters();
  });
  $("#browse-retry").addEventListener("click", () => {
    $("#browse-error").hidden = true;
    loadCategories();
  });
  document.addEventListener("i18n:change", () => {
    // Server text follows ?lang=, so reload the categories; labels rebuild when the data arrives.
    if (currentRoute() === "browse" || state.loaded) {
      if (state.loaded) {
        renderGroups();
        renderList();
      }
      loadCategories();
    }
  });
  window.addEventListener("hashchange", renderRoute);
}

const search = $("#browse-search");
search.setAttribute("name", "q");
search.setAttribute("type", "search");
search.setAttribute("inputmode", "search");
search.setAttribute("autocomplete", "off");

bindEvents();
whenReady().then(renderRoute, renderRoute);
