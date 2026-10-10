// File: frontend/js/features/read-aloud.js
// F15: read the category name and steps aloud, only when the user presses the button. Arabic and English.
// The button is always shown when the browser has speech. If the device has no voice for the language,
// the status line says what to do instead of the button silently disappearing.
import { onCard } from "./card-hook.js";
import { isMuted } from "../audio.js";
import { supported, speakParts, playClips, cancel } from "../speech.js";

// Server audio (built by scripts/make_audio.py) is tried first: it sounds the same on every device.
let manifest = null;
async function serverFiles(lang, id) {
  if (!id) return null;
  if (manifest === null) {
    try { const r = await fetch("audio/manifest.json", { cache: "no-cache" }); manifest = r.ok ? await r.json() : {}; }
    catch (err) { manifest = {}; }
  }
  const files = manifest[lang] && manifest[lang][id];
  return files && files.length ? files.map((f) => `audio/${f}`) : null;
}
export const styles = "comfort";

export default function init(ctx) {
  const { t } = ctx;
  if (!supported()) return;
  let btn = null;
  let status = null;
  let speaking = false;
  let run = 0; // id of the latest read, so a stale result cannot repaint

  function say(message) {
    if (status) status.textContent = message;
  }
  // The fix differs by system, so the message names the settings page to open.
  function noVoiceText() {
    const ua = navigator.userAgent || "";
    if (/Android|iPhone|iPad/.test(ua)) return t("f.read-aloud.no_voice");
    if (/Windows/.test(ua)) return t("f.read-aloud.no_voice_win");
    if (/Macintosh/.test(ua)) return t("f.read-aloud.no_voice_mac");
    return t("f.read-aloud.no_voice");
  }
  function paint() {
    if (!btn) return;
    btn.textContent = speaking ? t("f.read-aloud.stop") : t("f.read-aloud.start");
    btn.setAttribute("aria-pressed", String(speaking));
  }
  function stop(message = "") {
    run += 1;
    speaking = false;
    cancel();
    say(message);
    paint();
  }

  onCard((card, result) => {
    const list = card.querySelector(".result__steps");
    const name = card.querySelector(".result__name");
    if (!list || !name) return;
    btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.addEventListener("click", async () => {
      if (speaking) return stop();
      if (isMuted()) return say(t("f.read-aloud.muted"));
      const lang = document.documentElement.lang || "en";
      const parts = [name.textContent, ...[...list.querySelectorAll("li")].map((li) => li.textContent)];
      const mine = ++run;
      speaking = true;
      say(t("f.read-aloud.loading"));
      paint();
      const files = await serverFiles(lang.slice(0, 2), result && result.category && result.category.id);
      if (mine !== run) return;
      const onStart = () => mine === run && say("");
      let outcome = files ? await playClips(files, { onStart }) : "error";
      if (mine !== run) return;
      if (outcome === "error") outcome = await speakParts(parts, { lang, onStart });
      if (mine !== run) return;
      const result2 = outcome;
      speaking = false;
      say(result2 === "no-voice" ? noVoiceText() : result2 === "error" ? t("f.read-aloud.error") : "");
      paint();
    });
    status = document.createElement("p");
    status.className = "muted f-readstatus";
    status.setAttribute("role", "status");
    list.before(btn, status);
    paint();
  });

  ctx.on("i18n:change", () => stop());
  ctx.on("wasteai:route", () => stop());
  ctx.on("sound:change", (e) => { if (e.detail && e.detail.muted) stop(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
}
