// File: frontend/js/features/torch.js
// F10: torch and camera switch, shown only where the device supports them.
// Relevance: torch helps dark corners; switch reaches the rear camera on phones with several lenses.
import { activeCamera, adoptStream } from "../camera.js";
import { addTool, icon, say, syncBar } from "./capture-tools.js";
export const styles = "capture-tools";

export default function init(ctx) {
  let lit = false;

  const torch = document.createElement("button");
  torch.type = "button";
  torch.hidden = true;
  torch.append(icon("M13 2 4 14h7l-1 8 9-12h-7l1-8Z"));
  const flip = document.createElement("button");
  flip.type = "button";
  flip.hidden = true;
  flip.append(icon("M4 8h12l-3-3M20 16H8l3 3"));

  const track = () => {
    const cam = activeCamera();
    return cam ? cam.stream.getVideoTracks()[0] : null;
  };

  function labels() {
    const a = ctx.t("f.torch.label");
    const b = ctx.t("f.torch.switch");
    torch.setAttribute("aria-label", a);
    torch.title = a;
    torch.setAttribute("aria-pressed", String(lit));
    flip.setAttribute("aria-label", b);
    flip.title = b;
  }

  async function refresh() {
    lit = false;
    const tr = track();
    const caps = tr && tr.getCapabilities ? tr.getCapabilities() : {};
    torch.hidden = !(caps && caps.torch);
    flip.hidden = true;
    if (tr && navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
      try {
        const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
        flip.hidden = !(cams.length > 1 && track() === tr);
      } catch (e) { /* no list, no switch button */ }
    }
    labels();
    syncBar();
  }

  torch.addEventListener("click", async () => {
    const tr = track();
    if (!tr) return;
    try {
      await tr.applyConstraints({ advanced: [{ torch: !lit }] });
      lit = !lit;
      labels();
      say(ctx.t(lit ? "f.torch.on" : "f.torch.off"));
    } catch (e) {
      torch.hidden = true; // the browser refused: stop offering it
      syncBar();
    }
  });

  flip.addEventListener("click", async () => {
    const tr = track();
    if (!tr) return;
    flip.disabled = true;
    try {
      const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
      const now = tr.getSettings().deviceId;
      const next = cams[(cams.findIndex((d) => d.deviceId === now) + 1) % cams.length];
      const stream = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: next.deviceId } }, audio: false });
      await adoptStream(stream); // fires stage "camera", which runs refresh()
      say(ctx.t("f.torch.switched"));
    } catch (e) {
      say(ctx.t("f.torch.switch_failed"));
    } finally {
      flip.disabled = false;
    }
  });

  addTool(3, torch);
  addTool(4, flip);
  document.addEventListener("wasteai:capture", (e) => {
    const s = e.detail && e.detail.stage;
    if (s === "camera") refresh();
    else if (s === "camera-off") { lit = false; torch.hidden = true; flip.hidden = true; syncBar(); }
  });
  ctx.on("i18n:change", labels);
  refresh(); // the module may load after the camera already started
}
