# File: scripts/check_paths.py
"""Rule 1 checker: line 1 of every file names the file's own relative path.

Formats by type:
  .py .sh .yaml .yml .toml .txt .tpl .service .example -> ``# File: <path>``
  .js                                                 -> ``// File: <path>``
  .css                                                -> ``/* File: <path> */``
  .html .md                                           -> ``<!-- File: <path> -->``
  .json                                               -> top-level ``"_path"`` equals <path>

Usage: python3 scripts/check_paths.py [dir ...]   (default: server deploy scripts)
Exits 1 and lists offenders when any file is wrong.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIRS = ("server", "deploy", "scripts")
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "eval_photos"}
HASH_EXT = {".py", ".sh", ".yaml", ".yml", ".toml", ".txt", ".tpl", ".service", ".example"}


def expected_line(rel: str) -> str | None:
    """Return the exact expected first line, or None when the type is not checked."""
    ext = Path(rel).suffix.lower()
    if ext in HASH_EXT:
        return f"# File: {rel}"
    if ext == ".js":
        return f"// File: {rel}"
    if ext == ".css":
        return f"/* File: {rel} */"
    if ext in {".html", ".md"}:
        return f"<!-- File: {rel} -->"
    return None


def check_file(path: Path, root: Path = ROOT) -> str | None:
    """Return an error message for one file, or None when it is fine."""
    rel = path.relative_to(root).as_posix()
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return f"{rel}: unreadable JSON ({exc})"
        got = data.get("_path") if isinstance(data, dict) else None
        return None if got == rel else f"{rel}: _path is {got!r}, expected {rel!r}"
    want = expected_line(rel)
    if want is None:
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            first = fh.readline().rstrip("\r\n")
    except (OSError, UnicodeDecodeError) as exc:
        return f"{rel}: unreadable ({exc})"
    return None if first == want else f"{rel}: line 1 is {first!r}, expected {want!r}"


def iter_files(base: Path):
    for p in sorted(base.rglob("*")):
        if p.is_file() and not (set(p.relative_to(base).parts[:-1]) & SKIP_DIRS):
            yield p


def run(dirs: list[str], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for d in dirs:
        base = root / d
        if not base.is_dir():
            errors.append(f"{d}: directory not found")
            continue
        for f in iter_files(base):
            err = check_file(f, root)
            if err:
                errors.append(err)
    return errors


def main(argv: list[str]) -> int:
    errors = run(argv or list(DEFAULT_DIRS))
    if errors:
        print(f"PATH HEADER ERRORS ({len(errors)}):")
        for e in errors:
            print("  " + e)
        return 1
    print("OK: all path headers match")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
