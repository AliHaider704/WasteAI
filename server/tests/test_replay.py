# File: server/tests/test_replay.py
"""A36: replay metrics maths on a 6-row fixture (no Azure, no photos)."""
import importlib.util
from pathlib import Path

from app import aggregator, mapper

_spec = importlib.util.spec_from_file_location(
    "replay", Path(__file__).resolve().parents[2] / "scripts" / "replay.py")
replay = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(replay)


def tags(*pairs):
    return [{"label": lb, "score": s} for lb, s in pairs]


def fake_mapper(table):
    class M:
        @staticmethod
        def map_labels(pairs):
            return table.get(pairs[0][0], {}) if pairs else {}
    return M


def test_metrics_maths():
    table = {
        "a": {"glass": 0.95, "paper": 0.05},
        "b": {"paper": 0.95, "glass": 0.05},
        "c": {"battery": 0.9, "glass": 0.1},
        "d": {"glass": 0.5, "paper": 0.5},
        "e": {"paper": 0.9, "glass": 0.1},
    }
    rows = [
        {"truth": "glass", "local": tags(("a", 1.0)), "azure": tags(("a", 1.0))},   # right, ok
        {"truth": "glass", "local": tags(("b", 1.0)), "azure": tags(("b", 1.0))},   # confident wrong
        {"truth": "battery", "local": tags(("c", 1.0)), "azure": tags(("c", 1.0))},  # hazard found
        {"truth": "paper", "local": tags(("d", 1.0)), "azure": tags(("d", 1.0))},   # uncertain
        {"truth": "paper", "local": tags(("zz", 1.0)), "azure": None},              # nothing mapped
        {"truth": "paper", "local": tags(("e", 1.0)), "azure": tags(("e", 1.0))},   # right, ok
    ]
    m = replay.metrics(rows, fake_mapper(table), aggregator)
    assert m["photos"] == 6
    assert m["ok_count"] == 4
    assert m["top1"] == round(100 * 3 / 6, 1)
    assert m["accuracy_on_ok"] == round(100 * 3 / 4, 1)
    assert m["confident_wrong"] == round(100 * 1 / 6, 1)
    assert m["uncertain"] == round(100 * 2 / 6, 1)
    assert m["hazard_recall"] == 100.0 and m["hazard_photos"] == 1
    assert m["confusion"]["paper"]["(none)"] == 1


def test_unmapped_counts_real_rules():
    rows = [{"azure": tags(("plastic bottle", 0.9), ("qqqxyz", 0.8))},
            {"azure": tags(("qqqxyz", 0.7))}]
    out = replay.unmapped(rows, mapper)
    assert {"tag": "qqqxyz", "count": 2} in out
    assert all(t["tag"] != "plastic bottle" for t in out)


def test_report_has_table():
    m = {"photos": 1, "top1": 100.0, "top2_recall": 100.0, "group_accuracy": 100.0,
         "accuracy_on_ok": 100.0, "confident_wrong": 0.0, "uncertain": 0.0,
         "hazard_recall": None, "hazard_photos": 0, "confusion": {"glass": {"glass": 1}}}
    assert "| top1 | 100.0 % |" in replay.report_md(m, "x")
