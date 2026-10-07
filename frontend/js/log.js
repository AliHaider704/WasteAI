// File: frontend/js/log.js
// JSON client logger. English event names only, no PII, no image data.
// Sends to POST /api/v1/log (sendBeacon, else fetch keepalive). Drops silently on failure.
// Hard limit: 5 events per minute per page.

const LOG_URL = "/api/v1/log";
const MAX_EVENTS = 5;
const WINDOW_MS = 60000;
const MAX_DETAIL = 200;
const LEVELS = ["debug", "info", "warning", "error"];

const sent = []; // timestamps of recent sends

// Remove control characters, collapse whitespace, cut to the server limit.
function clean(text) {
  return String(text == null ? "" : text)
    .replace(/[\u0000-\u001f\u007f-\u009f]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, MAX_DETAIL);
}

function allowed() {
  const now = Date.now();
  while (sent.length && now - sent[0] > WINDOW_MS) sent.shift();
  if (sent.length >= MAX_EVENTS) return false;
  sent.push(now);
  return true;
}

/**
 * log(event, { level, requestId, detail })
 * `event` is a short English snake_case name, e.g. "api_error", "js_error".
 */
export function log(event, { level = "error", requestId = null, detail = "" } = {}) {
  try {
    if (!allowed()) return;
    const payload = { level: LEVELS.includes(level) ? level : "error", event: clean(event).slice(0, 64) || "unknown" };
    if (requestId) payload.request_id = clean(requestId).slice(0, 64);
    const d = clean(detail);
    if (d) payload.detail = d;
    const body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      const ok = navigator.sendBeacon(LOG_URL, new Blob([body], { type: "application/json" }));
      if (ok) return;
    }
    fetch(LOG_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch (err) {
    // logging must never throw
  }
}
