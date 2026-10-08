// File: frontend/js/upload.js
// Capture / upload flow: camera or file -> resize -> preview (retake) -> Analyze -> result.
// Builds its own panel inside the home view. Requires one line in app.js: import "./upload.js";
// All text is looked up by key (window.__i18n, provided by i18n.js in M5); the key is shown until then.

import { classify, ApiError, store } from "./api.js";
import { log } from "./log.js";
import { createConsent } from "./consent.js";
import { openBatch, setPrepare } from "./batch.js";
import { isCameraSupported, startCamera, stopCamera, grabFrame } from "./camera.js";

const MAX_SIDE = 1024;
const JPEG_QUALITY = 0.85;
const BACKGROUND = "#fff"; // flattens transparent PNG/WebP before JPEG encoding

const t = (key) => (window.__i18n && window.__i18n[key]) || key;
const state = { mode: "idle", stream: null, blob: null, url: null, source: null, session: 0, pending: false, cooldown: null };
const ui = {};

function el(tag, className, key) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (key) {
    node.dataset.i18n = key;
    node.textContent = t(key);
  }
  return node;
}

function fileInput(capture) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  if (capture) input.setAttribute("capture", "environment");
  input.hidden = true;
  if (!capture) input.multiple = true; // gallery: up to MAX_PHOTOS at once
  return input;
}

function build() {
  ui.home = document.querySelector('.view[data-view="home"]');
  if (!ui.home) return false;
  ui.actions = ui.home.querySelector(".actions");

  ui.panel = el("section", "capture");
  ui.panel.hidden = true;
  const title = el("h2", "capture__title", "capture.title");
  title.id = "capture-title";
  ui.panel.setAttribute("aria-labelledby", title.id);

  ui.video = document.createElement("video");
  ui.video.className = "capture__media";
  ui.video.autoplay = true;
  ui.video.muted = true;
  ui.video.setAttribute("playsinline", "");
  ui.img = document.createElement("img");
  ui.img.className = "capture__media";
  ui.img.alt = t("capture.preview_alt");
  ui.img.width = 4; // ratio hint; CSS sets aspect-ratio (no layout shift)
  ui.img.height = 3;
  ui.progress = document.createElement("progress"); // no value = calm indeterminate bar
  ui.progress.className = "capture__progress";
  ui.status = el("p", "muted capture__status");
  ui.status.setAttribute("role", "status");

  ui.shutter = el("button", "btn btn--primary", "capture.shutter");
  ui.go = el("button", "btn btn--primary", "capture.allow");
  ui.pick = el("button", "btn", "capture.choose");
  ui.retake = el("button", "btn", "capture.retake");
  ui.analyze = el("button", "btn btn--primary", "capture.analyze");
  ui.cancel = el("button", "btn", "capture.cancel");
  [ui.shutter, ui.go, ui.pick, ui.retake, ui.analyze, ui.cancel].forEach((b) => (b.type = "button"));

  ui.consent = createConsent();
  const buttons = el("div", "actions");
  buttons.append(ui.go, ui.shutter, ui.analyze, ui.retake, ui.pick, ui.cancel);

  ui.fileCapture = fileInput(true);
  ui.fileGallery = fileInput(false);
  ui.panel.append(title, ui.video, ui.img, ui.progress, ui.status, ui.consent.node, buttons, ui.fileCapture, ui.fileGallery);
  ui.home.append(ui.panel);
  return true;
}

function say(key) {
  ui.status.dataset.i18n = key || "";
  ui.status.textContent = key ? t(key) : "";
}

// mode -> visible parts
const MODES = {
  explain: { buttons: ["go", "pick", "cancel"] },
  starting: { video: true, buttons: ["cancel"] },
  camera: { video: true, buttons: ["shutter", "pick", "cancel"] },
  fallback: { buttons: ["pick", "cancel"] },
  processing: { buttons: [] },
  preview: { img: true, buttons: ["analyze", "retake", "cancel"] },
  loading: { img: true, progress: true, buttons: [] },
};

function setMode(mode) {
  state.mode = mode;
  const cfg = MODES[mode];
  ui.panel.hidden = mode === "idle";
  if (ui.actions) ui.actions.hidden = mode !== "idle";
  if (!cfg) return;
  ui.video.hidden = !cfg.video;
  ui.img.hidden = !cfg.img;
  ui.progress.hidden = !cfg.progress;
  ["go", "shutter", "pick", "retake", "analyze", "cancel"].forEach((name) => {
    ui[name].hidden = !cfg.buttons.includes(name);
  });
  ui.consent.setVisible(mode === "preview");
  ui.panel.setAttribute("aria-busy", String(mode === "loading" || mode === "processing"));
}

