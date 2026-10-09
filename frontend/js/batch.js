// File: frontend/js/batch.js
// Batch analysis: up to 10 photos, sent one by one (paced to respect the server rate limit).
// upload.js hands over the files and its resize function; no contract or server change.

import { classify, ApiError, store } from "./api.js";
import { setRich, t } from "./i18n.js";
import { log } from "./log.js";

export const MAX_PHOTOS = 10;
const FREE_SLOTS = 3;      // Nginx burst: the first requests can go out together, then ~1 per 6 s
const GAP_MS = 6500;
const MAX_RETRY = 2;

const batch = { items: [], phase: "idle", run: 0, prepare: null, lastSent: 0, seq: 0 };
const ui = {};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function el(tag, cls, key) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (key) { n.dataset.i18n = key; n.textContent = t(key); }
  return n;
}

function btn(key, cls = "btn") {
  const b = el("button", cls, key || undefined);
  b.type = "button";
  return b;
}

function build() {
  const home = document.querySelector('.view[data-view="home"]');
  if (!home) return false;
  ui.home = home;
  ui.root = el("section", "batch");
  ui.root.hidden = true;
  ui.root.setAttribute("aria-labelledby", "batch-title");
  const title = el("h2", "batch__title", "batch.title");
  title.id = "batch-title";
  ui.hint = el("p", "muted");
  ui.progress = document.createElement("progress");
  ui.progress.className = "batch__progress";
  ui.summary = el("p", "batch__summary");
  ui.summary.setAttribute("role", "status");
  ui.grid = el("ul", "batch__grid");
  ui.add = btn("batch.add");
  ui.start = btn(null, "btn btn--primary"); // text has a variable: set in render(), never by data-i18n
  ui.stop = btn("batch.stop");
  ui.retry = btn("batch.retry");
  ui.close = btn("batch.new");
  ui.input = document.createElement("input");
  ui.input.type = "file";
  ui.input.accept = "image/*";
  ui.input.multiple = true;
  ui.input.hidden = true;
  const bar = el("div", "actions batch__actions");
  bar.append(ui.start, ui.stop, ui.retry, ui.add, ui.close);
  const status = el("div", "batch__status");
  status.append(ui.progress, ui.summary);
  ui.root.append(title, ui.hint, status, ui.grid, bar, ui.input);
  home.append(ui.root);

  ui.add.addEventListener("click", () => ui.input.click());
  ui.input.addEventListener("change", () => { const f = [...ui.input.files]; ui.input.value = ""; addFiles(f); });
  ui.start.addEventListener("click", start);
  ui.stop.addEventListener("click", () => { batch.run += 1; batch.phase = "stopped"; render(); });
  ui.retry.addEventListener("click", () => { batch.items.forEach((i) => i.state === "fail" && (i.state = "wait", i.tries = 0)); start(); });
  ui.close.addEventListener("click", reset);
  ui.grid.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const item = batch.items.find((i) => i.id === Number(b.dataset.id));
    if (!item) return;
    if (b.dataset.act === "remove") remove(item);
    if (b.dataset.act === "details") details(item);
  });
  document.addEventListener("i18n:change", () => batch.items.length && render());
  return true;
}

function remove(item) {
  if (batch.phase === "running") return;
  URL.revokeObjectURL(item.url);
  batch.items = batch.items.filter((i) => i !== item);
  if (!batch.items.length) return reset();
  render();
}

function reset() {
  batch.run += 1;
  batch.items.forEach((i) => URL.revokeObjectURL(i.url));
  batch.items = [];
  batch.phase = "idle";
  ui.root.hidden = true;
  ui.home.classList.remove("is-batch");
  const scan = ui.home.querySelector('[data-action="scan"]');
  if (scan) scan.focus();
}

function details(item) {
  if (!item.result) return;
  if (store.photoUrl) URL.revokeObjectURL(store.photoUrl);
  store.photoUrl = URL.createObjectURL(item.blob); // own copy: the grid keeps its thumbnail
  store.result = item.result;
  document.dispatchEvent(new CustomEvent("wasteai:result", { detail: { result: item.result, photoUrl: store.photoUrl } }));
  location.hash = "#/result";
}

export function setPrepare(fn) {
  batch.prepare = fn;
}

export async function openBatch(files, prepare) {
  if (prepare) batch.prepare = prepare;
  await addFiles(files);
}

async function addFiles(files) {
  if (batch.phase === "running") return;
  const images = files.filter((f) => !f.type || f.type.startsWith("image/"));
  const room = MAX_PHOTOS - batch.items.length;
  ui.root.hidden = false;
  ui.home.classList.add("is-batch");
  if (batch.phase === "done" || batch.phase === "stopped") batch.phase = "ready";
  if (batch.phase === "idle") batch.phase = "ready";
  ui.hint.textContent = t("batch.preparing");
  for (const file of images.slice(0, Math.max(0, room))) {
    try {
      const blob = await batch.prepare(file);
      batch.items.push({ id: ++batch.seq, blob, url: URL.createObjectURL(blob), state: "ready", tries: 0, result: null });
    } catch (e) { log("batch_decode_failed", { detail: e && e.message }); }
  }
  ui.limitNote = images.length > room;
  if (!batch.items.length) return reset();
  render();
}

