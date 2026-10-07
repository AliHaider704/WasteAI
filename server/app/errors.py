# File: server/app/errors.py
"""Stable error codes (ARCHITECTURE section 4) with ar/en messages."""
from fastapi import Request
from fastapi.responses import JSONResponse

# code -> (http status, en, ar)
ERRORS: dict[str, tuple[int, str, str]] = {
    "invalid_image": (400, "The image could not be read.", "تعذّرت قراءة الصورة."),
    "image_too_large": (
        413, "Image must be 2 MB or less.", "يجب ألا يتجاوز حجم الصورة 2 ميغابايت."
    ),
    "unsupported_type": (
        415, "Use a JPEG, PNG or WebP image.", "استخدم صورة بصيغة JPEG أو PNG أو WebP."
    ),
    "invalid_request": (422, "The request is not valid.", "الطلب غير صالح."),
    "rate_limited": (429, "Too many requests. Please wait.", "طلبات كثيرة. يرجى الانتظار."),
    "all_sources_failed": (502, "No analysis source responded.", "لم يستجب أي مصدر للتحليل."),
    "overloaded": (503, "The service is busy. Try again.", "الخدمة مشغولة. حاول مرة أخرى."),
    "internal_error": (500, "Unexpected error.", "حدث خطأ غير متوقع."),
}


class AppError(Exception):
    def __init__(self, code: str, headers: dict[str, str] | None = None):
        self.code = code
        self.headers = headers or {}


def error_response(
    request: Request, code: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    status, en, ar = ERRORS.get(code, ERRORS["internal_error"])
    lang = request.query_params.get("lang", "en")
    body = {
        "error": {
            "code": code,
            "message": ar if lang == "ar" else en,
            "request_id": getattr(request.state, "request_id", ""),
        }
    }
    return JSONResponse(body, status_code=status, headers=headers)
