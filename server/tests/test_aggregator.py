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
