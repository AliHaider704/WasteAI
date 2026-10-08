// File: frontend/js/dropzone.js
// Full-screen drop overlay shown while files are dragged over the page. Text comes from i18n keys only.

import { t } from "./i18n.js";

const root = document.createElement("div");
root.className = "dropzone";
root.hidden = true;
root.setAttribute("aria-hidden", "true");

function part(tag, cls, key) {
  const n = document.createElement(tag);
  n.className = cls;
  n.dataset.i18n = key;
  n.textContent = t(key);
  return n;
}

const frame = document.createElement("div");
frame.className = "dropzone__frame";
const stamp = document.createElement("span");
stamp.className = "dropzone__stamp";
stamp.innerHTML = '<svg class="icon" aria-hidden="true"><use href="assets/icons.svg#upload"></use></svg>';
stamp.append(part("span", "", "drop.stamp"));
frame.append(stamp, part("p", "dropzone__title", "drop.title"), part("p", "dropzone__hint", "drop.hint"));
root.append(frame);
document.body.append(root);

let depth = 0;
const hasFiles = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files");
const show = (on) => { root.hidden = !on; document.documentElement.classList.toggle("is-dropping", on); };

window.addEventListener("dragenter", (e) => { if (hasFiles(e)) { depth += 1; show(true); } });
window.addEventListener("dragleave", (e) => { if (hasFiles(e) && --depth <= 0) { depth = 0; show(false); } });
["drop", "dragend"].forEach((type) => window.addEventListener(type, () => { depth = 0; show(false); }));
document.addEventListener("i18n:change", () => root.querySelectorAll("[data-i18n]").forEach((n) => (n.textContent = t(n.dataset.i18n))));
