// File: frontend/js/features/capture-tools.js
// Shared helpers for the M34 capture assistants (not a feature slug: no flag, no trigger).
import { activeCamera } from "../camera.js";

const SVG = "http://www.w3.org/2000/svg";

export const panel = () => document.querySelector(".capture");

/** Inline SVG icon from path data; decorative (the button carries the name). */
export function icon(d) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "ct-icon");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", d);
  svg.append(path);
  return svg;
}

function bar() {
  let node = document.querySelector(".ct-bar");
  if (node) return node;
  node = document.createElement("div");
  node.className = "ct-bar";
  node.hidden = true;
  const host = panel();
  const buttons = host && host.querySelector(".actions");
  if (host && buttons) host.insertBefore(node, buttons);
  else (document.getElementById("slot-capture") || document.body).append(node);
  const sync = () => {
    const live = Boolean(activeCamera());
    node.hidden = !live || !Array.from(node.children).some((c) => !c.hidden);
  };
  document.addEventListener("wasteai:capture", sync);
  node.sync = sync;
  return node;
}

/** Adds a tool button at a fixed position (DOM order = visual order = Tab order). */
export function addTool(order, button) {
  const node = bar();
  button.dataset.order = String(order);
  button.classList.add("ct-btn");
  node.append(button);
  Array.from(node.children).sort((a, b) => a.dataset.order - b.dataset.order).forEach((c) => node.append(c));
  node.sync();
  return node;
}

let live = null;
/** One polite live region for all capture tools. */
export function say(text) {
  if (!live) {
    live = document.createElement("p");
    live.className = "ct-live";
    live.setAttribute("role", "status");
    live.setAttribute("aria-live", "polite");
    (document.getElementById("slot-capture") || document.body).append(live);
  }
  live.textContent = "";
  setTimeout(() => { live.textContent = text; }, 50);
}

export const syncBar = () => { const n = document.querySelector(".ct-bar"); if (n && n.sync) n.sync(); };
