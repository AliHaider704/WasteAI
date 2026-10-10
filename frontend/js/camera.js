// File: frontend/js/camera.js
// getUserMedia wrapper. Failures are thrown as CameraError carrying an i18n key,
// so the caller can show a message and fall back to the file picker.

export class CameraError extends Error {
  constructor(i18nKey, cause) {
    super(i18nKey);
    this.name = "CameraError";
    this.i18nKey = i18nKey;
    this.cause = cause;
  }
}

// M34: the live stream is shared with feature modules through `wasteai:capture` stage "camera".
let active = null;
const announce = (detail) => document.dispatchEvent(new CustomEvent("wasteai:capture", { detail }));
export const activeCamera = () => active;

/** Camera switch: replaces the running stream; stopCamera still releases it. */
export async function adoptStream(next) {
  if (!active) return next.getTracks().forEach((track) => track.stop());
  active.stream.getTracks().forEach((track) => track.stop());
  active.stream = next;
  active.video.srcObject = next;
  await active.video.play();
  announce({ stage: "camera", stream: next, track: next.getVideoTracks()[0] });
}

/** getUserMedia needs a secure context (HTTPS or localhost). */
export function isCameraSupported() {
  return Boolean(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) && window.isSecureContext;
}

/** NotAllowedError has several causes. Ask the Permissions API which one, so the message can say what to do. */
async function deniedKey() {
  try {
    const status = await navigator.permissions.query({ name: "camera" });
    if (status.state === "denied") return "camera.blocked"; // saved "Block" for this site (browser or OS level)
    return "camera.dismissed"; // prompt closed or suppressed (Brave Shields, no user gesture): trying again can work
  } catch (e) {
    return "camera.denied"; // Permissions API cannot query "camera" here
  }
}

async function failure(err) {
  const key = keyFor(err);
  return new CameraError(key === "camera.denied" ? await deniedKey() : key, err);
}

function keyFor(err) {
  switch (err && err.name) {
    case "NotAllowedError":
    case "SecurityError":
    case "PermissionDeniedError":
      return "camera.denied";
    case "NotFoundError":
    case "DevicesNotFoundError":
      return "camera.not_found";
    case "NotReadableError":
    case "TrackStartError":
    case "AbortError":
      return "camera.busy";
    default:
      return "camera.error";
  }
}

/** Starts the rear camera (falls back to any camera) and plays it in `video`. Returns the stream. */
export async function startCamera(video) {
  if (!isCameraSupported()) throw new CameraError("camera.unsupported");
  const md = navigator.mediaDevices;
  let stream;
  try {
    stream = await md.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: false,
    });
  } catch (err) {
    if (err && err.name === "OverconstrainedError") {
      try {
        stream = await md.getUserMedia({ video: true, audio: false });
      } catch (err2) {
        throw await failure(err2);
      }
    } else {
      throw await failure(err);
    }
  }
  video.muted = true;
  video.setAttribute("playsinline", ""); // required by iOS Safari
  video.srcObject = stream;
  try {
    await video.play();
  } catch (err) {
    stopCamera(stream, video);
    throw new CameraError("camera.error", err);
  }
  active = { stream, origin: stream, video };
  announce({ stage: "camera", stream, track: stream.getVideoTracks()[0] });
  return stream;
}

/** Releases the camera so the browser's recording indicator turns off. */
export function stopCamera(stream, video) {
  if (stream) stream.getTracks().forEach((track) => track.stop());
  if (active && (stream === active.origin || stream === active.stream)) {
    active.stream.getTracks().forEach((track) => track.stop());
    active = null;
    announce({ stage: "camera-off" });
  }
  if (video) video.srcObject = null;
}

/** Copies the current video frame to a full-size canvas. */
export function grabFrame(video) {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) throw new CameraError("camera.error");
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").drawImage(video, 0, 0, width, height);
  return canvas;
}
