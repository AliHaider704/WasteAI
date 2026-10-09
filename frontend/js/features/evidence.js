// File: frontend/js/features/evidence.js
// P06: inside Details mode, show how raw labels became the category: label, rule, category.
import { onCard } from "./card-hook.js";
import { getCategories } from "../api.js";
import { getLang, plain } from "../i18n.js";
import { loadLabels, labelFor, loadSourceNames, sourceName } from "../labels.js";
export const styles = true;

const NS = "http://www.w3.org/2000/svg";

// "source:label>category_id" or "group_fallback". Anything else is skipped.
function parseReason(list, finalId) {
  const rows = [];
  if (!Array.isArray(list)) return rows;
  list.forEach((item) => {
    if (typeof item !== "string") return;
    if (item === "group_fallback") {
      if (finalId) rows.push({ fallback: true, cat: finalId });
      return;
    }
    const colon = item.indexOf(":");
    const arrow = item.lastIndexOf(">");
    if (colon < 1 || arrow < colon + 2) return;
    const src = item.slice(0, colon);
    const label = item.slice(colon + 1, arrow);
    const cat = item.slice(arrow + 1).trim();
    if (src && label && cat) rows.push({ src, label, cat });
  });
  return rows;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function link(svg, a, b, wrap) {
  const w = wrap.getBoundingClientRect();
  const ra = a.getBoundingClientRect();
  const rb = b.getBoundingClientRect();
  let x1, y1, x2, y2, d;
  const sideways = rb.left >= ra.right - 1 || rb.right <= ra.left + 1;
  if (sideways) {
    const toRight = rb.left >= ra.right - 1;
    x1 = (toRight ? ra.right : ra.left) - w.left;
    x2 = (toRight ? rb.left : rb.right) - w.left;
    y1 = ra.top + ra.height / 2 - w.top;
    y2 = rb.top + rb.height / 2 - w.top;
    const mx = (x1 + x2) / 2;
    d = `M${x1} ${y1}C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`;
  } else {
    x1 = ra.left + ra.width / 2 - w.left;
    x2 = rb.left + rb.width / 2 - w.left;
    y1 = ra.bottom - w.top;
    y2 = rb.top - w.top;
    const my = (y1 + y2) / 2;
    d = `M${x1} ${y1}C${x1} ${my} ${x2} ${my} ${x2} ${y2}`;
  }
  return d;
}

export default function init(ctx) {
  const { t } = ctx;

  async function build(card, result, host) {
    const rows = parseReason(result.reason, result.category && result.category.id);
    if (!rows.length) return null;
    let cats = [];
    try {
      const data = await getCategories(getLang());
      cats = Array.isArray(data) ? data : (data && data.categories) || [];
    } catch (err) {
      cats = [];
    }
    await Promise.all([loadLabels(), loadSourceNames()]);
    if (!card.isConnected || !host.isConnected) return null;
    const catName = (id) => { const c = cats.find((x) => x.id === id); return c ? plain(c.name) : ""; };
    const srcLabel = (id) => sourceName(id) || id;

    const root = el("section", "f-evidence");
    root.append(el("h4", "f-evidence__title", t("f.evidence.title")));
    const board = el("div", "f-evidence__board");
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "f-evidence__lines");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    board.append(svg);

    const colSeen = el("div", "f-evidence__col");
    const colRule = el("div", "f-evidence__col");
    const colCat = el("div", "f-evidence__col");
    [[colSeen, "f.evidence.col_seen"], [colRule, "f.evidence.col_rule"], [colCat, "f.evidence.col_cat"]].forEach(([c, k]) => {
      c.append(el("p", "f-evidence__head", t(k)));
    });

    const catBoxes = new Map();
    const pairs = [];
    const plainList = el("ul", "f-list f-list--plain f-evidence__text");
    rows.forEach((r) => {
      const name = catName(r.cat) || r.cat;
      const seen = el("div", "f-evidence__box");
      const rule = el("div", "f-evidence__box");
      if (r.fallback) {
        seen.append(el("span", "f-evidence__tag", t("f.evidence.tag_group")));
        rule.textContent = t("f.evidence.rule_group");
      } else {
        const bdi = document.createElement("bdi");
        bdi.dir = "ltr";
        bdi.translate = false;
        bdi.textContent = srcLabel(r.src);
        seen.append(bdi, document.createElement("br"), labelFor(r.label));
        rule.textContent = t("f.evidence.rule");
      }
      let cb = catBoxes.get(r.cat);
      if (!cb) {
        cb = el("div", "f-evidence__box f-evidence__box--cat", name);
        catBoxes.set(r.cat, cb);
        colCat.append(cb);
      }
      colSeen.append(seen);
      colRule.append(rule);
      pairs.push([seen, rule], [rule, cb]);

      const li = document.createElement("li");
      if (r.fallback) {
        li.textContent = t("f.evidence.list_group", { cat: name });
      } else {
        li.append(t("f.evidence.list_item", { label: labelFor(r.label), cat: name }));
        const bdi = document.createElement("bdi");
        bdi.dir = "ltr";
        bdi.translate = false;
        bdi.textContent = srcLabel(r.src);
        li.prepend(bdi, " ");
      }
      plainList.append(li);
    });
    board.append(colSeen, colRule, colCat);
    root.append(board, plainList);
    host.append(root);

    const paths = pairs.map(() => {
      const p = document.createElementNS(NS, "path");
      p.setAttribute("pathLength", "1");
      p.setAttribute("fill", "none");
      svg.append(p);
      return p;
    });
    const draw = () => {
      const w = board.getBoundingClientRect();
      svg.setAttribute("width", String(Math.round(w.width)));
      svg.setAttribute("height", String(Math.round(w.height)));
      svg.setAttribute("viewBox", `0 0 ${Math.round(w.width)} ${Math.round(w.height)}`);
      pairs.forEach(([a, b], i) => paths[i].setAttribute("d", link(svg, a, b, board)));
    };
    draw();
    if (!result.hazard) requestAnimationFrame(() => root.classList.add("is-drawn"));
    else root.classList.add("is-static");
    if ("ResizeObserver" in window) new ResizeObserver(draw).observe(board);
    return root;
  }

  onCard((card, result) => {
    const why = card.querySelector(".result__why");
    if (!why) return;
    const attach = () => {
      const box = why.querySelector(".f-details");
      if (!box || box.querySelector(".f-evidence") || box.dataset.evidence === "1") return;
      box.dataset.evidence = "1";
      build(card, result, box).catch(() => {});
    };
    new MutationObserver(attach).observe(why, { childList: true });
    attach();
  });
}
