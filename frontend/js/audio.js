// File: frontend/js/audio.js
// Calm optional sound: synthesized Web Audio cues (no audio files) and optional speech of the category name.
// - AudioContext is created only after a user gesture.
// - Sound is ON by default and OFF once the user mutes (saved in localStorage, wrapped in try/catch).
// - Wiring needs no changes elsewhere: it listens for the shutter button click, the "wasteai:result" event
//   and error messages shown in the capture panel. Only app.js must import this file.

import { speakParts, cancel as speechCancel } from "./speech.js";

const STORAGE_KEY = "wasteai.sound";
const VOICE_KEY = "wasteai.voice";
const MAX_GAIN = 0.15; // hard ceiling for every cue
const ERROR_KEYS = new Set([
  "camera.denied", "camera.not_found", "camera.busy", "camera.error", "upload.invalid", "upload.decode_failed",
]);

let ctx = null;
let muted = readMuted();
let voiceEnabled = readFlag(VOICE_KEY) !== "off";

// ---------- preferences ----------

function readFlag(key) {
  try {
    return localStorage.getItem(key);
  } catch (err) {
    return null;
  }
}

function writeFlag(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (err) {
    // storage may be blocked; the choice just won't persist
  }
}

function readMuted() {
  return readFlag(STORAGE_KEY) === "off";
}

export function isMuted() {
  return muted;
}

export function setVoiceEnabled(enabled) {
  voiceEnabled = Boolean(enabled);
  writeFlag(VOICE_KEY, voiceEnabled ? "on" : "off");
  if (!voiceEnabled) stopSpeech();
}

function syncButtons() {
  document.querySelectorAll('[data-action="sound"]').forEach((btn) => {
    btn.setAttribute("aria-pressed", String(!muted)); // pressed = sound on
    const use = btn.querySelector("use");
    if (use) use.setAttribute("href", `assets/icons.svg#${muted ? "volume-off" : "volume-on"}`);
  });
}

export function setMuted(value) {
  muted = Boolean(value);
  writeFlag(STORAGE_KEY, muted ? "off" : "on");
  if (muted) stopSpeech();
  syncButtons();
  document.dispatchEvent(new CustomEvent("sound:change", { detail: { muted } }));
}

export function toggleMuted() {
  setMuted(!muted);
  if (!muted) playShutter(); // soft tick confirms that sound is back on
}

// ---------- AudioContext (only after a user gesture) ----------

function unlock() {
  if (!ctx) {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return;
    try {
      ctx = new Ctor();
    } catch (err) {
      ctx = null;
      return;
    }
  }
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  if (ctx.state === "running" || ctx.state === "suspended") {
    ["pointerdown", "keydown", "touchend"].forEach((type) => document.removeEventListener(type, unlock, true));
  }
}

["pointerdown", "keydown", "touchend"].forEach((type) => document.addEventListener(type, unlock, true));

function withContext(play) {
  if (muted || !ctx) return;
  if (ctx.state === "running") {
    play(ctx);
  } else {
    ctx.resume().then(() => play(ctx)).catch(() => {});
  }
}

// ---------- cue synthesis ----------

/** One soft note: quick attack, exponential decay. Peak gain never exceeds MAX_GAIN. */
function tone(audio, { freq, endFreq, start = 0, duration, peak, type = "sine" }) {
  const t0 = audio.currentTime + start;
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (endFreq) osc.frequency.exponentialRampToValueAtTime(endFreq, t0 + duration);
  gain.gain.setValueAtTime(0.0001, t0);
  gain.gain.linearRampToValueAtTime(Math.min(peak, MAX_GAIN), t0 + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
  osc.connect(gain);
  gain.connect(audio.destination);
  osc.start(t0);
  osc.stop(t0 + duration + 0.02);
}

/** Rising two-note chime (C5 then G5), about 260 ms. */
export function playSuccess() {
  withContext((audio) => {
    tone(audio, { freq: 523.25, start: 0, duration: 0.16, peak: 0.11 });
    tone(audio, { freq: 783.99, start: 0.1, duration: 0.16, peak: 0.11 });
  });
}

/** Low, gentle falling tone, about 280 ms. */
export function playError() {
  withContext((audio) => {
    tone(audio, { freq: 207.65, endFreq: 164.81, start: 0, duration: 0.28, peak: 0.1 });
  });
}

/** Short shutter tick, about 150 ms. */
export function playShutter() {
  withContext((audio) => {
    tone(audio, { freq: 1400, endFreq: 700, start: 0, duration: 0.15, peak: 0.09, type: "triangle" });
  });
}

// ---------- optional speech ----------

function stopSpeech() {
  speechCancel();
}

/** Speaks `text` in the page language (Arabic included). Does nothing, silently, if the device has no matching voice. */
export function speak(text) {
  if (muted || !voiceEnabled || !text) return;
  speakParts([text], { lang: document.documentElement.lang, needVoice: true, volume: 0.8 }).catch(() => {});
}

// ---------- wiring ----------

document.addEventListener("click", (event) => {
  if (event.target.closest('[data-action="sound"]')) {
    unlock();
    toggleMuted();
    return;
  }
  if (event.target.closest('[data-i18n="capture.shutter"]')) playShutter();
});

document.addEventListener("wasteai:result", (event) => {
  const result = event.detail && event.detail.result;
  if (!result || result.status !== "ok" || !result.category) return;
  playSuccess();
  setTimeout(() => speak(result.category.name), 350); // let the chime finish first
});

// Error messages appear in the capture panel status line as keys on data-i18n.
new MutationObserver((records) => {
  for (const record of records) {
    const node = record.target;
    if (!node.classList || !node.classList.contains("capture__status")) continue;
    const key = node.dataset.i18n || "";
    if (key.startsWith("error.") || ERROR_KEYS.has(key)) playError();
  }
}).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["data-i18n"] });

document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopSpeech();
});
if ("speechSynthesis" in window && window.speechSynthesis.addEventListener) {
  window.speechSynthesis.addEventListener("voiceschanged", () => {}); // makes some browsers populate getVoices()
}

syncButtons();
