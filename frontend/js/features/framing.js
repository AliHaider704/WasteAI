// File: frontend/js/features/framing.js
// F07: optional guide frame over the live camera. Relevance: corner marks show where to place the item.
import { addTool, icon, panel, syncBar } from "./capture-tools.js";
export const styles = "capture-tools";

const KEY = "framing";

export default function init(ctx) {
  const host = panel();
  const video = host && host.querySelector("video");
  if (!host || !video) return;

  let on = ctx.store.get(KEY, false) === true;
  const frame = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  frame.setAttribute("class", "ct-frame");
  frame.setAttribute("viewBox", "0 0 100 100");
  frame.setAttribute("preserveAspectRatio", "none");
  frame.setAttribute("aria-hidden", "true");
  const marks = document.createElementNS("http://www.w3.org/2000/svg", "path");
  marks.setAttribute("d", "M0 14V0h10M90 0h10v14M100 86v14H90M10 100H0V86");
  frame.append(marks);
  frame.setAttribute("hidden", "");
  video.after(frame);

  const btn = document.createElement("button");
  btn.type = "button";
  btn.append(icon("M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"));
  btn.addEventListener("click", () => {
    on = !on;
    ctx.store.set(KEY, on);
    render();
  });

  function place() {
    host.style.setProperty("--ct-top", `${video.offsetTop}px`);
    host.style.setProperty("--ct-height", `${video.offsetHeight}px`);
  }
  function render() {
    const label = ctx.t("f.framing.label");
    btn.setAttribute("aria-label", label);
    btn.title = label;
    btn.setAttribute("aria-pressed", String(on));
    frame.toggleAttribute("hidden", !(on && !video.hidden));
    if (!frame.hasAttribute("hidden")) place();
  }

  addTool(1, btn);
  new ResizeObserver(render).observe(video);
  document.addEventListener("wasteai:capture", () => { render(); syncBar(); });
  ctx.on("i18n:change", render);
  render();
}
