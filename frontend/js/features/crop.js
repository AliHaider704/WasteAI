// File: frontend/js/features/crop.js
// F11: mark the item with a rectangle; the cropped pixels replace the photo that is sent.
// Relevance: removes background clutter that can confuse the classifier.
export const styles = "crop";

const STEP = 0.02;
const MIN = 0.1;
const QUALITY = 0.85;

export default function init(ctx) {
  const host = document.querySelector(".capture");
  const img = host && host.querySelector("img.capture__media");
  if (!img) return;

  let original = null; // the photo as first shown
  let current = null;  // what is shown now
  let replace = null;
  let r = { x: 0, y: 0, w: 1, h: 1 }; // fractions of the photo itself

  const wrap = document.createElement("div");
  wrap.className = "cr-wrap";
  img.replaceWith(wrap);
  wrap.append(img);

  const box = document.createElement("div");
  box.className = "cr-box";
  box.hidden = true;
  box.tabIndex = 0;
  box.setAttribute("role", "group");
  box.setAttribute("aria-label", ctx.t("f.crop.area"));
  ["nw", "ne", "sw", "se"].forEach((c) => {
    const hdl = document.createElement("span");
    hdl.className = "cr-handle cr-" + c;
    hdl.dataset.corner = c;
    box.append(hdl);
  });
  wrap.append(box);

  const mk = (key, onclick) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "btn";
    b.hidden = true;
    b.textContent = ctx.t(key);
    b.dataset.key = key;
    b.addEventListener("click", onclick);
    return b;
  };
  const toggle = mk("f.crop.start", () => (box.hidden ? open() : close()));
  const apply = mk("f.crop.apply", doApply);
  const reset = mk("f.crop.reset", doReset);
  const tools = document.createElement("div");
  tools.className = "cr-tools";
  tools.append(toggle, apply, reset);
  host.insertBefore(tools, host.querySelector(".actions") || null);

  function say(msg) {
    const live = host.querySelector(".capture__status");
    if (live) live.textContent = msg;
  }
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  // Where the photo sits inside the element (object-fit: contain).
  function fit() {
    const W = img.clientWidth, H = img.clientHeight;
    const nw = img.naturalWidth || W, nh = img.naturalHeight || H;
    const k = Math.min(W / nw, H / nh);
    const w = nw * k, h = nh * k;
    return { left: img.offsetLeft + (W - w) / 2, top: img.offsetTop + (H - h) / 2, w, h };
  }
  function draw() {
    const f = fit();
    box.style.insetInlineStart = "auto";
    box.style.left = f.left + r.x * f.w + "px";
    box.style.top = f.top + r.y * f.h + "px";
    box.style.width = r.w * f.w + "px";
    box.style.height = r.h * f.h + "px";
  }
  function open() {
    r = { x: 0.1, y: 0.1, w: 0.8, h: 0.8 };
    box.hidden = false;
    draw();
    toggle.textContent = ctx.t("f.crop.cancel");
    apply.hidden = false;
    box.focus();
  }
  function close() {
    box.hidden = true;
    apply.hidden = true;
    toggle.textContent = ctx.t("f.crop.start");
  }
  function setRect(n) {
    n.w = clamp(n.w, MIN, 1);
    n.h = clamp(n.h, MIN, 1);
    n.x = clamp(n.x, 0, 1 - n.w);
    n.y = clamp(n.y, 0, 1 - n.h);
    r = n;
    draw();
  }

  // Keyboard: arrows move, Shift + arrows resize.
  box.addEventListener("keydown", (e) => {
    const dx = { ArrowLeft: -1, ArrowRight: 1 }[e.key] || 0;
    const dy = { ArrowUp: -1, ArrowDown: 1 }[e.key] || 0;
    if (e.key === "Escape") { e.stopPropagation(); close(); toggle.focus(); return; }
    if (!dx && !dy) return;
    e.preventDefault();
    if (e.shiftKey) setRect({ ...r, w: r.w + dx * STEP, h: r.h + dy * STEP });
    else setRect({ ...r, x: r.x + dx * STEP, y: r.y + dy * STEP });
  });

  // Pointer: drag the body to move, a corner to resize.
  let drag = null;
  box.addEventListener("pointerdown", (e) => {
    const f = fit();
    drag = { corner: e.target.dataset.corner || "", sx: e.clientX, sy: e.clientY, r: { ...r }, f };
    box.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  box.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = (e.clientX - drag.sx) / drag.f.w;
    const dy = (e.clientY - drag.sy) / drag.f.h;
    const o = drag.r, c = drag.corner;
    if (!c) return setRect({ ...o, x: o.x + dx, y: o.y + dy });
    let { x, y, w, h } = o;
    if (c.includes("e")) w = o.w + dx; else { x = o.x + dx; w = o.w - dx; }
    if (c.includes("s")) h = o.h + dy; else { y = o.y + dy; h = o.h - dy; }
    if (w < MIN) { if (!c.includes("e")) x = o.x + o.w - MIN; w = MIN; }
    if (h < MIN) { if (!c.includes("s")) y = o.y + o.h - MIN; h = MIN; }
    setRect({ x, y, w, h });
  });
  const end = () => { drag = null; };
  box.addEventListener("pointerup", end);
  box.addEventListener("pointercancel", end);
  window.addEventListener("resize", () => { if (!box.hidden) draw(); });

  async function doApply() {
    if (!current || !replace) return;
    try {
      const bmp = await createImageBitmap(current);
      const sx = Math.round(r.x * bmp.width), sy = Math.round(r.y * bmp.height);
      const sw = Math.max(1, Math.round(r.w * bmp.width)), sh = Math.max(1, Math.round(r.h * bmp.height));
      const canvas = document.createElement("canvas");
      canvas.width = sw;
      canvas.height = sh;
      canvas.getContext("2d").drawImage(bmp, sx, sy, sw, sh, 0, 0, sw, sh);
      if (bmp.close) bmp.close();
      const out = await new Promise((ok) => canvas.toBlob(ok, "image/jpeg", QUALITY));
      if (!out) throw new Error("encode");
      current = out;
      replace(out); // swaps the preview and the file that Analyze sends
      close();
      reset.hidden = false;
      say(ctx.t("f.crop.done"));
      toggle.focus();
    } catch (_) { say(ctx.t("f.crop.failed")); }
  }
  function doReset() {
    if (!original || !replace) return;
    current = original;
    replace(original);
    reset.hidden = true;
    close();
    say(ctx.t("f.crop.restored"));
    toggle.focus();
  }

  ctx.on("wasteai:capture", (e) => {
    const d = e.detail || {};
    if (d.stage === "ready") {
      original = current = d.blob;
      replace = d.replace;
      close();
      reset.hidden = true;
      toggle.hidden = false;
    } else if (["open", "cancel", "sent", "before-send"].includes(d.stage)) {
      if (d.stage !== "before-send") { toggle.hidden = true; reset.hidden = true; original = current = replace = null; }
      close();
    }
  });
  // Keep button text in the current language.
  ctx.on("i18n:change", () => [toggle, apply, reset].forEach((b) => {
    const k = b === toggle ? (box.hidden ? "f.crop.start" : "f.crop.cancel") : b.dataset.key;
    b.textContent = ctx.t(k);
    box.setAttribute("aria-label", ctx.t("f.crop.area"));
  }));
}
