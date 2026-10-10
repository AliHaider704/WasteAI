# File: server/tests/test_policy.py
"""A41: cloud rule, flag-off equality, thresholds from env, grid choice."""
from app import aggregator, policy

H, G = aggregator.HAZARD_IDS, aggregator.GROUP_OF


def test_cloud_ok_cases():
    s = {"local_onnx": {"general_residual": 0.8}, "azure": {"glass": 0.9}}
    assert policy.cloud_ok(s, {"azure": 0.7}, 0.5, H, G) == "glass"
    assert policy.cloud_ok(s, {"azure": 0.3}, 0.5, H, G) is None  # too weak
    assert policy.cloud_ok(s, None, 0.5, H, G) is None  # needs evidence strength
    same = {"local_onnx": {"plastic_pp": 0.8}, "azure": {"plastic_pet": 0.9}}
    assert policy.cloud_ok(same, {"azure": 0.7}, 0.5, H, G) == "plastic_pet"  # same group
    cross = {"local_onnx": {"paper": 0.8}, "azure": {"plastic_pet": 0.9}}
    assert policy.cloud_ok(cross, {"azure": 0.9}, 0.5, H, G) is None  # across groups
    haz = {"local_onnx": {"general_residual": 0.8}, "azure": {"battery": 0.9}}
    assert policy.cloud_ok(haz, {"azure": 0.9}, 0.5, H, G) is None  # never a hazard


def _split():
    return {"local_onnx": {"general_residual": 0.7, "glass": 0.3}, "azure": {"glass": 0.6, "paper": 0.4}}


def test_flag_off_equals_old_and_on_turns_uncertain_into_ok(monkeypatch):
    monkeypatch.delenv("POLICY_V2", raising=False)
    off = aggregator.decide(_split(), {"azure": 0.8})
    assert off.status == "uncertain"
    monkeypatch.setenv("POLICY_V2", "true")
    on = aggregator.decide(_split(), {"azure": 0.8})
    assert on.status == "ok" and on.category_id == "glass" and on.hazard is False
    assert aggregator.decide(_split()).status == "uncertain"  # no strengths: rule inactive


def test_thresholds_from_env(monkeypatch):
    monkeypatch.setenv("OK_MIN", "0.5")
    monkeypatch.setenv("S_CLOUD", "bad")
    p = policy.params(0.65, 0.8)
    assert (p.ok_min, p.single_ok_min, p.s_cloud) == (0.5, 0.8, policy.DEFAULT_S_CLOUD)


def test_choose_respects_gc_and_uncertain_cap():
    base = {"top1": 50.0, "confident_wrong": 5.0, "hazard_recall": 90.0}
    mk = lambda acc, unc, cw, hz, n=10, t=55.0: {  # noqa: E731
        "accuracy_on_ok": acc, "uncertain": unc, "confident_wrong": cw, "hazard_recall": hz,
        "ok_count": n, "top1": t}
    rows = [mk(95.0, 60.0, 1.0, 90.0),  # too uncertain
            mk(99.0, 20.0, 9.0, 90.0),  # confident-wrong up 4 points
            mk(98.0, 20.0, 2.0, 80.0),  # hazard recall lower
            mk(90.0, 30.0, 3.0, 90.0, n=20), mk(90.0, 30.0, 2.0, 90.0, n=15)]
    best = policy.choose(rows, base)
    assert best["confident_wrong"] == 2.0 and best["accuracy_on_ok"] == 90.0
    assert policy.choose([mk(99.0, 90.0, 1.0, 90.0)], base) is None
