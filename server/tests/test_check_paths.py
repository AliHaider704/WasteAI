# File: server/tests/test_check_paths.py
"""Tests for scripts/check_paths.py (rule 1: line 1 names the file's own path)."""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_paths.py"
spec = importlib.util.spec_from_file_location("check_paths", SCRIPT)
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_expected_formats():
    assert cp.expected_line("server/a.py") == "# File: server/a.py"
    assert cp.expected_line("deploy/x.sh") == "# File: deploy/x.sh"
    assert cp.expected_line("frontend/js/a.js") == "// File: frontend/js/a.js"
    assert cp.expected_line("frontend/css/a.css") == "/* File: frontend/css/a.css */"
    assert cp.expected_line("docs/a.md") == "<!-- File: docs/a.md -->"
    assert cp.expected_line("server/data/a.bin") is None


def test_good_files_pass(tmp_path):
    _write(tmp_path, "server/a.py", "# File: server/a.py\nx = 1\n")
    _write(tmp_path, "server/README.md", "<!-- File: server/README.md -->\n")
    _write(tmp_path, "server/d.json", json.dumps({"_path": "server/d.json"}))
    assert cp.run(["server"], tmp_path) == []


def test_bad_py_header_listed(tmp_path):
    _write(tmp_path, "server/a.py", "# server/a.py\n")
    errs = cp.run(["server"], tmp_path)
    assert len(errs) == 1 and errs[0].startswith("server/a.py")


def test_wrong_and_missing_json_path(tmp_path):
    _write(tmp_path, "server/a.json", json.dumps({"_path": "server/other.json"}))
    _write(tmp_path, "server/b.json", json.dumps({"x": 1}))
    _write(tmp_path, "server/c.json", json.dumps([1, 2]))
    assert len(cp.run(["server"], tmp_path)) == 3


def test_missing_dir_and_skipped_dirs(tmp_path):
    _write(tmp_path, "server/__pycache__/x.py", "junk\n")
    assert cp.run(["server"], tmp_path) == []
    assert cp.run(["nope"], tmp_path) == ["nope: directory not found"]


def test_main_exit_codes(tmp_path, monkeypatch):
    _write(tmp_path, "server/a.py", "bad\n")
    real_run = cp.run
    monkeypatch.setattr(cp, "run", lambda dirs: real_run(dirs, tmp_path))
    assert cp.main(["server"]) == 1
    _write(tmp_path, "server/a.py", "# File: server/a.py\n")
    assert cp.main(["server"]) == 0


def test_real_repo_is_clean():
    assert cp.run(list(cp.DEFAULT_DIRS)) == []
