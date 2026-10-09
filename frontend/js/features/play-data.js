// File: frontend/js/features/play-data.js
// Shared helpers for the Sorting Record, stamps and weekly goal (M41, D-044). Hazard ids never count.
export const HAZARD = new Set(["battery", "hazardous_chemical", "medical", "ewaste_small", "ewaste_large"]);

/** Records one ok, non-hazard result once per request id. Returns {data, isNew} or null. */
export function noteResult(ctx, res) {
  if (!res || !res.rid || HAZARD.has(res.id)) return null;
  const d = ctx.store.get("record", null) || { cats: {}, seen: [], lastNew: "", total: 0 };
  if (d.seen.includes(res.rid)) return { data: d, isNew: d.lastNew === res.rid };
  d.seen = [res.rid, ...d.seen].slice(0, 30);
  d.total = (d.total || 0) + 1;
  let isNew = false;
  if (d.cats[res.id]) {
    d.cats[res.id].n += 1;
  } else {
    d.cats[res.id] = { n: 1, first: Date.now() };
    d.lastNew = res.rid;
    isNew = true;
  }
  ctx.store.set("record", d);
  return { data: d, isNew };
}

/** Local Monday of the current week: a stable key and a number that moves once per week. */
export function weekInfo(now = new Date()) {
  const back = (now.getDay() + 6) % 7;
  const mon = new Date(now.getFullYear(), now.getMonth(), now.getDate() - back);
  const key = `${mon.getFullYear()}-${mon.getMonth() + 1}-${mon.getDate()}`;
  const days = Math.round(Date.UTC(mon.getFullYear(), mon.getMonth(), mon.getDate()) / 864e5);
  return { key, index: Math.floor(days / 7) };
}
