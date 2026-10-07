# File: server/app/sources/vision_local.py
"""Local ONNX image classifier: loaded once, 1 thread, top-3 labels."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import numpy as np

from app.imaging import PreparedImage
from app.sources.base import Source, SourceResult

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
DEFAULT_LABELS_PATH = "data/model_labels.json"


class LocalModelError(Exception):
    pass


def load_labels(path: str | Path) -> tuple[list[str], int, str]:
    """Read the active model entry from model_labels.json -> (labels, size, norm).

    Accepts entry = [labels...] or {"labels": [...], "size": 224, "norm": "imagenet"},
    stored under "models" or "label_sets", keyed by the "active" name.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    active = data.get("active")
    if not active:
        raise LocalModelError("model_labels.json has no active model (finish A2)")
    entry = (data.get("models") or data.get("label_sets") or {}).get(active)
    if entry is None:
        raise LocalModelError(f"active model {active!r} not found in labels file")
    if isinstance(entry, dict):
        return list(entry["labels"]), int(entry.get("size", 224)), str(entry.get("norm", "imagenet"))
    return list(entry), 224, "imagenet"


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


class VisionLocal(Source):
    name = "local_onnx"

    def __init__(self, model_path: str | None, labels: list[str], size: int = 224,
                 norm: str = "imagenet", session=None) -> None:
        self.model_path = model_path
        self.labels = labels
        self.size = size
        self.norm = norm
        self._session = session  # injectable for tests
        self._input_name = ""
        self._nhwc = False
        if session is not None:
            self._bind()

    @classmethod
    def from_env(cls) -> VisionLocal:
        labels, size, norm = load_labels(os.environ.get("MODEL_LABELS_PATH", DEFAULT_LABELS_PATH))
        return cls(os.environ.get("MODEL_PATH"), labels, size, norm)

    @property
    def ready(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        """Load the model once at startup (call from app lifespan)."""
        if self._session is not None:
            return
        if not self.model_path or not Path(self.model_path).is_file():
            raise LocalModelError(f"model file not found: {self.model_path}")
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self._session = ort.InferenceSession(
            self.model_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._bind()

    def _bind(self) -> None:
        inp = self._session.get_inputs()[0]
        self._input_name = inp.name
        shape = list(inp.shape)
        self._nhwc = len(shape) == 4 and shape[-1] == 3

    def _preprocess(self, prepared: PreparedImage) -> np.ndarray:
        img = prepared.image.resize((self.size, self.size))
        arr = np.asarray(img, dtype=np.float32)
        if self.norm == "imagenet":
            arr = (arr / 255.0 - _MEAN) / _STD
        elif self.norm == "unit":
            arr = arr / 255.0
        if not self._nhwc:
            arr = arr.transpose(2, 0, 1)
        return np.ascontiguousarray(arr[np.newaxis, ...], dtype=np.float32)

    def _infer(self, prepared: PreparedImage) -> list[dict]:
        out = self._session.run(None, {self._input_name: self._preprocess(prepared)})[0]
        scores = np.asarray(out, dtype=np.float32).reshape(-1)
        if scores.min() < 0 or scores.max() > 1 or abs(float(scores.sum()) - 1.0) > 1e-2:
            scores = _softmax(scores)
        k = min(3, len(self.labels), len(scores))
        idx = np.argsort(scores)[::-1][:k]
        return [{"label": self.labels[i], "score": round(float(scores[i]), 4)} for i in idx]

    async def classify(self, prepared: PreparedImage) -> SourceResult:
        if not self.ready:
            return SourceResult(self.name, False, error="model_not_loaded")
        try:
            top = await asyncio.to_thread(self._infer, prepared)
        except Exception as exc:  # source failure is skipped, never fatal
            return SourceResult(self.name, False, error=type(exc).__name__)
        return SourceResult(self.name, True, top)
