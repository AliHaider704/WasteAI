// File: frontend/js/features/two-sources.js
// F16 / P01: when the sources disagree, say plainly what each one saw and what the system did.
import { onCard } from "./card-hook.js";
import { getCategories } from "../api.js";
import { getLang, plain } from "../i18n.js";
import { loadLabels, labelFor, loadSourceNames, sourceName } from "../labels.js";
export const styles = "explain";

function parseReason(list) {
  const map = {};
  (Array.isArray(list) ? list : []).forEach((item) => {
    if (typeof item !== "string") return;
    const colon = item.indexOf(":");
    const arrow = item.lastIndexOf(">");
    if (colon < 1 || arrow < colon) return;
    const src = item.slice(0, colon);
    const cat = item.slice(arrow + 1).trim();
    if (cat) (map[src] = map[src] || new Set()).add(cat);
  });
  return map;
}

export default function init(ctx) {
  const { t } = ctx;
  onCard(async (card, result) => {
    const sources = (result.sources || []).filter((s) => s.ok && s.top && s.top.length);
    const differ = result.agreement === "none" || result.agreement === "partial" || result.status === "uncertain";
    if (!differ || !sources.length) return;
    let cats = [];
    try {
      const data = await getCategories(getLang());
      cats = Array.isArray(data) ? data : (data && data.categories) || [];
    } catch (err) {
      cats = [];
    }
    await Promise.all([loadLabels(), loadSourceNames()]);
    if (!card.isConnected) return;
    const reasons = parseReason(result.reason);
    const catName = (id) => { const c = cats.find((x) => x.id === id); return c ? plain(c.name) : ""; };

    const box = document.createElement("details");
    box.className = "f-explain";
    const sum = document.createElement("summary");
    sum.textContent = t("f.two-sources.summary");
    box.append(sum);
    const list = document.createElement("ul");
    list.className = "f-list f-list--plain";
    sources.forEach((s) => {
      const li = document.createElement("li");
      const strong = document.createElement("strong");
      const real = sourceName(s.name);
      if (real) {
        const bdi = document.createElement("bdi");
        bdi.dir = "ltr";
        bdi.translate = false;
        bdi.textContent = real;
        strong.append(bdi);
      } else {
        strong.textContent = t(`source.${s.name}`);
      }
      li.append(strong, document.createElement("br"));
      const saw = s.top.map((l) => labelFor(l.label)).join(", ");
      li.append(t("f.two-sources.saw", { list: saw }));
      const mapped = [...(reasons[s.name] || [])].map(catName).filter(Boolean);
      if (mapped.length) {
        li.append(document.createElement("br"), t("f.two-sources.mapped", { list: mapped.join(", ") }));
      }
      list.append(li);
    });
    const close = document.createElement("p");
    close.textContent = t(result.status === "uncertain" ? "f.two-sources.closing_unsure" : "f.two-sources.closing_used");
    box.append(list, close);
    const why = card.querySelector(".result__why");
    if (why) why.before(box);
    else card.append(box);
  });
}
