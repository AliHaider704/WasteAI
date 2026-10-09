// File: frontend/js/features/mistakes.js
// F06: common mistakes per group.
import { mount, put, heading } from "./knowledge.js";

export const styles = "knowledge";

export default function init(ctx) {
  mount(ctx, "mistakes", (cat, entries) => {
    const items = entries.filter((e) => e.group === cat.group);
    if (!items.length) return null;
    const wrap = document.createElement("div");
    const list = document.createElement("ul");
    list.className = "f-list f-list--plain";
    items.forEach((entry) => {
      const li = document.createElement("li");
      put(li, entry);
      list.append(li);
    });
    wrap.append(heading(ctx.t("f.mistakes.title")), list);
    return wrap;
  });
}
