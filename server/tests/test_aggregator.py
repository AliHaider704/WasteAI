# File: server/tests/test_aggregator.py
from app.aggregator import GROUP_OF, decide


def L(d):  # local
    return {"local_onnx": d}


def test_full_agreement_ok():
    d = decide({"local_onnx": {"plastic_pet": 0.9, "plastic_unknown": 0.1},
                "azure": {"plastic_pet": 0.8, "plastic_unknown": 0.2}})
    assert d.status == "ok" and d.category_id == "plastic_pet"
    assert d.agreement == "full" and not d.hazard


def test_partial_agreement_ok():
    d = decide({"local_onnx": {"plastic_pet": 0.9, "plastic_unknown": 0.1},
                "azure": {"plastic_unknown": 0.6, "plastic_pet": 0.4}})
    assert d.agreement == "partial" and d.status == "ok"


def test_no_agreement_uncertain():
    d = decide({"local_onnx": {"glass": 0.9, "paper": 0.1},
                "azure": {"paper": 0.9, "glass": 0.1}})
    assert d.agreement == "none" and d.status == "uncertain"
    assert d.category_id is None and len(d.alternatives) == 2


def test_single_source_thresholds():
    hi = decide(L({"glass": 0.85, "paper": 0.15}))
    lo = decide(L({"glass": 0.70, "paper": 0.30}))
    assert hi.agreement == "single_source" and hi.status == "ok"
    assert lo.status == "uncertain"


def test_hazard_flag_even_when_uncertain():
    d = decide({"local_onnx": {"battery": 0.4, "metal_steel": 0.6},
                "azure": {"battery": 0.3, "metal_steel": 0.7}})
    assert d.status == "uncertain" and d.hazard and d.hazard_id == "battery"
    assert "battery" in [a[0] for a in d.alternatives]


def test_hazard_below_threshold():
    d = decide({"local_onnx": {"battery": 0.2, "metal_steel": 0.8},
                "azure": {"battery": 0.1, "metal_steel": 0.9}})
    assert not d.hazard and d.status == "ok"


def test_all_26_ids_have_group():
    assert len(GROUP_OF) == 26


# --- A14: calibration and group fallback ---
from app import aggregator  # noqa: E402


def _two(a, b):
    return {"local_onnx": a, "azure": b}


def test_group_fallback_plastics():
    d = decide(_two({"plastic_pet": 0.45, "plastic_hdpe": 0.40, "glass": 0.15},
                    {"plastic_hdpe": 0.45, "plastic_pet": 0.40, "glass": 0.15}))
    assert d.status == "ok" and d.fallback and d.category_id == "plastic_unknown"
    assert d.confidence <= aggregator.FALLBACK_CAP and d.hazard is False


def test_fallback_not_for_hazard_or_other_groups():
    h = decide(_two({"battery": 0.4, "ewaste_small": 0.4, "paper": 0.2},
                    {"ewaste_small": 0.4, "battery": 0.4, "paper": 0.2}))
    assert not h.fallback and h.hazard
    for ids in (("battery", "ewaste_small"), ("hazardous_chemical", "medical"),
                ("ewaste_large", "ewaste_small")):
        assert aggregator.group_fallback([(ids[0], 0.45), (ids[1], 0.45)]) is None
    assert aggregator.group_fallback([("glass", 0.5), ("paper", 0.4)]) is None
    assert aggregator.group_fallback([("textile", 0.4), ("wood", 0.4)]) is None


def test_fallback_needs_combined_score():
    assert aggregator.group_fallback([("paper", 0.3), ("cardboard", 0.2)]) is None
    assert aggregator.group_fallback([("paper", 0.4), ("cardboard", 0.35)])[0] == "paper"


def test_calibrate_identity_and_monotone():
    s = {"a": 0.7, "b": 0.3}
    assert aggregator.calibrate(s, 1.0) == s
    soft = aggregator.calibrate(s, 2.0)
    assert abs(sum(soft.values()) - 1) < 1e-9 and soft["a"] < 0.7 and soft["a"] > soft["b"]
