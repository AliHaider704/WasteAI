// File: frontend/js/features/status.js
// F28: footer button, dialog with the public /health answer. Polls no faster than every 30 s (A32 floor).
export const styles = true;

const POLL_MS = 30000;
const KNOWN = ["up", "down", "quota", "disabled"];

export default function init(ctx) {
  const host = ctx.slot("footer");
  if (!host) return;
  const { t } = ctx;
  let data = null;
  let failed = false;
  let loading = false;
  let timer = 0;
  let last = 0;

  const open = document.createElement("button");
  open.type = "button";
  open.className = "f-status-btn";
  open.setAttribute("aria-haspopup", "dialog");
  const dialog = document.createElement("dialog");
  dialog.className = "f-dialog";
  dialog.setAttribute("aria-labelledby", "f-st-title");
  const title = document.createElement("h2");
  title.id = "f-st-title";
  const note = document.createElement("p");
  note.setAttribute("role", "status");
  const list = document.createElement("ul");
  list.className = "f-status-list";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn";
  close.autofocus = true;
  dialog.append(title, note, list, close);
  host.append(open, dialog);

  function render() {
    open.textContent = t("f.status.button");
    title.textContent = t("f.status.title");
    close.textContent = t("f.status.close");
    list.replaceChildren();
    if (loading && !data) note.textContent = t("f.status.loading");
    else if (failed && !data) note.textContent = t("f.status.error");
    else if (data) {
      note.textContent = t(data.status === "ok" ? "f.status.ok" : "f.status.degraded");
      const srcs = data.sources || {};
      for (const name of Object.keys(srcs)) {
        const li = document.createElement("li");
        const k = "f.status.src." + name;
        const label = t(k) || name;
        const s = String(srcs[name]);
        li.textContent = label + ": " + t("f.status.state." + (KNOWN.includes(s) ? s : "unknown"));
        list.append(li);
      }
    }
  }

  async function load() {
    if (loading || Date.now() - last < POLL_MS) return;
    loading = true;
    render();
    const ctl = new AbortController();
    const to = setTimeout(() => ctl.abort(), 6000);
    try {
      const r = await fetch("/api/v1/health", { signal: ctl.signal, cache: "no-store" });
      if (!r.ok) throw new Error("http");
      data = await r.json();
      failed = false;
    } catch (e) {
      failed = true;
    } finally {
      clearTimeout(to);
      loading = false;
      last = Date.now();
      render();
    }
  }

  open.addEventListener("click", () => {
    dialog.showModal();
    close.focus();
    load();
    timer = setInterval(load, POLL_MS);
  });
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { clearInterval(timer); open.focus(); });
  ctx.on("i18n:change", render);
  render();
}
