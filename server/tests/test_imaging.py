# File: server/tests/test_imaging.py
import asyncio
import io

import pytest
from PIL import Image

from app.concurrency import Limiter, OverloadedError
from app.imaging import MAX_BYTES, MAX_SIDE, ImageError, detect_type, prepare, wipe


def _img_bytes(fmt: str, size=(64, 48), mode="RGB", **kw) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128)).save(buf, fmt, **kw)
    return buf.getvalue()


@pytest.mark.parametrize("fmt,kind", [("JPEG", "jpeg"), ("PNG", "png"), ("WEBP", "webp")])
def test_detect_type(fmt, kind):
    assert detect_type(_img_bytes(fmt)) == kind


def test_unsupported_type_415():
    with pytest.raises(ImageError) as e:
        prepare(b"GIF89a" + b"\x00" * 50)
    assert (e.value.code, e.value.status) == ("unsupported_type", 415)


def test_too_large_413():
    with pytest.raises(ImageError) as e:
        prepare(b"\xff\xd8\xff" + b"\x00" * MAX_BYTES)
    assert (e.value.code, e.value.status) == ("image_too_large", 413)


def test_corrupt_400():
    with pytest.raises(ImageError) as e:
        prepare(b"\xff\xd8\xff" + b"garbage" * 10)
    assert (e.value.code, e.value.status) == ("invalid_image", 400)


def test_resize_and_rgb():
    p = prepare(_img_bytes("PNG", size=(3000, 1500), mode="RGBA"))
    assert max(p.size) <= MAX_SIDE and p.image.mode == "RGB"
    p.close()


def test_exif_stripped_and_hash_stable():
    img = Image.new("RGB", (80, 60), (10, 120, 10))
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    a, b = prepare(buf.getvalue()), prepare(buf.getvalue())
    assert not a.image.getexif() and not a.image.info.get("exif")
    assert a.sha256 == b.sha256 and len(a.sha256) == 64


def test_wipe_bytearray():
    buf = bytearray(b"secret")
    wipe(buf)
    assert len(buf) == 0


def test_limiter_503_after_wait():
    async def run():
        lim = Limiter(slots=1, wait_s=0.1)
        async with lim.slot():
            with pytest.raises(OverloadedError) as e:
                async with lim.slot():
                    pass
            assert e.value.status == 503
        async with lim.slot():  # slot released again
            pass

    asyncio.run(run())


def test_animated_webp_rejected():
    buf = io.BytesIO()
    frames = [Image.new("RGB", (32, 32), c) for c in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(buf, "WEBP", save_all=True, append_images=frames[1:], duration=50)
    with pytest.raises(ImageError) as e:
        prepare(buf.getvalue())
    assert (e.value.code, e.value.status) == ("invalid_image", 400)


def test_pixel_cap_from_header(monkeypatch):
    monkeypatch.setattr("app.imaging.MAX_PIXELS", 1000)
    with pytest.raises(ImageError) as e:
        prepare(_img_bytes("PNG", size=(100, 100)))
    assert e.value.code == "invalid_image"


def test_content_must_match_magic_bytes():
    png = _img_bytes("PNG")
    with pytest.raises(ImageError) as e:  # JPEG magic, PNG body
        prepare(b"\xff\xd8\xff" + png[3:])
    assert e.value.status in (400, 415)


def test_error_body_shape_and_no_store():
    from app.errors import build_error
    r = build_error("invalid_image", "en", "rid1")
    assert r.headers["cache-control"] == "no-store"
    assert b"rid1" in r.body and b"Traceback" not in r.body
