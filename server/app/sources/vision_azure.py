# File: server/app/sources/vision_azure.py
import io
import json
import os
import time
from functools import lru_cache
from pathlib import Path

import httpx
from PIL import Image

from app import quota
from app.imaging import to_jpeg
from app.sources.base import SourceResult  # assumed: SourceResult(name, ok, top)

API_VERSION = "2023-10-01"


STOPLIST_PATH = Path(
    os.getenv("AZURE_STOPLIST_PATH", Path(__file__).resolve().parents[2] / "data" / "azure_stoplist.json")
)


@lru_cache(maxsize=1)
def load_stoplist() -> frozenset[str]:
    """Generic Azure tags that carry no waste information (data/azure_stoplist.json)."""
    try:
        data = json.loads(STOPLIST_PATH.read_text("utf-8"))
    except (OSError, ValueError):
        return frozenset()
    return frozenset(str(w).strip().lower() for w in data.get("stop", []))


def top_labels(body: dict, limit: int = 10) -> list[dict]:
    """Tags and object tags, generic ones removed, best `limit` by confidence."""
    stop = load_stoplist()
    scores: dict[str, float] = {}

    def add(t: dict) -> None:
        name = str(t["name"])
        if name.strip().lower() in stop:
            return
        scores[name] = max(scores.get(name, 0.0), float(t["confidence"]))

    for t in (body.get("tagsResult") or {}).get("values", []):
        add(t)
    for o in (body.get("objectsResult") or {}).get("values", []):
        for t in o.get("tags", []):
            add(t)
    best = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
    return [{"label": k, "score": round(v, 4)} for k, v in best]


DEEP_INTERVAL = 3600.0  # one real Azure call per hour at most (/health/deep)


def _probe_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.linear_gradient("L").resize((100, 100)).convert("RGB").save(buf, "JPEG")
    return buf.getvalue()


class VisionAzure:
    name = "azure"

    def __init__(self, endpoint: str = "", key: str = "", timeout: float = 6.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.key = key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._deep: dict | None = None
        self._deep_at = 0.0

    @classmethod
    def from_env(cls) -> "VisionAzure":
        return cls(os.getenv("AZURE_VISION_ENDPOINT", ""), os.getenv("AZURE_VISION_KEY", ""))

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint and self.key)

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        return "quota" if quota.exhausted() else "up"

    def _fail(self, error: str = "failed") -> SourceResult:
        return SourceResult(name=self.name, ok=False, top=[], error=error)

    def selftest(self) -> dict:
        """Cheap check, no network: config present and quota counter readable."""
        reason, status = "config_ok", "up"
        if not self.enabled:
            status, reason = "disabled", "not_configured"
        else:
            try:
                if quota.exhausted():
                    status, reason = "quota", "monthly_cap_reached"
            except Exception:
                status, reason = "down", "quota_unreadable"
        return {"status": status, "reason": reason, "checked_at": int(time.time())}

    async def deep_check(self) -> dict:
        """Real call with a generated image, at most once per hour (counts against the quota)."""
        now = time.monotonic()
        if self._deep is not None and now - self._deep_at < DEEP_INTERVAL:
            return {**self._deep, "cached": True}
        t0 = time.perf_counter()
        res = await self.classify(_probe_jpeg())
        if not self.enabled:
            status = "disabled"
        else:
            status = "up" if res.ok else ("quota" if res.error == "quota" else "down")
        self._deep = {"status": status, "reason": "ok" if res.ok else res.error,
                      "latency_ms": int((time.perf_counter() - t0) * 1000),
                      "checked_at": int(time.time())}
        self._deep_at = now
        return {**self._deep, "cached": False}

    async def classify(self, data) -> SourceResult:
        if hasattr(data, "image"):
            data = to_jpeg(data)
        if not self.enabled:
            return self._fail("not_configured")
        if not quota.try_acquire():
            return self._fail("quota")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        try:
            resp = await self._client.post(
                f"{self.endpoint}/computervision/imageanalysis:analyze",
                params={"api-version": API_VERSION, "features": "tags,objects"},
                content=data,
                headers={
                    "Ocp-Apim-Subscription-Key": self.key,
                    "Content-Type": "application/octet-stream",
                },
            )
            resp.raise_for_status()
            top = top_labels(resp.json())
        except httpx.TimeoutException:
            return self._fail("timeout")
        except httpx.HTTPStatusError as exc:
            return self._fail(f"http_{exc.response.status_code}")
        except (httpx.HTTPError, ValueError, KeyError):
            return self._fail("bad_response")
        return SourceResult(name=self.name, ok=True, top=top)
