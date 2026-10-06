# server/app/sources/vision_azure.py
import os

import httpx

from app import quota
from app.imaging import to_jpeg
from app.sources.base import SourceResult  # assumed: SourceResult(name, ok, top)

API_VERSION = "2023-10-01"


def top3(body: dict) -> list[dict]:
    scores: dict[str, float] = {}
    for t in (body.get("tagsResult") or {}).get("values", []):
        scores[t["name"]] = max(scores.get(t["name"], 0.0), float(t["confidence"]))
    for o in (body.get("objectsResult") or {}).get("values", []):
        for t in o.get("tags", []):
            scores[t["name"]] = max(scores.get(t["name"], 0.0), float(t["confidence"]))
    best = sorted(scores.items(), key=lambda kv: -kv[1])[:3]
    return [{"label": k, "score": round(v, 4)} for k, v in best]


class VisionAzure:
    name = "azure"

    def __init__(self, endpoint: str = "", key: str = "", timeout: float = 6.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.key = key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

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

    def _fail(self) -> SourceResult:
        return SourceResult(name=self.name, ok=False, top=[])

    async def classify(self, data) -> SourceResult:
        if hasattr(data, "image"):
            data = to_jpeg(data)
        if not self.enabled or not quota.try_acquire():
            return self._fail()
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
            top = top3(resp.json())
        except (httpx.HTTPError, ValueError, KeyError):
            return self._fail()
        return SourceResult(name=self.name, ok=bool(top), top=top)
