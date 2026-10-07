# File: server/app/errresp.py
from fastapi.responses import JSONResponse

MESSAGES = {
    "invalid_image": ("The image could not be read.", "تعذّر قراءة الصورة."),
    "image_too_large": ("Image must be 2 MB or less.", "يجب ألا يتجاوز حجم الصورة 2 ميغابايت."),
    "unsupported_type": ("Use a JPEG, PNG or WebP image.", "استخدم صورة JPEG أو PNG أو WebP."),
    "invalid_request": ("Invalid request.", "طلب غير صالح."),
    "rate_limited": ("Too many requests. Try again shortly.", "طلبات كثيرة. حاول بعد قليل."),
    "all_sources_failed": ("Analysis is unavailable right now.", "التحليل غير متاح حاليًا."),
    "overloaded": ("Server is busy. Retry in a moment.", "الخادم مشغول. أعد المحاولة بعد قليل."),
    "internal_error": ("Unexpected error.", "حدث خطأ غير متوقع."),
}


def error_response(code, status, lang="en", rid=None, headers=None) -> JSONResponse:
    en, ar = MESSAGES.get(code, MESSAGES["internal_error"])
    body = {"error": {"code": code, "message": ar if lang == "ar" else en, "request_id": rid}}
    return JSONResponse(body, status_code=status, headers=headers)
