// File: frontend/js/features/journey.js
// F02: three neutral stages after the bin, from the EPA recycling overview. Recyclable groups only.
import { mount, put, heading, sourceLine } from "./knowledge.js";

export const styles = "lifecycle";

export default function init(ctx) {
  mount(ctx, "journey", (cat, entries) => {
    const stages = entries.filter((e) => (e.groups || []).includes(cat.group));
    if (!stages.length || cat.hazard) return null;
    const wrap = document.createElement("div");
    const list = document.createElement("ol");
    list.className = "f-list f-list--plain";
    stages.forEach((stage) => {
      const li = document.createElement("li");
      put(li, stage);
      list.append(li);
    });
    wrap.append(heading(ctx.t("f.journey.title")), list, sourceLine(ctx, "journey", stages[0].source));
    return wrap;
  });
}
