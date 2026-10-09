// File: frontend/js/features/evaporate.js
// Photo removal with honest wording (M43, P08, D-045). It only removes the preview from this screen:
// the photo was never stored on the server. No animation beyond a plain fade; none on hazard results.
import { slotEl } from "./personal-data.js";
import { HAZARD } from "./play-data.js";
export const styles = "evaporate";

export default function init(ctx) {
  document.addEventListener("wasteai:result", (ev) => {
    const d = ev.detail || {};
    const id = d.result && d.result.category && d.result.category.id;
    const out = slotEl(ctx, "result");
    out?.querySelector(".f-evap")?.remove();
    if (!out || !d.photoUrl || (id && HAZARD.has(id))) return;
    const url = d.photoUrl;
    const wrap = document.createElement("div");
    wrap.className = "f-evap";
    const note = document.createElement("p");
    note.setAttribute("role", "status");
    note.textContent = ctx.t("f.evaporate.note");
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn";
    b.textContent = ctx.t("f.evaporate.button");
    b.addEventListener("click", () => {
      const img = document.querySelector(".result__photo");
      const finish = () => {
        img?.remove();
        URL.revokeObjectURL(url); // the only copy in this browser tab
        b.remove();
        note.textContent = ctx.t("f.evaporate.done");
      };
      if (img && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        img.classList.add("f-evap__fade");
        img.addEventListener("transitionend", finish, { once: true });
        setTimeout(finish, 600);
      } else finish();
    });
    wrap.append(note, b);
    out.append(wrap);
  });
}
