# server/app/sources/base.py
"""Common interface for classification sources (local ONNX, Azure, ReciclAPI)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.imaging import PreparedImage


@dataclass
class SourceResult:
    name: str
    ok: bool
    top: list[dict] = field(default_factory=list)  # [{"label": str, "score": float}], max 3
    error: str | None = None

    def as_contract(self) -> dict:
        """Shape of `sources[]` in the /classify response."""
        return {"name": self.name, "ok": self.ok, "top": self.top[:3]}


class Source(ABC):
    name: str

    @abstractmethod
    async def classify(self, prepared: PreparedImage) -> SourceResult:
        """Never raise for provider failures: return SourceResult(ok=False, error=...)."""
