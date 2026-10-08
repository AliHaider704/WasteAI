# File: server/tests/test_hygiene.py
"""Tests for scripts/check_hygiene.py (good and bad temp trees)."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_hygiene.py"
spec = importlib.util.spec_from_file_location("check_hygiene", SCRIPT)
ch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ch)


def _w(root: Path, rel: str, text: str = "x\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_clean_tree(tmp_path):
    _w(tmp_path, "server/.env.example")
    _w(tmp_path, "a.py", "print('hi')\n")
    _w(tmp_path, "README.md", "mail me at you" + "@gmail.com\n")  # md is exempt
    assert ch.run(tmp_path) == []


def test_merge_marker(tmp_path):
    _w(tmp_path, "a.js", "ok\n" + "<" * 7 + " HEAD\n")
    assert any("merge marker" in e for e in ch.run(tmp_path))


def test_email_and_key(tmp_path):
    _w(tmp_path, "a.sh", "mail=someone" + "@gmail.com\n")
    _w(tmp_path, "b.py", "k = 'AKIA" + "A" * 16 + "'\n")
    errs = ch.run(tmp_path)
    assert any("email" in e for e in errs) and any("key-like" in e for e in errs)


def test_duplicate_env_and_db(tmp_path):
    _w(tmp_path, "server/.env.example")
    _w(tmp_path, "env.example")
    _w(tmp_path, "server/data/app.db", "x")
    errs = ch.run(tmp_path)
    assert any("duplicate env" in e for e in errs) and any("database" in e for e in errs)
