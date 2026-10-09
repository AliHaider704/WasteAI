// File: frontend/js/features/checklist.js
// F05: before-you-drop checkboxes per group. State is not saved.
import { mount, put, heading } from "./knowledge.js";

export const styles = "knowledge";
let seq = 0;

export default function init(ctx) {
  mount(ctx, "checklist", (cat, entries) => {
    const items = entries.filter((e) => e.group === cat.group);
    if (!items.length) return null;
    const wrap = document.createElement("div");
    const list = document.createElement("ul");
    list.className = "f-list";
    items.forEach((entry) => {
      const li = document.createElement("li");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.id = `f-chk-${(seq += 1)}`;
      const label = document.createElement("label");
      label.htmlFor = box.id;
      put(label, entry);
      li.append(box, label);
      list.append(li);
    });
    wrap.append(heading(ctx.t("f.checklist.title")), list);
    return wrap;
  });
}
