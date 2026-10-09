// File: frontend/js/features/facts.js
// F01: sourced facts only. No entry for a category means no card.
import { mount, put, heading } from "./knowledge.js";
import { getLang } from "../i18n.js";

export const styles = "knowledge";

export default function init(ctx) {
  mount(ctx, "facts", (cat, entries) => {
    const items = entries.filter((e) => (e.ids || []).includes(cat.id) || e.group === cat.group);
    if (!items.length) return null;
    const wrap = document.createElement("div");
    wrap.append(heading(ctx.t("f.facts.title")));
    items.forEach((entry) => {
      const p = document.createElement("p");
      put(p, entry);
      const src = entry.source || {};
      const note = document.createElement("small");
      note.className = "muted";
      if (src.url) {
        const a = document.createElement("a");
        a.href = src.url;
        a.rel = "noopener";
        a.textContent = (typeof src.title === "object" ? src.title[getLang()] : src.title) || new URL(src.url).hostname;
        note.append(a, " ");
      }
      if (src.accessed) note.append(ctx.t("f.facts.accessed", { date: src.accessed }));
      wrap.append(p, note);
    });
    return wrap;
  });
}
