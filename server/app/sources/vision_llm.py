# File: server/app/sources/vision_llm.py
"""Optional free-tier vision LLM tiebreaker. Returns raw labels only, never a category id.

Off by default (LLM_TIEBREAKER_ENABLED=false). Model name and endpoint limits must be read
from the provider's pages at build time; nothing here is a verified free-tier limit.
"""
import os
import re

import httpx

from app import quota
from app.imaging import to_jpeg
from app.sources.base import SourceResult

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
PROMPT = (
    "Name the main waste item in this photo. Answer with at most 5 short English object "
    "or material labels, most likely first, separated by commas. Labels only, no sentences."
)
_LABEL_RE = re.compile(r"^[a-z][a-z \-]{0,39}$")


def parse_labels(text: str, limit: int = 5) -> list[dict]:
    """Turn a comma/newline list into [{label, score}] with falling scores (0.9, 0.8, ...)."""
    out: list[dict] = []
    for raw in re.split(r"[,\n;]", text or ""):
        label = raw.strip().strip(".*-").lower()
        if _LABEL_RE.match(label) and all(o["label"] != label for o in out):
            out.append({"label": label, "score": round(max(0.9 - 0.1 * len(out), 0.5), 2)})
        if len(out) >= limit:
            break
    return out


class VisionLLM:
    name = "llm"

    def __init__(self, enabled: bool = False, api_key: str = "", model: str = "",
                 daily_cap: int = 20, timeout: float = 6.0) -> None:
        self.flag = enabled
        self.api_key, self.model = api_key, model
        self.daily_cap, self.timeout = daily_cap, timeout
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_env(cls) -> "VisionLLM":
        try:
            cap = int(os.getenv("LLM_DAILY_CAP", "20"))
        except ValueError:
            cap = 20
        return cls(os.getenv("LLM_TIEBREAKER_ENABLED", "false").strip().lower() == "true",
                   os.getenv("LLM_API_KEY", ""), os.getenv("LLM_MODEL", ""), cap)

    @property
    def enabled(self) -> bool:
        return bool(self.flag and self.api_key and self.model)

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        return "quota" if quota.llm_exhausted(self.daily_cap) else "up"

    def _fail(self) -> SourceResult:
        return SourceResult(name=self.name, ok=False, top=[])

    async def classify(self, data) -> SourceResult:
        if hasattr(data, "image"):
            data = to_jpeg(data)
        if not self.enabled or not quota.llm_try_acquire(self.daily_cap):
            return self._fail()
        import base64

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        body = {"contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": "image/jpeg",
                             "data": base64.b64encode(data).decode("ascii")}},
        ]}], "generationConfig": {"maxOutputTokens": 40, "temperature": 0}}
        try:
            resp = await self._client.post(
                f"{BASE_URL}/{self.model}:generateContent",
                json=body, headers={"x-goog-api-key": self.api_key})
            resp.raise_for_status()
            parts = resp.json()["candidates"][0]["content"]["parts"]
            top = parse_labels(" ".join(str(p.get("text", "")) for p in parts))
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            return self._fail()
        return SourceResult(name=self.name, ok=bool(top), top=top)
