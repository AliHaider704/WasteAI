// File: frontend/js/features/delete-data.js
// F20: footer button + confirm dialog that clears everything saved on this device.
export const styles = true;

export default function init(ctx) {
  const host = ctx.slot("footer");
  if (!host) return;
  const { t } = ctx;
  let removed = null;

  const open = document.createElement("button");
  open.type = "button";
  open.className = "f-textbtn";
  open.setAttribute("aria-haspopup", "dialog");

  const dialog = document.createElement("dialog");
  dialog.className = "f-dialog";
  dialog.setAttribute("aria-labelledby", "f-del-title");
  const title = document.createElement("h2");
  title.id = "f-del-title";
  const body = document.createElement("p");
  const actions = document.createElement("div");
  actions.className = "f-actions";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn";
  cancel.autofocus = true;
  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "btn";
  actions.append(cancel, confirm);
  dialog.append(title, body, actions);
  host.append(open, dialog);

  function render() {
    open.textContent = t("f.delete-data.button");
    title.textContent = t("f.delete-data.title");
    if (removed === null) {
      body.textContent = t("f.delete-data.body");
      cancel.textContent = t("f.delete-data.cancel");
      confirm.textContent = t("f.delete-data.confirm");
      confirm.hidden = false;
    } else {
      body.textContent = t("f.delete-data.done", { n: removed });
      cancel.textContent = t("f.delete-data.reload");
      confirm.hidden = true;
    }
  }

  open.addEventListener("click", () => {
    removed = null;
    render();
    dialog.showModal();
    cancel.focus();
  });
  cancel.addEventListener("click", () => dialog.close());
  confirm.addEventListener("click", () => {
    removed = ctx.store.clearAll();
    render();
    cancel.focus();
  });
  dialog.addEventListener("close", () => {
    if (removed !== null) location.reload(); // back to defaults
    else open.focus();
  });
  ctx.on("i18n:change", render);
  render();
}
