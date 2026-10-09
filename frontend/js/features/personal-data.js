// File: frontend/js/features/personal-data.js
import { getCategories } from "../api.js";

export const plain = (s) => String(s ?? "").replace(/<[^>]*>/g, "");
export const lang = (ctx) => (typeof ctx.lang === "function" ? ctx.lang() : ctx.lang) || document.documentElement.lang || "en";
export const slotEl = (ctx, n) => (typeof ctx.slot === "function" ? ctx.slot(n) : null) || document.getElementById("slot-" + n);

const cache = {};
export function catalog(l) {
  if (!cache[l]) {
    cache[l] = getCategories(l)
      .then((d) => new Map((Array.isArray(d) ? d : d?.categories || []).map((c) => [c.id, c])))
      .catch(() => { delete cache[l]; return new Map(); });
  }
  return cache[l];
}

/** Returns {id, rid} for a result event, or null (uncertain, error, no category). */
export function resultOf(ev) {
  const r = ev?.detail?.result ?? ev?.detail;
  const id = r && r.status === "ok" ? r.category?.id : null;
  return id ? { id, rid: r.request_id || "" } : null;
}

export function when(ctx, ts) {
  const l = lang(ctx) === "ar" ? "ar-u-nu-latn" : lang(ctx);
  return new Intl.DateTimeFormat(l, { dateStyle: "short", timeStyle: "short" }).format(new Date(ts));
}

/** Confirm dialog: Cancel has default focus, Escape closes, focus returns to opener. */
export function confirmDialog(opener, text, yesLabel, noLabel, onYes) {
  const d = document.createElement("dialog");
  d.className = "f-dialog";
  const p = document.createElement("p");
  p.textContent = text;
  const no = document.createElement("button");
  const yes = document.createElement("button");
  [no, yes].forEach((b) => { b.type = "button"; b.className = "btn"; });
  no.textContent = noLabel;
  yes.textContent = yesLabel;
  no.autofocus = true;
  no.addEventListener("click", () => d.close());
  yes.addEventListener("click", () => { d.close(); onYes(); });
  d.addEventListener("close", () => { d.remove(); opener?.focus(); });
  d.append(p, no, yes);
  document.body.append(d);
  d.showModal();
}

export function card(host, cls) {
  const box = document.createElement("details");
  box.className = "f-card f-personal " + cls;
  const sum = document.createElement("summary");
  const body = document.createElement("div");
  box.append(sum, body);
  host.append(box);
  return { box, sum, body };
}
