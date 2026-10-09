// File: frontend/js/features/favorites.js
import { catalog, plain, lang, slotEl, resultOf, card } from "./personal-data.js";

const MAX = 20;

export default function init(ctx) {
  const browse = slotEl(ctx, "browse");
  const resultSlot = slotEl(ctx, "result");
  const read = () => ctx.store.get("favorites", []);
  let current = null;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn f-fav-btn";
  btn.hidden = true;
  resultSlot?.append(btn);

  const list = browse ? card(browse, "f-favorites") : null;

  function toggle(id) {
    const f = read();
    ctx.store.set("favorites", f.includes(id) ? f.filter((x) => x !== id) : [id, ...f].slice(0, MAX));
    render();
  }

  async function render() {
    const f = read();
    if (current) {
      const on = f.includes(current);
      btn.hidden = false;
      btn.setAttribute("aria-pressed", String(on));
      btn.textContent = ctx.t(on ? "f.favorites.remove" : "f.favorites.add");
    }
    if (!list) return;
    const cat = await catalog(lang(ctx));
    list.sum.textContent = ctx.t("f.favorites.title");
    list.body.replaceChildren();
    if (!f.length) {
      const p = document.createElement("p");
      p.textContent = ctx.t("f.favorites.empty");
      list.body.append(p);
      return;
    }
    const ul = document.createElement("ul");
    ul.className = "f-list";
    for (const id of f) {
      const name = plain(cat.get(id)?.name) || ctx.t("f.favorites.unknown");
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "#/browse?q=" + encodeURIComponent(name);
      a.textContent = name;
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "btn";
      rm.textContent = ctx.t("f.favorites.remove");
      rm.addEventListener("click", () => toggle(id));
      li.append(a, " ", rm);
      ul.append(li);
    }
    list.body.append(ul);
  }

  btn.addEventListener("click", () => current && toggle(current));
  document.addEventListener("wasteai:result", (ev) => {
    current = resultOf(ev)?.id || null;
    if (!current) btn.hidden = true;
    render();
  });
  document.addEventListener("i18n:change", render);
  render();
}
