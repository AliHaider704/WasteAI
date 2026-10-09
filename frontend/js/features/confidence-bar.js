// File: frontend/js/features/confidence-bar.js
// F12: a meter next to the confidence word. The word stays; the bar never replaces it.
import { onCard } from "./card-hook.js";
export const styles = "result-visuals";

export default function init(ctx) {
  onCard((card, result) => {
    const word = card.querySelector(".result__confidence");
    if (!word || !result.category) return;
    const pct = Math.round(Number(result.category.confidence) * 100);
    if (!Number.isFinite(pct)) return;
    const meter = document.createElement("span");
    meter.className = "f-meter";
    meter.dataset.level = word.dataset.level || "";
    meter.setAttribute("role", "meter");
    meter.setAttribute("aria-valuemin", "0");
    meter.setAttribute("aria-valuemax", "100");
    meter.setAttribute("aria-valuenow", String(pct));
    meter.setAttribute("aria-valuetext", `${word.textContent} ${pct}%`);
    meter.setAttribute("aria-label", ctx.t("f.confidence-bar.label"));
    const fill = document.createElement("span");
    fill.className = "f-meter__fill";
    meter.append(fill);
    meter.style.setProperty("--v", `${Math.max(0, Math.min(100, pct))}%`);
    word.after(meter);
  });
}