function counts() {
  const c = { ok: 0, unsure: 0, fail: 0, done: 0 };
  batch.items.forEach((i) => {
    if (i.state === "done") { c.done++; i.result.status === "ok" ? c.ok++ : c.unsure++; }
    if (i.state === "fail") { c.fail++; c.done++; }
  });
  return c;
}

async function start() {
  if (batch.phase === "running") return;
  const token = ++batch.run;
  batch.phase = "running";
  let strikes = 0;
  render();
  for (const item of batch.items) {
    if (item.state === "done" || item.state === "fail") continue;
    for (;;) {
      if (token !== batch.run) return;
      item.state = "run";
      render();
      const wait = batch.lastSent + (batch.sentCount >= FREE_SLOTS ? GAP_MS : 0) - Date.now();
      if (wait > 0) await sleep(wait);
      if (token !== batch.run) return;
      try {
        batch.lastSent = Date.now();
        batch.sentCount = (batch.sentCount || 0) + 1;
        item.result = await classify(item.blob, document.documentElement.lang || "en", false);
        item.state = "done";
        strikes = 0;
        break;
      } catch (err) {
        const limited = err instanceof ApiError && err.code === "rate_limited";
        if (limited && ++strikes >= 2) { // repeated 429s can trigger a temporary ban: stop here
          item.state = "wait";
          batch.phase = "limited";
          return render();
        }
        if (limited && item.tries++ < MAX_RETRY) {
          item.state = "wait";
          render();
          await sleep(((err.retryAfter || 7) + 1) * 1000);
          continue;
        }
        item.state = "fail";
        item.err = err instanceof ApiError ? err.i18nKey : "error.unknown";
        break;
      }
    }
    render();
  }
  if (token === batch.run) {
    batch.phase = "done";
    render();
    document.dispatchEvent(new CustomEvent("wasteai:batch", { detail: { items: batch.items.length, done: true } }));
  }
}

function statusLabel(item) {
  if (item.state === "run") return t("batch.running");
  if (item.state === "wait") return t("batch.wait");
  if (item.state === "fail") return t(item.err || "error.unknown");
  if (item.state === "done") {
    const r = item.result;
    return r.status === "ok" ? t(`result.confidence.${r.category.confidence >= 0.8 ? "high" : r.category.confidence >= 0.65 ? "medium" : "low"}`) : t("batch.unsure");
  }
  return "";
}

function card(item, index) {
  const li = el("li", `batch__card is-${item.state}`);
  const img = document.createElement("img");
  img.src = item.url;
  img.alt = t("batch.photo_alt", { n: index + 1 });
  img.width = 4; img.height = 3; img.className = "batch__thumb";
  const body = el("div", "batch__body");
  const name = el("strong", "batch__name");
  const r = item.result;
  if (r && r.status === "ok") setRich(name, r.category.name);
  else name.textContent = t("batch.photo_alt", { n: index + 1 });
  const meta = el("span", "batch__meta muted");
  meta.textContent = statusLabel(item);
  body.append(name, meta);
  const tags = el("div", "batch__tags");
  const bin = r && r.guidance && r.guidance.bin;
  if (bin) { // same behaviour as the bin chips on Home and Browse: bininfo.js opens the bin dialog
    const b = el("button", `bin bin--${bin}`);
    b.type = "button";
    b.dataset.binInfo = bin;
    b.setAttribute("aria-haspopup", "dialog");
    b.textContent = t(`bin.${bin}`);
    tags.append(b);
  }
  if (r && r.hazard) { const h = el("span", "batch__hazard"); h.textContent = t("batch.hazard"); tags.append(h); }
  if (tags.children.length) body.append(tags);
  li.append(img, body);
  if (r) { const d = btn("batch.details"); d.dataset.act = "details"; d.dataset.id = item.id; li.append(d); }
  else if (batch.phase !== "running") { const x = btn("batch.remove", "icon-btn batch__remove"); x.dataset.act = "remove"; x.dataset.id = item.id; x.textContent = "×"; x.setAttribute("aria-label", t("batch.remove")); li.append(x); }
  return li;
}

function render() {
  const c = counts();
  const running = batch.phase === "running";
  const total = batch.items.length;
  const pending = batch.items.some((i) => i.state === "ready" || i.state === "wait");
  ui.grid.replaceChildren(...batch.items.map(card));
  ui.progress.hidden = !running && batch.phase !== "done";
  ui.progress.max = total; ui.progress.value = c.done;
  ui.hint.textContent = batch.phase === "limited" ? t("batch.slowdown")
    : ui.limitNote ? t("batch.limit", { n: MAX_PHOTOS }) : t("batch.hint", { n: MAX_PHOTOS });
  ui.summary.textContent = running || c.done
    ? `${t("batch.progress", { done: c.done, total })} · ${t("batch.summary", { ok: c.ok, unsure: c.unsure, fail: c.fail })}` : "";
  ui.start.hidden = running || !pending;
  const form = new Intl.PluralRules(document.documentElement.lang || "en").select(total);
  const key = `batch.start.${form}`;
  ui.start.textContent = t(window.__i18n && window.__i18n[key] ? key : "batch.start.other", { n: total });
  ui.stop.hidden = !running;
  ui.retry.hidden = running || !batch.items.some((i) => i.state === "fail");
  ui.add.hidden = running || total >= MAX_PHOTOS;
  ui.close.hidden = running;
  ui.root.setAttribute("aria-busy", String(running));
}

build();
