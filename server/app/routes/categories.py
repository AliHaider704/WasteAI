# File: server/app/routes/categories.py
from fastapi import APIRouter

from app import catalog
from app.errors import build_error

router = APIRouter()


@router.get("/categories")
def categories(lang: str = "en"):
    if lang not in ("ar", "en"):
        return build_error("invalid_request", "en")
    return {"version": 1, "categories": catalog.load_categories(lang)}
