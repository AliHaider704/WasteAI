// File: frontend/js/api.js
// API client with a MOCK switch. Mock mode is ON by default until sync point S1.
// Switch without editing code: ?mock=0 uses the real backend. In mock mode,
// ?scenario=ok|uncertain|hazard|rate_limited|image_too_large|all_sources_failed picks the response.

import { log } from "./log.js";

const params = new URLSearchParams(location.search);
export const MOCK = params.get("mock") === "1";
const API_BASE = "/api/v1";
const MOCK_BASE = "mock/";
const MOCK_DELAY_MS = 900;
const TIMEOUT_MS = 20000;
const MOCK_RETRY_AFTER_S = 30;
const RETRIES = 3; // idempotent GETs only
const BACKOFF_BASE_MS = 500;
const BACKOFF_CAP_MS = 8000;

const SCENARIOS = {
  ok: "classify_ok",
  uncertain: "classify_uncertain",
  hazard: "classify_hazard",
  rate_limited: "error_rate_limited",
  image_too_large: "error_image_too_large",
  all_sources_failed: "error_all_sources_failed",
};

// Stable API error codes (ARCHITECTURE §4) plus two client-side codes.
export const ERROR_KEYS = {
  invalid_image: "error.invalid_image",
  image_too_large: "error.image_too_large",
  unsupported_type: "error.unsupported_type",
  invalid_request: "error.invalid_request",
  rate_limited: "error.rate_limited",
  all_sources_failed: "error.all_sources_failed",
  overloaded: "error.overloaded",
  internal_error: "error.internal_error",
  network_error: "error.network",
  timeout: "error.timeout",
  unknown: "error.unknown",
};

const MOCK_STATUS = {
  invalid_image: 400, image_too_large: 413, unsupported_type: 415, invalid_request: 422,
  rate_limited: 429, all_sources_failed: 502, overloaded: 503, internal_error: 500,
};

export class ApiError extends Error {
  constructor(code, { status = 0, requestId = null, retryAfter = null } = {}) {
    super(code);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
    this.retryAfter = retryAfter; // seconds, from the Retry-After header (429)
    this.i18nKey = ERROR_KEYS[code] || ERROR_KEYS.unknown;
  }
}

// Shared hand-off between upload.js (writes) and the results UI in M4 (reads).
export const store = { result: null, photoUrl: null };

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Error body is not our JSON (for example the Nginx HTML 413 page): map by status (B-08).
function codeFromStatus(status) {
  if (status === 413) return "image_too_large";
  if (status === 429) return "rate_limited";
  return "internal_error";
}

function retryAfterSeconds(res) {
  const n = Number(res.headers.get("Retry-After"));
  return Number.isFinite(n) && n > 0 ? Math.ceil(n) : null;
}

// Only server-side or network failures are logged; user mistakes (4xx) are not.
function logFailure(err, url) {
  if (err.status === 0 || err.status >= 500) {
    const path = String(url).split("?")[0];
    log("api_error", { requestId: err.requestId, detail: `${err.code} ${err.status} ${path}` });
  }
}

async function request(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let res;
  try {
    res = await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    const e = new ApiError(err && err.name === "AbortError" ? "timeout" : "network_error");
    logFailure(e, url);
    throw e;
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 204) return null;
  let body = null;
  try {
    body = await res.json();
  } catch (err) {
    body = null;
  }
  if (!res.ok) {
    const e = body && body.error;
    const code = e && e.code ? e.code : codeFromStatus(res.status);
    const apiErr = new ApiError(code, {
      status: res.status,
      requestId: e && e.request_id ? e.request_id : null,
      retryAfter: retryAfterSeconds(res),
    });
    logFailure(apiErr, url);
    throw apiErr;
  }
  if (body === null) {
    const e = new ApiError("internal_error", { status: res.status });
    logFailure(e, url);
    throw e;
  }
  return body;
}

function retryable(err) {
  if (!(err instanceof ApiError)) return false;
  return err.status === 0 || err.status === 429 || err.status === 502 || err.status === 503 || err.status === 504;
}

// Exponential backoff with full jitter: random(0, min(cap, base * 2^attempt)).
function backoffMs(attempt) {
  return Math.random() * Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** attempt);
}

// Idempotent GETs only. POSTs never go through here.
async function requestWithRetry(url, options = {}) {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await request(url, options);
    } catch (err) {
      if (attempt >= RETRIES || !retryable(err)) throw err;
      const serverWait = err.retryAfter ? Math.min(err.retryAfter * 1000, BACKOFF_CAP_MS) : 0;
      await sleep(Math.max(serverWait, backoffMs(attempt)));
    }
  }
}

// Mock files hold error bodies with HTTP 200, so convert them to the same ApiError.
function throwIfMockError(body) {
  if (!body || !body.error) return body;
  const { code, request_id: requestId } = body.error;
  throw new ApiError(code, {
    status: MOCK_STATUS[code] || 0,
    requestId,
    retryAfter: code === "rate_limited" ? MOCK_RETRY_AFTER_S : null,
  });
}

/** POST /classify. `blob` is the resized JPEG. Never auto-retried. */
export async function classify(blob, lang, allowCloudLlm = false) {
  if (MOCK) {
    const file = SCENARIOS[params.get("scenario")] || SCENARIOS.ok;
    await sleep(MOCK_DELAY_MS);
    return throwIfMockError(await request(`${MOCK_BASE}${file}.json`));
  }
  const form = new FormData();
  form.append("image", blob, "photo.jpg");
  form.append("allow_cloud_llm", allowCloudLlm ? "1" : "0");
  return request(`${API_BASE}/classify?lang=${encodeURIComponent(lang)}`, { method: "POST", body: form });
}

/** GET /categories (retried with backoff). */
export async function getCategories(lang) {
  if (MOCK) return request(`${MOCK_BASE}categories.json`);
  return requestWithRetry(`${API_BASE}/categories?lang=${encodeURIComponent(lang)}`);
}

/** GET /health (retried with backoff). */
export async function getHealth() {
  if (MOCK) return { status: "ok" };
  return requestWithRetry(`${API_BASE}/health`);
}

/** POST /feedback (used by the results UI in M4). Resolves with null on success (204). */
export async function sendFeedback(requestId, correctCategoryId) {
  if (MOCK) {
    await sleep(300);
    return null;
  }
  return request(`${API_BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId, correct_category_id: correctCategoryId }),
  });
}
