// File: frontend/js/header-scroll.js
// Hides the header while scrolling down, shows it again when scrolling up.
const header = document.querySelector(".app-header");
if (header) {
  let lastY = window.scrollY;
  let ticking = false;
  const update = () => {
    const y = Math.max(window.scrollY, 0);
    const delta = y - lastY;
    header.classList.toggle("is-scrolled", y > 4);
    if (y <= 8 || delta < -6) header.classList.remove("is-hidden");
    else if (delta > 6 && y > header.offsetHeight) header.classList.add("is-hidden");
    if (Math.abs(delta) > 6 || y <= 8) lastY = y;
    ticking = false;
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true });
  // Keep it visible when keyboard focus lands inside it.
  header.addEventListener("focusin", () => header.classList.remove("is-hidden"));
}
