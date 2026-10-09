// File: frontend/js/features/badges.js
// Sorting stamps: a bin-style rectangle for a category sorted for the first time. No hazard stamps, no rewards.
import { catalog, plain, lang, slotEl, resultOf } from "./personal-data.js";
import { noteResult } from "./play-data.js";
export const styles = "badges";

export default function init(ctx) {
  const host = slotEl(ctx, "result");
  if (!host) return;
  const box = document.createElement("p");
  box.className = "f-new-stamp";
  box.setAttribute("role", "status");
  box.hidden = true;
  host.append(box);
  let shown = null;

  async function paint() {
    box.replaceChildren();
    if (!shown) {
      box.hidden = true;
      return;
    }
    const cat = await catalog(lang(ctx));
    const s = document.createElement("span");
    s.className = `bin bin--${cat.get(shown)?.bin || "grey"} f-stamp`;
    s.textContent = plain(cat.get(shown)?.name) || shown;
    box.append(ctx.t("f.badges.new") + " ", s);
    box.hidden = false;
  }

  document.addEventListener("wasteai:result", (ev) => {
    const r = resultOf(ev);
    const out = r ? noteResult(ctx, r) : null;
    shown = out && out.isNew ? r.id : null;
    paint();
  });
  document.addEventListener("i18n:change", paint);
}
