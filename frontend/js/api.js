// PATH: waste-ai/frontend/js/api.js
// API client with a MOCK switch. Mock mode is ON by default until sync point S1.
// Switch without editing code: ?mock=0 uses the real backend. In mock mode,
// ?scenario=ok|uncertain|hazard|rate_limited|image_too_large|all_sources_failed picks the response.

const params = new URLSearchParams(location.search);
export const MOCK = params.get("mock") !== "0"; // S1: flip this default to false
const API_BASE = "/api/v1";
const MOCK_BASE = "mock/";
const MOCK_DELAY_MS = 900;
const TIMEOUT_MS = 20000;
const MOCK_RETRY_AFTER_S = 30;

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

async function request(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let res;
  try {
    res = await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    throw new ApiError(err && err.name === "AbortError" ? "timeout" : "network_error");
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
    throw new ApiError(e && e.code ? e.code : "internal_error", {
      status: res.status,
      requestId: e && e.request_id ? e.request_id : null,
      retryAfter: Number(res.headers.get("Retry-After")) || null,
    });
  }
  if (body === null) throw new ApiError("internal_error", { status: res.status });
  return body;
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

/** POST /classify. `blob` is the resized JPEG. Resolves with the contract response. */
export async function classify(blob, lang) {
  if (MOCK) {
    const file = SCENARIOS[params.get("scenario")] || SCENARIOS.ok;
    await sleep(MOCK_DELAY_MS);
    return throwIfMockError(await request(`${MOCK_BASE}${file}.json`));
  }
  const form = new FormData();
  form.append("image", blob, "photo.jpg");
  return request(`${API_BASE}/classify?lang=${encodeURIComponent(lang)}`, { method: "POST", body: form });
}

/** GET /categories. */
export async function getCategories(lang) {
  if (MOCK) return request(`${MOCK_BASE}categories.json`);
  return request(`${API_BASE}/categories?lang=${encodeURIComponent(lang)}`);
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
