// File: frontend/js/features/knowledge.js
// Shared helper for the "Good to know" block under the result (M32). One <details>, one section per feature.
import { store } from "../api.js";
import { getLang, setRich } from "../i18n.js";

const cache = {};

export function loadData(slug) {
  if (!cache[slug]) {
    cache[slug] = fetch(`data/${slug}.json`)
      .then((r) => (r.ok ? r.json() : { entries: [] }))
      .catch(() => ({ entries: [] }));
  }
  return cache[slug];
}

export function put(node, entry) {
  setRich(node, entry[getLang()] || "");
}

export function heading(text) {
  const h = document.createElement("h3");
  h.textContent = text;
  return h;
}

/** build(category, entries) returns a node, or null when there is nothing to show. */
export function mount(ctx, slug, build) {
  const host = ctx.slot("result");
  if (!host) return;
  let box = host.querySelector(".f-know");
  if (!box) {
    box = document.createElement("details");
    box.className = "f-card f-know";
    box.hidden = true;
    box.dataset.key = `f.${slug}.summary`;
    const body = document.createElement("div");
    body.className = "f-know__body";
    box.append(document.createElement("summary"), body);
    host.append(box);
  }
  const sec = document.createElement("div");
  sec.className = "f-know__s";
  sec.dataset.slug = slug;
  sec.hidden = true;
  box.querySelector(".f-know__body").append(sec);
  let current = store.result;

  async function render() {
    const category = current && current.category;
    sec.replaceChildren();
    sec.hidden = true;
    if (category) {
      const data = await loadData(slug);
      const node = build(category, data.entries || []);
      if (node) {
        sec.append(node);
        sec.hidden = false;
      }
    }
    box.querySelector("summary").textContent = ctx.t(box.dataset.key);
    box.hidden = ![...box.querySelectorAll(".f-know__s")].some((s) => !s.hidden);
  }

  ctx.on("wasteai:result", (e) => {
    current = e.detail && e.detail.result;
    render();
  });
  ctx.on("i18n:change", render);
  render();
}

/** "Source: <link>  Accessed <date>" line; the title is Latin, so it sits in <bdi dir="ltr">. */
export function sourceLine(ctx, slug, source) {
  const note = document.createElement("small");
  note.className = "muted f-source";
  if (!source || !source.url) return note;
  note.append(`${ctx.t(`f.${slug}.source`)} `);
  const a = document.createElement("a");
  a.href = source.url;
  a.rel = "noopener";
  const b = document.createElement("bdi");
  b.dir = "ltr";
  b.textContent = source.title || new URL(source.url).hostname;
  a.append(b);
  note.append(a);
  if (source.accessed) {
    const date = document.createElement("span");
    date.className = "f-source__date";
    date.textContent = ctx.t(`f.${slug}.accessed`, { date: source.accessed });
    note.append(date);
  }
  return note;
}
