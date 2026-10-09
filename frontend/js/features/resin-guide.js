// File: frontend/js/features/resin-guide.js
// F04: the seven resin codes, shown for plastic results; the current one is marked.
import { mount, put, heading } from "./knowledge.js";

export const styles = "knowledge";

export default function init(ctx) {
  mount(ctx, "resin-guide", (cat, entries) => {
    if (cat.group !== "plastics" || !entries.length) return null;
    const wrap = document.createElement("div");
    const list = document.createElement("ul");
    list.className = "f-list f-list--plain";
    entries.forEach((entry) => {
      const li = document.createElement("li");
      put(li, entry);
      if ((entry.ids || []).includes(cat.id)) li.setAttribute("aria-current", "true");
      list.append(li);
    });
    wrap.append(heading(ctx.t("f.resin-guide.title")), list);
    return wrap;
  });
}
