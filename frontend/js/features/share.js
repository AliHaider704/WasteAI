// File: frontend/js/features/share.js
// F14: share the result as an image card (PNG drawn on a canvas: name, bin, first steps, link). Never the user's photo.
// Order of attempts: native share sheet with the file, then preview + save/copy, then plain text.
import { onCard } from "./card-hook.js";
import { store } from "../api.js";
export const styles = "result-visuals";

const SITE_URL = "https://wasteai.duckdns.org/";
const W = 1080;
const H = 1620;
const PAD = 84;
// The image is always drawn on the light palette so a shared card looks the same for everyone.
const C = { kraft: "#E9E1D3", paper: "#F6F1E6", ink: "#25221D", muted: "#5A5348", border: "#C9BFAB", accent: "#23405E", dangerBg: "#FBE0DC", dangerText: "#9A1B14" };
const SANS = '"Plex Sans", "Plex Sans Arabic", system-ui, sans-serif';
const SERIF = '"Newsreader", "Noto Naskh Arabic", Georgia, serif';

function wrap(ctx, text, maxWidth, maxLines) {
  const words = String(text).split(/\s+/).filter(Boolean);
  const lines = [];
  let line = "";
  for (const w of words) {
    const next = line ? `${line} ${w}` : w;
    if (line && ctx.measureText(next).width > maxWidth) {
      lines.push(line);
      line = w;
    } else line = next;
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) {
    lines.length = maxLines;
    let last = lines[maxLines - 1];
    while (last.length > 1 && ctx.measureText(`${last}…`).width > maxWidth) last = last.slice(0, -1);
    lines[maxLines - 1] = `${last}…`;
  }
  return lines;
}

async function loadFonts(strings) {
  if (!document.fonts || !document.fonts.load) return;
  const sample = strings.join(" ");
  await Promise.all(
    [`600 100px ${SERIF}`, `600 40px ${SANS}`, `400 40px ${SANS}`].map((f) => document.fonts.load(f, sample).catch(() => null)),
  );
}

