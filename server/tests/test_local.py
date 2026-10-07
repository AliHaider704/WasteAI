# File: server/tests/test_local.py
import asyncio
import json

import numpy as np
import pytest
from PIL import Image

from app.imaging import PreparedImage
from app.sources.vision_local import LocalModelError, VisionLocal, load_labels

LABELS = ["cardboard", "glass", "metal", "paper", "plastic", "trash"]


class _Inp:
    name = "input"
    shape = [1, 3, 224, 224]


class FakeSession:
    def __init__(self, logits):
        self.logits = np.array([logits], dtype=np.float32)
        self.seen_shape = None

    def get_inputs(self):
        return [_Inp()]

    def run(self, _outs, feed):
        self.seen_shape = feed["input"].shape
        return [self.logits]


def _prepared() -> PreparedImage:
    return PreparedImage(image=Image.new("RGB", (300, 200), (90, 90, 200)), sha256="x" * 64)


def test_top3_sorted_and_softmaxed():
    sess = FakeSession([0.1, 0.2, 0.3, 0.4, 5.0, 0.0])
    src = VisionLocal(None, LABELS, session=sess)
    res = asyncio.run(src.classify(_prepared()))
    assert res.ok and sess.seen_shape == (1, 3, 224, 224)
    assert [t["label"] for t in res.top][0] == "plastic" and len(res.top) == 3
    assert 0.9 < res.top[0]["score"] <= 1.0
    assert res.as_contract()["name"] == "local_onnx"


def test_probabilities_kept_as_is():
    src = VisionLocal(None, LABELS, session=FakeSession([0.0, 0.7, 0.1, 0.1, 0.05, 0.05]))
    res = asyncio.run(src.classify(_prepared()))
    assert res.top[0] == {"label": "glass", "score": 0.7}


def test_not_loaded_is_skipped_not_raised():
    res = asyncio.run(VisionLocal("missing.onnx", LABELS).classify(_prepared()))
    assert not res.ok and res.error == "model_not_loaded"


def test_inference_error_is_skipped():
    class Boom(FakeSession):
        def run(self, *_a):
            raise RuntimeError("bad")

    res = asyncio.run(VisionLocal(None, LABELS, session=Boom([0] * 6)).classify(_prepared()))
    assert not res.ok and res.error == "RuntimeError"


def test_load_missing_file_raises():
    with pytest.raises(LocalModelError):
        VisionLocal("nope.onnx", LABELS).load()


def test_load_labels(tmp_path):
    p = tmp_path / "labels.json"
    model = {"labels": LABELS, "size": 160, "norm": "unit"}
    p.write_text(json.dumps({"active": "m", "models": {"m": model}}))
    assert load_labels(p) == (LABELS, 160, "unit")
    p.write_text(json.dumps({"active": None, "models": {}}))
    with pytest.raises(LocalModelError):
        load_labels(p)
