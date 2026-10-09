// File: frontend/js/features/my-bins.js
// F13: the user writes what each local bin is called. Plain text only, kept on the device.
import { onCard } from "./card-hook.js";
export const styles = "comfort";

const BINS = ["blue", "green", "yellow", "red", "black", "brown", "grey", "special"];

export default function init(ctx) {
  const { t, store } = ctx;
  if (document.documentElement.dataset.kids === "on") return;
  const host = ctx.slot("result");
  if (!host) return;
  let names = store.get("my-bins", {}) || {};

  const open = document.createElement("button");
  open.type = "button";
  open.className = "btn";
  open.setAttribute("aria-haspopup", "dialog");
  host.append(open);

  const dlg = document.createElement("dialog");
  dlg.className = "f-dialog";
  document.body.append(dlg);
  let confirming = false;

  function mark(card) {
    if (!card) return;
    card.querySelectorAll(".f-mybin").forEach((n) => n.remove());
    const chip = card.querySelector(".result__stamp .bin");
    const text = chip && names[chip.dataset.binInfo];
    if (!text) return;
    const span = document.createElement("span");
    span.className = "f-mybin";
    span.textContent = t("f.my-bins.yours", { name: text });
    card.querySelector(".result__stamp").append(span);
  }

  function btn(key, cls, fn) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = cls;
    b.textContent = t(key);
    b.addEventListener("click", fn);
    return b;
  }

  function build() {
    open.textContent = t("f.my-bins.open");
    dlg.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = t("f.my-bins.title");
    dlg.append(title);
    const actions = document.createElement("div");
    actions.className = "f-actions";
    if (confirming) {
      const q = document.createElement("p");
      q.textContent = t("f.my-bins.clear_q");
      dlg.append(q);
      const cancel = btn("f.my-bins.cancel", "btn", () => { confirming = false; build(); });
      actions.append(cancel, btn("f.my-bins.clear_yes", "btn", () => {
        names = {};
        store.remove("my-bins");
        confirming = false;
        mark(document.querySelector(".result__card"));
        dlg.close();
      }));
      dlg.append(actions);
      cancel.focus(); // Cancel is the default focus
      return;
    }
    const note = document.createElement("p");
    note.textContent = t("f.my-bins.note");
    dlg.append(note);
    BINS.forEach((bin) => {
      const row = document.createElement("div");
      row.className = "f-field";
      const label = document.createElement("label");
      label.htmlFor = `f-mybin-${bin}`;
      label.textContent = t(`bin.${bin}`);
      const input = document.createElement("input");
      input.className = "input";
      input.id = label.htmlFor;
      input.name = `bin-${bin}`;
      input.type = "text";
      input.maxLength = 40;
      input.autocomplete = "off";
      input.placeholder = t("f.my-bins.placeholder");
      input.value = names[bin] || "";
      row.append(label, input);
      dlg.append(row);
    });
    actions.append(
      btn("f.my-bins.save", "btn btn--primary", () => {
        const next = {};
        BINS.forEach((bin) => {
          const v = dlg.querySelector(`#f-mybin-${bin}`).value.trim().slice(0, 40);
          if (v) next[bin] = v;
        });
        names = next;
        store.set("my-bins", names);
        mark(document.querySelector(".result__card"));
        dlg.close();
      }),
      btn("f.my-bins.clear", "btn", () => { confirming = true; build(); }),
      btn("f.my-bins.close", "btn", () => dlg.close())
    );
    dlg.append(actions);
  }

  open.addEventListener("click", () => {
    confirming = false;
    build();
    dlg.showModal();
    const first = dlg.querySelector("input");
    if (first) first.focus();
  });
  dlg.addEventListener("close", () => { confirming = false; open.focus(); });
  ctx.on("i18n:change", () => {
    open.textContent = t("f.my-bins.open");
    if (dlg.open) build();
    mark(document.querySelector(".result__card"));
  });
  open.textContent = t("f.my-bins.open");
  onCard(mark);
}