function releaseCamera() {
  stopCamera(state.stream, ui.video);
  state.stream = null;
}

function releasePhoto() {
  if (state.url) URL.revokeObjectURL(state.url);
  state.url = null;
  state.blob = null;
  ui.consent.reset();
  ui.img.removeAttribute("src");
}

function closePanel(restoreFocus) {
  state.session += 1;
  stopCountdown();
  releaseCamera();
  releasePhoto();
  say("");
  setMode("idle");
  if (restoreFocus) {
    const scan = ui.home.querySelector('[data-action="scan"]');
    if (scan) scan.focus();
  }
}

// ---------- image processing ----------

async function decode(file) {
  if ("createImageBitmap" in window) {
    try {
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch (err) {
      try {
        return await createImageBitmap(file);
      } catch (err2) {
        // fall through to <img> decoding
      }
    }
  }
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("decode"));
    };
    img.src = url;
  });
}

/** Draws `source` into a canvas whose longest side is <= 1024 px and encodes JPEG q0.85. */
function resizeToJpeg(source, width, height) {
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = BACKGROUND;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("encode"))), "image/jpeg", JPEG_QUALITY);
  });
}

function showPreview(blob, source) {
  releasePhoto();
  state.blob = blob;
  state.source = source;
  state.url = URL.createObjectURL(blob);
  ui.img.src = state.url;
  say("");
  setMode("preview");
  ui.analyze.focus();
}

async function toJpeg(file) {
  const bitmap = await decode(file);
  const blob = await resizeToJpeg(bitmap, bitmap.width, bitmap.height);
  if (bitmap.close) bitmap.close();
  return blob;
}

function handleFiles(files, source) {
  const list = Array.from(files || []);
  if (list.length > 1) {
    if (state.mode !== "idle") closePanel(false);
    openBatch(list.slice(0, 40), toJpeg); // batch.js keeps the first MAX_PHOTOS images
    return;
  }
  handleFile(list[0], source);
}

async function handleFile(file, source) {
  if (!file || state.mode === "loading") return;
  const session = ++state.session;
  releaseCamera();
  setMode("processing");
  if (file.type && !file.type.startsWith("image/")) {
    setMode("fallback");
    say("upload.invalid");
    return;
  }
  say("upload.processing");
  try {
    const bitmap = await decode(file);
    const blob = await resizeToJpeg(bitmap, bitmap.width, bitmap.height);
    if (bitmap.close) bitmap.close();
    if (session !== state.session) return; // cancelled meanwhile
    showPreview(blob, source);
  } catch (err) {
    if (session !== state.session) return;
    setMode("fallback");
    say("upload.decode_failed");
  }
}

// ---------- camera flow ----------

const EXPLAINED_KEY = "wasteai.camera_explained";

function wasExplained() {
  try {
    return localStorage.getItem(EXPLAINED_KEY) === "1";
  } catch (e) {
    return false;
  }
}

function markExplained() {
  try {
    localStorage.setItem(EXPLAINED_KEY, "1");
  } catch (e) {
    /* storage unavailable: explain again next time */
  }
}

async function openCamera(skipExplain) {
  const session = ++state.session;
  releasePhoto();
  if (!skipExplain && !wasExplained()) {
    // Explain why the camera is needed before the browser shows its prompt.
    setMode("explain");
    say("camera.explain");
    ui.go.focus();
    return;
  }
  setMode("starting");
  say("camera.starting");
  try {
    const stream = await startCamera(ui.video);
    if (session !== state.session) {
      stopCamera(stream, ui.video);
      return;
    }
    state.stream = stream;
    state.source = "camera";
    say("");
    setMode("camera");
    ui.shutter.focus();
  } catch (err) {
    if (session !== state.session) return;
    setMode("fallback");
    say(err && err.i18nKey ? err.i18nKey : "camera.error");
    ui.pick.focus();
  }
}

async function takePhoto() {
  try {
    const frame = grabFrame(ui.video);
    const blob = await resizeToJpeg(frame, frame.width, frame.height);
    releaseCamera();
    showPreview(blob, "camera");
  } catch (err) {
    releaseCamera();
    setMode("fallback");
    say("camera.error");
  }
}

