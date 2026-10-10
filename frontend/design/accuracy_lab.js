// File: frontend/design/accuracy_lab.js
// Dev-only. No network calls except loading the category list.
const $ = (id) => document.getElementById(id);
const MIN_PER_CAT = 3;
let cats = [];
let items = []; // {file, url, cat}
let i = 0;

async function loadCats() {
  for (const url of ["/api/v1/categories?lang=en", "../mock/categories.json"]) {
    try {
      const r = await fetch(url, { cache: "no-store" });
      if (!r.ok) continue;
      const d = await r.json();
      if (d.categories && d.categories.length) return d.categories;
    } catch (e) { /* try next */ }
  }
  return [];
}

function buildSelect() {
  const sel = $("cat");
  sel.replaceChildren(new Option("-- choose --", ""));
  const groups = new Map();
  for (const c of cats) {
    if (!groups.has(c.group)) {
      const g = document.createElement("optgroup");
      g.label = c.group;
      groups.set(c.group, g);
      sel.append(g);
    }
    groups.get(c.group).append(new Option(`${c.name} (${c.id})`, c.id));
  }
}

function counts() {
  const m = new Map(cats.map((c) => [c.id, 0]));
  for (const it of items) if (it.cat) m.set(it.cat, (m.get(it.cat) || 0) + 1);
  return m;
}

function renderCounts() {
  const m = counts();
  const body = $("counts").tBodies[0];
  body.replaceChildren();
  const low = [];
  for (const [id, n] of m) {
    const tr = body.insertRow();
    tr.insertCell().textContent = id;
    tr.insertCell().textContent = n;
    if (n < MIN_PER_CAT) { tr.className = "low"; low.push(id); }
  }
  const done = items.filter((x) => x.cat).length;
  $("total").textContent = `Labelled ${done} of ${items.length} photos (target 100 or more).`;
  $("warn").textContent = low.length
    ? `Fewer than ${MIN_PER_CAT} photos: ${low.join(", ")}`
    : items.length ? "Every category has enough photos." : "";
}

function show() {
  if (!items.length) return;
  const it = items[i];
  $("work").hidden = false;
  $("img").src = it.url;
  $("fname").textContent = it.file.name;
  $("pos").textContent = `Photo ${i + 1} of ${items.length}`;
  $("cat").value = it.cat || "";
  $("back").disabled = i === 0;
  $("next").disabled = i === items.length - 1;
  renderCounts();
}

function go(d) {
  const n = i + d;
  if (n >= 0 && n < items.length) { i = n; show(); }
}

function csvCell(s) {
  return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}

function download() {
  const rows = items.filter((x) => x.cat);
  if (!rows.length) { $("warn").textContent = "Nothing labelled yet."; return; }
  const names = new Set();
  const dup = rows.filter((r) => (names.has(r.file.name) ? true : (names.add(r.file.name), false)));
  if (dup.length) {
    $("warn").textContent = `Duplicate file names (rename first): ${dup.map((d) => d.file.name).join(", ")}`;
    return;
  }
  const text = ["filename,category_id", ...rows.map((r) => `${csvCell(r.file.name)},${r.cat}`)].join("\n") + "\n";
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "eval_labels.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

$("files").addEventListener("change", (e) => {
  items.forEach((x) => URL.revokeObjectURL(x.url));
  items = [...e.target.files].map((f) => ({ file: f, url: URL.createObjectURL(f), cat: "" }));
  i = 0;
  show();
  renderCounts();
});

$("cat").addEventListener("change", () => {
  items[i].cat = $("cat").value;
  if ($("cat").value && i < items.length - 1) { i += 1; }
  show();
  $("cat").focus();
});
$("back").addEventListener("click", () => go(-1));
$("next").addEventListener("click", () => go(1));
$("skip").addEventListener("click", () => { items[i].cat = ""; show(); });
$("csv").addEventListener("click", download);
document.addEventListener("keydown", (e) => {
  if (document.activeElement === $("cat") || !items.length) return;
  if (e.key === "ArrowRight") go(1);
  if (e.key === "ArrowLeft") go(-1);
});

cats = await loadCats();
if (!cats.length) $("warn").textContent = "Could not load categories (API and mock both failed).";
buildSelect();
renderCounts();
