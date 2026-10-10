# File: server/tests/test_clip.py
"""A40: zero-shot maths and the source wrapper with fixture vectors (no model download)."""
import asyncio
import json

import numpy as np
import pytest
from PIL import Image

from app import orchestrator
from app.imaging import PreparedImage
from app.sources import vision_clip

IDS = ["glass", "paper", "battery"]
MAT = np.eye(3, dtype=np.float32)


class FakeInput:
    name = "pixel_values"


class FakeSession:
    def __init__(self, emb):
        self.emb, self.seen = np.asarray(emb, dtype=np.float32), None

    def get_inputs(self):
        return [FakeInput()]

    def run(self, _outs, feed):
        self.seen = feed["pixel_values"]
        return [self.emb.reshape(1, -1)]


def _img():
    return PreparedImage(Image.new("RGB", (64, 48), (200, 10, 10)), "test")


def test_zero_shot_ranks_and_sums_to_one():
    top = vision_clip.zero_shot([0.1, 0.9, 0.0], IDS, MAT, temperature=10.0)
    assert [t["label"] for t in top][0] == "paper"
    assert abs(sum(t["score"] for t in top) - 1.0) < 0.01
    assert top[0]["score"] > top[1]["score"] > top[2]["score"]


def test_nan_embedding_rejected():
    with pytest.raises(vision_clip.ClipError):
        vision_clip.zero_shot([float("nan"), 0, 0], IDS, MAT)


def test_source_classify_and_selftest():
    sess = FakeSession([1.0, 0.0, 0.0])
    src = vision_clip.VisionClip(None, IDS, MAT, session=sess)
    res = asyncio.run(src.classify(_img()))
    assert res.ok and res.top[0]["label"] == "glass"
    assert sess.seen.shape == (1, 3, 224, 224) and sess.seen.dtype == np.float32
    assert src.selftest()["status"] == "up"


def test_failure_is_not_fatal():
    class Boom(FakeSession):
        def run(self, *_a):
            raise RuntimeError("x")
    res = asyncio.run(vision_clip.VisionClip(None, IDS, MAT, session=Boom([1, 0, 0])).classify(_img()))
    assert res.ok is False and res.error == "RuntimeError"
    assert asyncio.run(vision_clip.VisionClip("/x.onnx", IDS, MAT).classify(_img())).ok is False


def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("CLIP_ENABLED", raising=False)
    assert vision_clip.VisionClip.from_env() is None


def test_load_text_vectors_normalizes(tmp_path):
    f = tmp_path / "t.json"
    f.write_text(json.dumps({"categories": {"b": [3.0, 4.0], "a": [0.0, 2.0]}}))
    ids, mat = vision_clip.load_text_vectors(f)
    assert ids == ["a", "b"] and np.allclose(np.linalg.norm(mat, axis=1), 1.0)
    f.write_text("{}")
    with pytest.raises(vision_clip.ClipError):
        vision_clip.load_text_vectors(f)


def test_identity_scoring_and_items():
    assert orchestrator._score([("glass", 0.7), ("paper", 0.3)], "clip") == {"glass": 0.7, "paper": 0.3}
    items = orchestrator._source_items([("clip", True, [("glass", 0.7)])], {"clip": 5})
    assert items[0]["top"] == [{"label": "glass", "score": 0.7, "mapped": True, "cat": "glass"}]


def test_clip_weight_default():
    from app import aggregator
    assert aggregator.weights()["clip"] == 0.3
