// File: frontend/js/features/ink.js
// P02: the stamp border wears with lower confidence. Text colors never change. Hazard results stay neutral.
import { onCard } from "./card-hook.js";
export const styles = "result-visuals";

export default function init() {
  onCard((card, result) => {
    if (result.hazard || !result.category) return;
    const word = card.querySelector(".result__confidence");
    const chip = card.querySelector(".result__stamp .bin");
    if (!word || !chip) return;
    const tier = { high: "sharp", medium: "worn", low: "faint" }[word.dataset.level];
    if (tier) chip.classList.add(`f-ink--${tier}`);
  });
}
