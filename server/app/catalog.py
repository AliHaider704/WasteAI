# server/app/catalog.py
import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = Path(os.getenv("CONTRACT_DIR", ROOT / "contract"))
CONTENT_DIR = Path(os.getenv("CONTENT_DIR", ROOT / "content"))
HAZARD_IDS = {"battery", "hazardous_chemical", "medical", "ewaste_small", "ewaste_large"}


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _items(data) -> list:
    if isinstance(data, dict):
        data = data.get("categories", data)
    if isinstance(data, dict):
        return [{"id": k, **v} for k, v in data.items() if isinstance(v, dict)]
    return data if isinstance(data, list) else []


@lru_cache(maxsize=1)
def _base() -> list[dict]:
    return _items(_read(CONTRACT_DIR / "categories.json"))


@lru_cache(maxsize=4)
def _guidance(lang: str) -> dict[str, dict]:
    return {c["id"]: c for c in _items(_read(CONTENT_DIR / f"guidance.{lang}.json")) if "id" in c}


@lru_cache(maxsize=4)
def load_categories(lang: str) -> list[dict]:
    g = _guidance(lang)
    out = []
    for c in _base():
        e = g.get(c["id"], {})
        out.append({
            "id": c["id"],
            "name": e.get("name") or c.get("name") or c["id"],
            "group": c.get("group", ""),
            "bin": c.get("bin", "special"),
            "icon": c.get("icon", ""),
            "summary": e.get("summary", ""),
            "steps": e.get("steps", []),
            "warnings": e.get("warnings", []),
        })
    return out


def by_id(lang: str) -> dict[str, dict]:
    return {c["id"]: c for c in load_categories(lang)}


def is_hazard(category_id: str) -> bool:
    return category_id in HAZARD_IDS
