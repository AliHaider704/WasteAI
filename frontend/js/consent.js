// File: frontend/js/consent.js
// Per-photo consent checkbox for the optional cloud model (D-024, A15).
// Unchecked by default, never saved between photos, shown only when the server offers the option.

import { t } from "./i18n.js";
import { MOCK, getHealth } from "./api.js";
import { log } from "./log.js";

let seq = 0;

export function createConsent() {
  const id = `consent-${(seq += 1)}`;
  const node = document.createElement("div");
  node.className = "consent";
  node.hidden = true;

  const input = document.createElement("input");
  input.type = "checkbox";
  input.id = id;
  input.name = "allow_cloud_llm";
  input.className = "consent__box";

  const label = document.createElement("label");
  label.htmlFor = id;
  label.className = "consent__label";
  label.dataset.i18n = "consent.label";
  label.textContent = t("consent.label");

  const note = document.createElement("p");
  note.className = "muted consent__note";
  note.dataset.i18n = "consent.note";
  note.textContent = t("consent.note");

  const row = document.createElement("div");
  row.className = "consent__row";
  row.append(input, label);
  node.append(row, note);

  let offered = MOCK; // mock mode shows it so the flow can be checked without a server
  let wanted = false;

  const sync = () => {
    node.hidden = !(offered && wanted);
  };

  if (!MOCK) {
    getHealth()
      .then((h) => {
        const s = h && h.sources && h.sources.llm;
        offered = s === "up";
        sync();
      })
      .catch((err) => log("consent_health_failed", { detail: err && err.message }));
  }

  return {
    node,
    /** Show the checkbox only while a photo preview is on screen. */
    setVisible(on) {
      wanted = Boolean(on);
      sync();
    },
    /** True only when the person ticked the box for the current photo. */
    isChecked() {
      return offered && input.checked;
    },
    /** Called whenever the photo is discarded: the choice never carries over. */
    reset() {
      input.checked = false;
    },
  };
}
