// File: frontend/js/features/card-hook.js
// Helper for result-card features: runs fn(card, result) once for every freshly rendered card.
import { store } from "../api.js";

export function onCard(fn) {
  const root = document.getElementById("result-root");
  if (!root) return;
  const seen = new WeakSet();
  const run = () => {
    const card = root.querySelector(".result__card");
    if (!card || !store.result || seen.has(card)) return;
    seen.add(card);
    fn(card, store.result);
  };
  new MutationObserver(run).observe(root, { childList: true });
  run();
}
