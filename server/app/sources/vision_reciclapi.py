# File: server/app/sources/vision_reciclapi.py
import os

import httpx

from app.imaging import to_jpeg
from app.sources.base import SourceResult  # assumed: SourceResult(name, ok, top)


def _parse(body) -> list[dict]:
    """Lenient parser: plan/response shape is UNVERIFIED (D-004)."""
    if isinstance(body, dict):
        items = body.get("predictions") or body.get("results") or body.get("classes") or []
    else:
        items = body if isinstance(body, list) else []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        label = it.get("label") or it.get("class") or it.get("name")
        score = it.get("score", it.get("confidence"))
        if label is not None and score is not None:
            out.append({"label": str(label), "score": round(float(score), 4)})
    return sorted(out, key=lambda d: -d["score"])[:3]


class VisionReciclAPI:
    name = "reciclapi"

    def __init__(self, key: str = "", url: str = "", host: str = "", timeout: float = 4.0) -> None:
        self.key, self.url, self.host, self.timeout = key, url, host, timeout
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_env(cls) -> "VisionReciclAPI":
        return cls(
            os.getenv("RECICLAPI_KEY", ""),
            os.getenv("RECICLAPI_URL", ""),
            os.getenv("RECICLAPI_HOST", ""),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.key and self.url)

    async def classify(self, data) -> SourceResult:
        if hasattr(data, "image"):
            data = to_jpeg(data)
        if not self.enabled:
            return SourceResult(name=self.name, ok=False, top=[])
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        headers = {"X-RapidAPI-Key": self.key}
        if self.host:
            headers["X-RapidAPI-Host"] = self.host
        try:
            resp = await self._client.post(
                self.url, files={"image": ("image.jpg", data, "image/jpeg")}, headers=headers
            )
            resp.raise_for_status()
            top = _parse(resp.json())
        except (httpx.HTTPError, ValueError, TypeError):
            return SourceResult(name=self.name, ok=False, top=[])
        return SourceResult(name=self.name, ok=bool(top), top=top)
