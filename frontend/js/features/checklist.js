// File: frontend/js/features/checklist.js
// F05: before-you-drop checkboxes per group. State is not saved.
import { store } from "../api.js";
import { getLang } from "../i18n.js";
import { mount, put, heading } from "./knowledge.js";

export const styles = "knowledge";
let seq = 0;

export default function init(ctx) {
  mount(ctx, "checklist", (cat, entries) => {
    const items = entries.filter((e) => e.group === cat.group);
    if (!items.length) return null;
    const wrap = document.createElement("div");
    const list = document.createElement("ul");
    list.className = "f-list f-list--check";
    const boxes = [];
    items.forEach((entry) => {
      const li = document.createElement("li");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.id = `f-chk-${(seq += 1)}`;
      const label = document.createElement("label");
      label.htmlFor = box.id;
      const main = document.createElement("span");
      put(main, entry);
      label.append(main);
      if (entry.why) {
        const why = document.createElement("small");
        why.className = "muted";
        why.textContent = entry.why[getLang()] || "";
        label.append(why);
      }
      box.addEventListener("change", update);
      boxes.push(box);
      li.append(box, label);
      list.append(li);
    });

    const bar = document.createElement("progress");
    bar.className = "f-check__bar";
    bar.max = items.length;
    const count = document.createElement("span");
    count.className = "f-check__count";
    const verdict = document.createElement("p");
    verdict.className = "f-check__verdict";
    verdict.setAttribute("role", "status");
    const head = document.createElement("div");
    head.className = "f-check__head";
    head.append(count, bar);

    function update() {
      const done = boxes.filter((b) => b.checked).length;
      bar.value = done;
      count.textContent = ctx.t("f.checklist.progress", { done, total: boxes.length });
      const binId = store.result && store.result.guidance && store.result.guidance.bin;
      const ready = done === boxes.length;
      verdict.dataset.ready = String(ready);
      verdict.textContent = ready && binId ? ctx.t("f.checklist.ready", { bin: ctx.t(`bin.${binId}`) }) : ready ? ctx.t("f.checklist.ready_plain") : ctx.t("f.checklist.pending");
    }
    update();

    wrap.append(heading(ctx.t("f.checklist.title")), head, list, verdict);
    return wrap;
  });
}
