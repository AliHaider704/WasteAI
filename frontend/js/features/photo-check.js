// File: frontend/js/features/photo-check.js
// F08: calm tip for a dark, bright or blurry photo. Never blocks the upload.
// Relevance: a clear photo gives the classifier a fair chance.
export const styles = "photo-check";

const DEFAULTS = { side: 128, dark_below: 55, bright_above: 215, blurry_below: 60 };

/** Mean brightness (0-255) and Laplacian variance of a gray copy no larger than `side` px. */
export async function scorePhoto(blob, side) {
  const bmp = await createImageBitmap(blob);
  const k = Math.min(1, side / Math.max(bmp.width, bmp.height));
  const w = Math.max(3, Math.round(bmp.width * k));
  const h = Math.max(3, Math.round(bmp.height * k));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const g = canvas.getContext("2d", { willReadFrequently: true });
  g.drawImage(bmp, 0, 0, w, h);
  if (bmp.close) bmp.close();
  const px = g.getImageData(0, 0, w, h).data;
  const gray = new Float32Array(w * h);
  let sum = 0;
  for (let i = 0; i < gray.length; i++) {
    gray[i] = 0.299 * px[i * 4] + 0.587 * px[i * 4 + 1] + 0.114 * px[i * 4 + 2];
    sum += gray[i];
  }
  let n = 0, s = 0, s2 = 0;
  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      const i = y * w + x;
      const v = gray[i - 1] + gray[i + 1] + gray[i - w] + gray[i + w] - 4 * gray[i];
      s += v;
      s2 += v * v;
      n++;
    }
  }
  const mean = sum / gray.length;
  return { brightness: mean, sharpness: n ? s2 / n - (s / n) * (s / n) : 0 };
}

export default async function init(ctx) {
  let cfg = DEFAULTS;
  try {
    const res = await fetch("data/photo-check.json");
    if (res.ok) cfg = { ...DEFAULTS, ...(await res.json()) };
  } catch (_) { /* defaults */ }

  const host = document.querySelector(".capture");
  if (!host) return;
  const tip = document.createElement("p");
  tip.className = "pc-tip";
  tip.setAttribute("role", "status"); // one announcement per change
  tip.hidden = true;
  host.insertBefore(tip, host.querySelector(".actions") || null);

  let run = 0;
  const clear = () => {
    run++;
    tip.hidden = true;
    tip.textContent = "";
  };

  ctx.on("wasteai:capture", async (e) => {
    const d = e.detail || {};
    if (d.stage !== "ready") return clear();
    const mine = ++run;
    tip.hidden = true;
    tip.textContent = "";
    try {
      const s = await scorePhoto(d.blob, cfg.side);
      if (mine !== run) return; // a newer photo or a cancel won
      const text = s.brightness < cfg.dark_below ? ctx.t("f.photo-check.dark")
        : s.brightness > cfg.bright_above ? ctx.t("f.photo-check.bright")
        : s.sharpness < cfg.blurry_below ? ctx.t("f.photo-check.blurry") : "";
      if (!text) return;
      tip.textContent = text;
      tip.hidden = false;
    } catch (_) { /* a failed check shows nothing */ }
  });
}
