# server/app/imaging.py
"""Image safety + preprocessing: magic bytes, decode, resize, strip EXIF, wipe buffers."""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 2 * 1024 * 1024
MAX_DECODE_SIDE = 1600
MAX_SIDE = 1024
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageError(Exception):
    """Contract error: code is stable (ARCHITECTURE §4), status is the HTTP status."""

    def __init__(self, code: str, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass
class PreparedImage:
    image: Image.Image  # clean RGB, longest side <= MAX_SIDE, no EXIF
    sha256: str  # hash of the resized pixels (cache key)

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size

    def close(self) -> None:
        self.image.close()


def detect_type(data: bytes) -> str | None:
    """Return 'jpeg' | 'png' | 'webp' from magic bytes, else None."""
    head = bytes(data[:12])
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def wipe(buf: bytearray | None) -> None:
    """Zero a mutable buffer in place (immutable bytes cannot be wiped; drop refs instead)."""
    if isinstance(buf, bytearray):
        buf[:] = bytes(len(buf))
        buf.clear()


def _to_clean_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P", "PA"):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    rgb = img.convert("RGB")
    clean = Image.new("RGB", rgb.size)  # fresh image: no EXIF / info carried over
    clean.paste(rgb)
    return clean


def prepare(data: bytes | bytearray) -> PreparedImage:
    """Validate and normalize an upload. Raises ImageError (413/415/400)."""
    if len(data) > MAX_BYTES:
        raise ImageError("image_too_large", 413)
    if detect_type(bytes(data[:12])) is None:
        raise ImageError("unsupported_type", 415)
    src = None
    try:
        src = Image.open(io.BytesIO(bytes(data)))
        if src.width * src.height > MAX_PIXELS:
            raise ImageError("invalid_image", 400)
        if src.format == "JPEG":  # cheap downscaled decode for large JPEGs
            src.draft("RGB", (MAX_DECODE_SIDE, MAX_DECODE_SIDE))
        src.load()
        oriented = ImageOps.exif_transpose(src) or src
        clean = _to_clean_rgb(oriented)
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise ImageError("invalid_image", 400) from None
    finally:
        if src is not None:
            src.close()
    clean.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    digest = hashlib.sha256(f"{clean.size}".encode() + clean.tobytes()).hexdigest()
    return PreparedImage(image=clean, sha256=digest)