function loadImage(url) {
  return new Promise((resolve) => {
    if (!url) return resolve(null);
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

/** Draws the card and resolves to a PNG blob. */
async function drawCard(d) {
  const photo = await loadImage(d.photoUrl);
  await loadFonts([d.name, d.bin, d.app, d.stepsTitle, d.note, ...d.steps, d.warning]);
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  const rtl = d.dir === "rtl";
  ctx.direction = d.dir;
  ctx.textAlign = "start";
  ctx.textBaseline = "alphabetic";
  // Each string gets its own direction (mock and some catalog text is Latin inside an Arabic card); the edge stays on the layout side.
  const put = (text, x, y) => {
    ctx.direction = /[\u0600-\u06FF]/.test(text) ? "rtl" : "ltr";
    ctx.textAlign = rtl ? "right" : "left";
    ctx.fillText(text, x, y);
  };
  const left = rtl ? W - PAD : PAD; // the "start" edge for text
  const dirX = rtl ? -1 : 1;
  const inner = W - PAD * 2;

  ctx.fillStyle = C.kraft;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = C.paper;
  ctx.strokeStyle = C.border;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(36, 36, W - 72, H - 72, 24);
  ctx.fill();
  ctx.stroke();

  // App name, then a rule that separates the header from the result.
  ctx.fillStyle = C.muted;
  ctx.font = `600 30px ${SANS}`;
  put(d.app, left, 134);
  ctx.fillStyle = C.border;
  ctx.fillRect(PAD, 164, inner, 2);

  // The user's own photo, cropped to fill a fixed frame so the layout never shifts.
  let y = 200;
  if (photo) {
    const ph = 440;
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(PAD, y, inner, ph, 14);
    ctx.clip();
    const k = Math.max(inner / photo.naturalWidth, ph / photo.naturalHeight);
    const dw = photo.naturalWidth * k;
    const dh = photo.naturalHeight * k;
    ctx.drawImage(photo, PAD + (inner - dw) / 2, y + (ph - dh) / 2, dw, dh);
    ctx.restore();
    ctx.strokeStyle = C.border;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(PAD, y, inner, ph, 14);
    ctx.stroke();
    y += ph + 40;
  }

  // Category name: the largest type on the card.
  ctx.fillStyle = C.ink;
  ctx.font = `600 92px ${SERIF}`;
  const nameLines = wrap(ctx, d.name, inner, 2);
  y += photo ? 76 : 92;
  nameLines.forEach((l) => {
    put(l, left, y);
    y += 108;
  });
  y -= 108 - 40;

  // Bin block uses the bin's own colors, read from the result chip on screen.
  if (d.bin) {
    const h = 168;
    ctx.fillStyle = d.binBg;
    ctx.beginPath();
    ctx.roundRect(PAD, y, inner, h, 14);
    ctx.fill();
    ctx.fillStyle = d.binFg;
    ctx.font = `400 30px ${SANS}`;
    put(d.binLabel, left + dirX * 36, y + 56);
    ctx.font = `600 64px ${SANS}`;
    put(wrap(ctx, d.bin, inner - 72, 1)[0], left + dirX * 36, y + 128);
    y += h + 44;
  }

  // Hazard: the first warning leads, in the danger palette.
  if (d.warning) {
    ctx.font = `600 34px ${SANS}`;
    const lines = wrap(ctx, d.warning, inner - 64, 2);
    const h = 40 + lines.length * 48;
    ctx.fillStyle = C.dangerBg;
    ctx.beginPath();
    ctx.roundRect(PAD, y, inner, h, 10);
    ctx.fill();
    ctx.fillStyle = C.dangerText;
    lines.forEach((l, i) => put(l, left + dirX * 32, y + 56 + i * 48));
    y += h + 40;
  }

  // Steps: the content is a sequence, so the numbers carry order.
  const footerTop = H - 250;
  if (d.steps.length) {
    ctx.fillStyle = C.ink;
    ctx.font = `600 38px ${SANS}`;
    put(d.stepsTitle, left, y + 30);
    y += 78;
    ctx.font = `400 38px ${SANS}`;
    for (let i = 0; i < d.steps.length; i += 1) {
      const lines = wrap(ctx, d.steps[i], inner - 88, 2);
      const h = lines.length * 50;
      if (y + h > footerTop) break;
      const cx = left + dirX * 28;
      ctx.fillStyle = C.accent;
      ctx.beginPath();
      ctx.arc(cx, y - 2, 28, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#FFFFFF";
      ctx.textAlign = "center";
      ctx.font = `600 30px ${SANS}`;
      ctx.fillText(String(i + 1), cx, y + 9); // numeral: centered, no direction
      ctx.textAlign = "start";
      ctx.fillStyle = C.ink;
      ctx.font = `400 38px ${SANS}`;
      lines.forEach((l, j) => put(l, left + dirX * 88, y + 12 + j * 50));
      y += h + 30;
    }
  }

  // Footer: honest note and the link.
  ctx.fillStyle = C.border;
  ctx.fillRect(PAD, H - 196, inner, 2);
  ctx.fillStyle = C.muted;
  ctx.font = `400 28px ${SANS}`;
  wrap(ctx, d.note, inner, 2).forEach((l, i) => put(l, left, H - 138 + i * 38));
  ctx.direction = "ltr";
  ctx.textAlign = rtl ? "right" : "left";
  ctx.font = `600 28px ${SANS}`;
  ctx.fillStyle = C.accent;
  ctx.fillText(d.url.replace(/^https?:\/\//, ""), rtl ? W - PAD : PAD, H - 72);

  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob"))), "image/png"));
}

export default function init(ctx) {
  const { t } = ctx;
  onCard((card, result) => {
    const nameEl = card.querySelector(".result__name");
    const chip = card.querySelector(".result__stamp .bin");
    if (!result.category || !nameEl) return;
    const stepEls = [...card.querySelectorAll(".result__steps li")];
    const warnEl = card.querySelector(".result__warnings li");
    const chipStyle = chip ? getComputedStyle(chip) : null;
    const url = SITE_URL;
    const data = () => ({
      dir: document.documentElement.dir || "ltr",
      app: t("app.title"),
      name: nameEl.textContent.trim(),
      bin: chip ? chip.textContent.trim() : "",
      binLabel: t("f.share.bin_label"),
      binBg: chipStyle ? chipStyle.backgroundColor : C.accent,
      binFg: chipStyle ? chipStyle.color : "#FFFFFF",
      warning: result.hazard && warnEl ? warnEl.textContent.trim() : "",
      stepsTitle: t("f.share.steps"),
      steps: stepEls.slice(0, 3).map((li) => li.textContent.trim()),
      note: t("f.share.note"),
      url,
      photoUrl: store.photoUrl,
    });
    const vars = { name: nameEl.textContent, bin: chip ? chip.textContent : "", step: stepEls[0] ? stepEls[0].textContent : "", url };
    const text = t(stepEls[0] ? "f.share.text" : "f.share.text_short", vars);

    const box = document.createElement("div");
    box.className = "f-share";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.textContent = t("f.share.button");
    const status = document.createElement("p");
    status.className = "muted";
    status.setAttribute("role", "status");
    box.append(btn, status);

    /** No file sharing on this device: the card is saved as a PNG so it can still be sent. */
    function download(file) {
      const href = URL.createObjectURL(file);
      const a = document.createElement("a");
      a.href = href;
      a.download = file.name;
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(href), 10000);
    }

    btn.addEventListener("click", async () => {
      status.textContent = t("f.share.preparing");
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      try {
        const blob = await drawCard(data());
        const file = new File([blob], `wasteai-${result.category.id}.png`, { type: "image/png" });
        const payload = { files: [file], title: nameEl.textContent.trim(), text: url, url };
        if (navigator.canShare && navigator.canShare(payload)) {
          try {
            await navigator.share(payload);
            status.textContent = "";
            return;
          } catch (err) {
            if (err && err.name === "AbortError") {
              status.textContent = "";
              return;
            }
          }
        }
        download(file);
        status.textContent = t("f.share.saved");
      } catch (err) {
        status.textContent = "";
        try {
          if (navigator.share) await navigator.share({ text, url });
          else if (navigator.clipboard) {
            await navigator.clipboard.writeText(text);
            status.textContent = t("f.share.copied");
          }
        } catch (e) {
          status.textContent = t("f.share.failed");
        }
      } finally {
        btn.disabled = false;
        btn.removeAttribute("aria-busy");
      }
    });

    const why = card.querySelector(".result__why");
    if (why) why.before(box);
    else card.append(box);
  });
}
