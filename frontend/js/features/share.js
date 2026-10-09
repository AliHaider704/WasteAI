// File: frontend/js/features/share.js
// F14: share the result as plain text (name, bin, first step, address). Never a photo.
import { onCard } from "./card-hook.js";
export const styles = "result-visuals";

export default function init(ctx) {
  const { t } = ctx;
  onCard((card, result) => {
    const nameEl = card.querySelector(".result__name");
    const chip = card.querySelector(".result__stamp .bin");
    if (!result.category || !nameEl) return;
    const step = card.querySelector(".result__steps li");
    const vars = { name: nameEl.textContent, bin: chip ? chip.textContent : "", step: step ? step.textContent : "", url: location.origin + location.pathname };
    const text = t(step ? "f.share.text" : "f.share.text_short", vars);

    const box = document.createElement("div");
    box.className = "f-share";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.textContent = t("f.share.button");
    const status = document.createElement("p");
    status.className = "muted";
    status.setAttribute("role", "status");
    const area = document.createElement("textarea");
    area.readOnly = true;
    area.hidden = true;
    area.setAttribute("aria-label", t("f.share.area"));
    box.append(btn, status, area);

    btn.addEventListener("click", async () => {
      status.textContent = "";
      if (navigator.share) {
        try {
          await navigator.share({ text });
          return;
        } catch (err) {
          if (err && err.name === "AbortError") return;
        }
      }
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
          status.textContent = t("f.share.copied");
          return;
        }
      } catch (err) {
        // fall through to the manual text area
      }
      area.value = text;
      area.hidden = false;
      area.focus();
      area.select();
      status.textContent = t("f.share.manual");
    });

    const why = card.querySelector(".result__why");
    if (why) why.before(box);
    else card.append(box);
  });
}
