// File: frontend/js/features/timer.js
// F09: shutter countdown (off, 3, 5 s). Relevance: lets the user step back and hold the item still.
import { addTool, icon, panel, say } from "./capture-tools.js";
export const styles = "capture-tools";

const CHOICES = [0, 3, 5];

export default function init(ctx) {
  const host = panel();
  const shutter = host && Array.from(host.querySelectorAll("button")).find((b) => b.dataset.i18n === "capture.shutter");
  if (!shutter) return;

  let index = Math.max(0, CHOICES.indexOf(ctx.store.get("timer", 0)));
  let remaining = 0;
  let tick = null;
  let bypass = false;

  const btn = document.createElement("button");
  btn.type = "button";
  const num = document.createElement("span");
  num.className = "ct-num";
  btn.append(icon("M12 21a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM12 9v4l3 2M9 2h6"), num);
  const count = document.createElement("p");
  count.className = "ct-count";
  count.setAttribute("aria-hidden", "true"); // the live region speaks; the digit is only for the eyes
  count.hidden = true;
  const video = host.querySelector("video");
  video.after(count);

  function render() {
    const value = CHOICES[index];
    const label = value ? ctx.t("f.timer.label_on", { n: value }) : ctx.t("f.timer.label_off");
    btn.setAttribute("aria-label", label);
    btn.title = label;
    btn.setAttribute("aria-pressed", String(value > 0));
    num.textContent = value ? String(value) : "";
  }

  function stop(announce) {
    if (tick) clearInterval(tick);
    tick = null;
    count.hidden = true;
    shutter.disabled = false;
    if (announce) say(ctx.t("f.timer.cancelled"));
  }

  function finish() {
    stop(false);
    bypass = true;
    shutter.click(); // the normal path: photo, shutter tick (only when sound is on), camera release
    bypass = false;
  }

  function start() {
    remaining = CHOICES[index];
    count.textContent = String(remaining);
    count.hidden = false;
    shutter.disabled = true;
    say(ctx.t("f.timer.start", { n: remaining }));
    tick = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) return finish();
      count.textContent = String(remaining);
    }, 1000);
  }

  // Capture phase on the panel runs before the shutter's own handler and the sound cue.
  host.addEventListener("click", (e) => {
    if (bypass || !CHOICES[index] || !e.target.closest("button") || e.target.closest("button") !== shutter) return;
    e.stopPropagation();
    e.preventDefault();
    if (!tick) start();
  }, true);
  // Escape cancels the countdown only; the panel stays open.
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && tick) {
      e.stopPropagation();
      stop(true);
    }
  }, true);
  document.addEventListener("wasteai:capture", (e) => {
    const s = e.detail && e.detail.stage;
    if (tick && s !== "camera") stop(false); // panel closed, photo taken elsewhere, camera off
  });
  btn.addEventListener("click", () => {
    index = (index + 1) % CHOICES.length;
    ctx.store.set("timer", CHOICES[index]);
    render();
  });

  addTool(2, btn);
  ctx.on("i18n:change", render);
  render();
}
