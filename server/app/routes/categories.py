# File: server/app/routes/categories.py
from fastapi import APIRouter

from app import catalog
from app.errresp import error_response

router = APIRouter()


@router.get("/categories")
def categories(lang: str = "en"):
    if lang not in ("ar", "en"):
        return error_response("invalid_request", 422, "en")
    return {"version": 1, "categories": catalog.load_categories(lang)}
