// File: frontend/js/features/exhibition.js
// F23: kiosk reset. After idle time, a countdown dialog; at zero everything saved on this device is cleared and the app returns to Home.
export const styles = true;

const IDLE_MS = 120000;
const COUNT_S = 15;

export default function init(ctx) {
  const { t, store } = ctx;
  document.documentElement.dataset.exhibition = "on";

  const dialog = document.createElement("dialog");
  dialog.className = "f-dialog";
  dialog.setAttribute("aria-labelledby", "f-ex-title");
  const title = document.createElement("h2");
  title.id = "f-ex-title";
  const body = document.createElement("p");
  body.setAttribute("role", "status");
  const keep = document.createElement("button");
  keep.type = "button";
  keep.className = "btn";
  keep.autofocus = true;
  const actions = document.createElement("div");
  actions.className = "f-ex-actions";
  actions.append(keep);
  dialog.append(title, body, actions);
  (ctx.slot("footer") || document.body).append(dialog);

  let touched = false;
  let idleTimer = 0;
  let tick = 0;
  let left = COUNT_S;

  function render() {
    title.textContent = t("f.exhibition.title");
    body.textContent = t("f.exhibition.body", { n: left });
    keep.textContent = t("f.exhibition.keep");
  }
  function reset() {
    store.clearAll();
    location.hash = "#/";
    location.reload();
  }
  function stopCount() {
    clearInterval(tick);
    if (dialog.open) dialog.close();
  }
  function startCount() {
    left = COUNT_S;
    render();
    dialog.showModal();
    keep.focus();
    tick = setInterval(() => {
      left -= 1;
      if (left <= 0) { clearInterval(tick); reset(); return; }
      render();
    }, 1000);
  }
  function arm() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => { if (touched) startCount(); }, IDLE_MS);
  }
  function activity() {
    if (dialog.open) return; // only the button keeps the session alive
    touched = true;
    arm();
  }

  keep.addEventListener("click", () => { stopCount(); arm(); });
  dialog.addEventListener("cancel", () => { stopCount(); arm(); }); // Escape
  ["pointerdown", "keydown", "touchstart"].forEach((ev) =>
    document.addEventListener(ev, activity, { passive: true }));
  ctx.on("i18n:change", render);
  render();
  arm();
}
