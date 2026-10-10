// File: frontend/js/features/read-aloud.js
// F15: read the category name and steps aloud, only when the user presses the button. Arabic and English.
// The button is always shown when the browser has speech. If the device has no voice for the language,
// the status line says what to do instead of the button silently disappearing.
import { onCard } from "./card-hook.js";
import { isMuted } from "../audio.js";
import { supported, speakParts, cancel } from "../speech.js";
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

  onCard((card) => {
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
      const result = await speakParts(parts, { lang, onStart: () => mine === run && say("") });
      if (mine !== run) return;
      speaking = false;
      say(result === "no-voice" ? t("f.read-aloud.no_voice") : result === "error" ? t("f.read-aloud.error") : "");
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