// ---------- analyze ----------

// 429: disable Analyze and show a visible countdown from Retry-After (F-04).
function stopCountdown() {
  if (state.cooldown) clearInterval(state.cooldown);
  state.cooldown = null;
  if (ui.analyze) ui.analyze.disabled = false;
}

function startCountdown(seconds) {
  stopCountdown();
  let left = Math.max(1, Math.min(Math.ceil(seconds) || 30, 600));
  const session = state.session;
  ui.analyze.disabled = true;
  const tick = () => {
    if (session !== state.session) return stopCountdown();
    if (left <= 0) {
      stopCountdown();
      say("countdown.ready");
      ui.analyze.focus();
      return;
    }
    ui.status.dataset.i18n = "";
    ui.status.textContent = t("countdown.wait").replace("{n}", String(left));
    left -= 1;
  };
  tick();
  state.cooldown = setInterval(tick, 1000);
}

async function analyze() {
  if (!state.blob || state.mode !== "preview" || state.pending || state.cooldown) return; // F-19
  state.pending = true;
  setMode("loading");
  say("loading.analyzing");
  try {
    const result = await classify(state.blob, document.documentElement.lang || "en", ui.consent.isChecked());
    finish(result);
  } catch (err) {
    setMode("preview"); // keeps the photo preview
    if (err instanceof ApiError) {
      if (err.code === "rate_limited") startCountdown(err.retryAfter || 30);
      else say(err.i18nKey);
    } else {
      log("analyze_error", { detail: err && err.message });
      say("error.unknown");
    }
    if (!state.cooldown) ui.analyze.focus();
  } finally {
    state.pending = false;
  }
}

function finish(result) {
  if (store.photoUrl) URL.revokeObjectURL(store.photoUrl);
  store.photoUrl = state.url; // keep the preview alive for the result page
  state.url = null;
  store.result = result;
  closePanel(false);
  document.dispatchEvent(new CustomEvent("wasteai:result", { detail: { result, photoUrl: store.photoUrl } }));
  location.hash = "#/result";
}

function retake() {
  if (state.source === "camera") {
    openCamera();
  } else {
    ui.fileGallery.click();
  }
}

// ---------- wiring ----------

function onScan() {
  if (state.mode === "loading") return;
  if (!isCameraSupported()) {
    ui.fileCapture.click(); // synchronous: keeps the user gesture (iOS)
    return;
  }
  openCamera();
}

function bindDragAndDrop() {
  const home = ui.home;
  ["dragenter", "dragover"].forEach((type) =>
    home.addEventListener(type, (e) => {
      e.preventDefault();
      home.classList.add("is-dragover");
    })
  );
  home.addEventListener("dragleave", (e) => {
    if (!home.contains(e.relatedTarget)) home.classList.remove("is-dragover");
  });
  home.addEventListener("drop", (e) => {
    e.preventDefault();
    home.classList.remove("is-dragover");
    handleFiles(e.dataTransfer && e.dataTransfer.files, "drop");
  });
}

function bind() {
  setPrepare(toJpeg);
  document.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-action]");
    if (!trigger) return;
    if (trigger.dataset.action === "scan") onScan();
    if (trigger.dataset.action === "upload" && state.mode !== "loading") ui.fileGallery.click();
  });
  ui.go.addEventListener("click", () => {
    markExplained();
    openCamera(true);
  });
  ui.shutter.addEventListener("click", takePhoto);
  ui.pick.addEventListener("click", () => ui.fileGallery.click());
  ui.retake.addEventListener("click", retake);
  ui.analyze.addEventListener("click", analyze);
  ui.cancel.addEventListener("click", () => closePanel(true));
  [[ui.fileCapture, "capture"], [ui.fileGallery, "gallery"]].forEach(([input, source]) => {
    input.addEventListener("change", () => {
      const files = input.files;
      const list = Array.from(files || []);
      input.value = "";
      handleFiles(list, source);
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.mode !== "idle" && state.mode !== "loading") closePanel(true);
  });
  window.addEventListener("hashchange", () => {
    if (state.mode !== "idle" && state.mode !== "loading") closePanel(false);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && (state.mode === "camera" || state.mode === "starting")) closePanel(false);
  });
  bindDragAndDrop();
}

if (build()) bind();
