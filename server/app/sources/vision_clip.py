# File: server/app/sources/vision_clip.py
"""Optional zero-shot image-text source (A40, D-051). Flag CLIP_ENABLED=false by default.

Only the int8 image encoder runs on the server. Text embeddings of our 26 categories are
precomputed on a dev machine (scripts/build_clip_prompts.py -> data/clip_text.json).
Score = softmax(CLIP_TEMP x cosine similarity); labels are category ids (identity mapping).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import numpy as np

from app.imaging import PreparedImage
from app.sources.base import Source, SourceResult

_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
DEFAULT_TEXT_PATH = Path(__file__).resolve().parents[2] / "data" / "clip_text.json"


class ClipError(Exception):
    pass


def enabled_by_env() -> bool:
    return os.getenv("CLIP_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def load_text_vectors(path: str | Path) -> tuple[list[str], np.ndarray]:
    """clip_text.json -> (category ids, matrix [n, dim], rows L2-normalized)."""
    data = json.loads(Path(path).read_text("utf-8"))
    cats = data.get("categories") or {}
    if not cats:
        raise ClipError("clip_text.json has no categories")
    ids = sorted(cats)
    mat = np.asarray([cats[c] for c in ids], dtype=np.float32)
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
    return ids, mat


def zero_shot(embedding: np.ndarray, ids: list[str], mat: np.ndarray,
              temperature: float = 100.0, k: int = 3) -> list[dict]:
    """Cosine similarity to every category, softmax with a fixed temperature, top-k."""
    e = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if not np.isfinite(e).all():
        raise ClipError("nan_output")
    e = e / (np.linalg.norm(e) + 1e-12)
    logits = temperature * (mat @ e)
    p = np.exp(logits - logits.max())
    p /= p.sum()
    idx = np.argsort(p)[::-1][: min(k, len(ids))]
    return [{"label": ids[i], "score": round(float(p[i]), 4)} for i in idx]


class VisionClip(Source):
    name = "clip"

    def __init__(self, model_path: str | None, ids: list[str], mat: np.ndarray,
                 size: int = 224, temperature: float = 100.0, session=None) -> None:
        self.model_path, self.ids, self.mat = model_path, ids, mat
        self.size, self.temperature = size, temperature
        self._session = session  # injectable for tests
        self._input_name = ""
        self.health = {"status": "down", "reason": "not_loaded", "checked_at": None, "latency_ms": None}
        if session is not None:
            self._bind()

    @classmethod
    def from_env(cls) -> VisionClip | None:
        """None unless CLIP_ENABLED=true and both files exist (the flag is off by default)."""
        if not enabled_by_env():
            return None
        ids, mat = load_text_vectors(os.getenv("CLIP_TEXT_PATH", DEFAULT_TEXT_PATH))
        return cls(os.getenv("CLIP_MODEL_PATH"), ids, mat,
                   temperature=float(os.getenv("CLIP_TEMP", "100")))

    @property
    def enabled(self) -> bool:
        return self._session is not None or bool(self.model_path)

    @property
    def ready(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        if self._session is not None:
            return
        if not self.model_path or not Path(self.model_path).is_file():
            raise ClipError(f"model file not found: {self.model_path}")
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = opts.inter_op_num_threads = 1
        self._session = ort.InferenceSession(self.model_path, sess_options=opts,
                                             providers=["CPUExecutionProvider"])
        self._bind()

    def _bind(self) -> None:
        self._input_name = self._session.get_inputs()[0].name
        self.health = {"status": "up", "reason": "loaded", "checked_at": None, "latency_ms": None}

    def mark_down(self, reason: str) -> None:
        self.health = {"status": "down", "reason": reason, "checked_at": int(time.time()),
                       "latency_ms": None}

    def _preprocess(self, prepared: PreparedImage) -> np.ndarray:
        arr = np.asarray(prepared.image.resize((self.size, self.size)), dtype=np.float32) / 255.0
        arr = ((arr - _MEAN) / _STD).transpose(2, 0, 1)
        return np.ascontiguousarray(arr[np.newaxis, ...], dtype=np.float32)

    def _infer(self, prepared: PreparedImage) -> list[dict]:
        out = self._session.run(None, {self._input_name: self._preprocess(prepared)})[0]
        return zero_shot(np.asarray(out), self.ids, self.mat, self.temperature)

    def selftest(self) -> dict:
        """One real inference on a generated image; checks dimension, NaN and probabilities."""
        t0 = time.perf_counter()
        reason = "ok"
        if not self.ready:
            reason = "model_not_loaded"
        else:
            try:
                from PIL import Image

                img = Image.linear_gradient("L").resize((self.size, self.size)).convert("RGB")
                top = self._infer(PreparedImage(img, "selftest"))
                if not top or not 0.0 < sum(t["score"] for t in top) <= 1.01:
                    reason = "bad_probabilities"
            except Exception as exc:
                reason = f"inference_error:{type(exc).__name__}"
        self.health = {"status": "up" if reason == "ok" else "down", "reason": reason,
                       "checked_at": int(time.time()),
                       "latency_ms": int((time.perf_counter() - t0) * 1000)}
        return self.health

    async def classify(self, prepared: PreparedImage) -> SourceResult:
        if not self.ready:
            return SourceResult(self.name, False, error="model_not_loaded")
        try:
            top = await asyncio.to_thread(self._infer, prepared)
        except Exception as exc:  # a failing source is skipped, never fatal
            return SourceResult(self.name, False, error=type(exc).__name__)
        return SourceResult(self.name, True, top)
