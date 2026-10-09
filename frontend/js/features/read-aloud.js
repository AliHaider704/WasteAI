// File: frontend/js/features/read-aloud.js
// F15: read the category name and steps aloud, only when the user presses the button.
// No voice for the page language, or sound off: the button is not shown.
import { onCard } from "./card-hook.js";
import { isMuted } from "../audio.js";
export const styles = "comfort";

export default function init(ctx) {
  const { t } = ctx;
  const syn = window.speechSynthesis;
  if (!syn || typeof SpeechSynthesisUtterance === "undefined") return;
  let current = null;
  let speaking = false;

  const hasVoice = () => {
    const code = document.documentElement.lang.slice(0, 2).toLowerCase();
    return (syn.getVoices() || []).some((v) => String(v.lang).toLowerCase().startsWith(code));
  };
  function paint() {
    if (!current) return;
    current.hidden = isMuted() || !hasVoice();
    current.textContent = t(speaking ? "f.read-aloud.stop" : "f.read-aloud.start");
    current.setAttribute("aria-pressed", String(speaking));
  }
  function stop() {
    speaking = false;
    try { syn.cancel(); } catch (err) { /* ignore */ }
    paint();
  }

  onCard((card) => {
    const list = card.querySelector(".result__steps");
    const name = card.querySelector(".result__name");
    if (!list || !name) return;
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn";
    current = b;
    b.addEventListener("click", () => {
      if (speaking) return stop();
      const code = document.documentElement.lang.slice(0, 2).toLowerCase();
      const voice = (syn.getVoices() || []).find((v) => String(v.lang).toLowerCase().startsWith(code));
      if (!voice) return paint();
      const parts = [name.textContent, ...[...list.querySelectorAll("li")].map((li) => li.textContent)];
      const u = new SpeechSynthesisUtterance(parts.join(". "));
      u.voice = voice;
      u.lang = voice.lang;
      u.volume = 0.8;
      u.rate = 0.95;
      u.onend = u.onerror = () => { speaking = false; paint(); };
      speaking = true;
      paint();
      try { syn.speak(u); } catch (err) { stop(); }
    });
    list.before(b);
    paint();
  });

  if (syn.addEventListener) syn.addEventListener("voiceschanged", paint);
  ctx.on("i18n:change", stop);
  ctx.on("wasteai:route", stop);
  ctx.on("sound:change", (e) => { if (e.detail && e.detail.muted) stop(); else paint(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
}
