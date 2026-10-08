# File: scripts/check_hygiene.py
"""Repo hygiene guard (D-033). Fails on: merge markers, personal data or keys,
duplicate env templates, database files in the tree.

Usage: python3 scripts/check_hygiene.py [root]   (default: repo root)
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
             "eval_photos", "_converted", "fonts"}
BIN_EXT = {".woff2", ".png", ".jpg", ".jpeg", ".webp", ".onnx", ".zip", ".db", ".ico"}
MARK = re.compile(r"^(<{7}|>{7})(\s|$)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
EMAIL_OK = ("example.com", "example.org", "users.noreply.github.com")
KEYS = re.compile(r"AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}")
ENV_OK = "server/.env.example"


def files(root: Path):
    """Tracked files when root is a git repo (ignored local files do not count), else a walk."""
    if (root / ".git").exists():
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True)
        if out.returncode == 0:
            for rel in sorted(filter(None, out.stdout.split("\0"))):
                p = root / rel
                if p.is_file():
                    yield p
            return
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS):
            yield p


def run(root: Path = ROOT) -> list[str]:
    errs: list[str] = []
    for p in files(root):
        rel = p.relative_to(root).as_posix()
        if p.suffix.lower() == ".db" or ".db-" in p.name:
            errs.append(f"{rel}: database file in the tree")
        if p.name in {"env.example", ".env.example", "gitignore"} and rel != ENV_OK and p.name != "gitignore":
            errs.append(f"{rel}: duplicate env template (keep only {ENV_OK})")
        if p.name == "gitignore":
            errs.append(f"{rel}: stray copy of .gitignore")
        if p.suffix.lower() in BIN_EXT:
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        is_md = p.suffix.lower() == ".md"
        for n, line in enumerate(lines, 1):
            if MARK.match(line):
                errs.append(f"{rel}:{n}: merge marker")
            if is_md:
                continue
            if KEYS.search(line):
                errs.append(f"{rel}:{n}: key-like string")
            for m in EMAIL.findall(line):
                if not m.endswith(EMAIL_OK):
                    errs.append(f"{rel}:{n}: email-like string")
    return errs


if __name__ == "__main__":
    errors = run(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT)
    if errors:
        print(f"HYGIENE ERRORS ({len(errors)}):")
        print("\n".join(f"  {e}" for e in errors))
        sys.exit(1)
    print("OK: hygiene")
