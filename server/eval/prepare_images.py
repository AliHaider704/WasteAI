# server/eval/prepare_images.py
"""Prepare eval photos like production: strip EXIF, resize <= 1024 px, JPEG q85.

Input:  eval_photos/<category_id>/*.jpg|png|webp|heic-converted
Output: eval_photos_prepared/<category_id>/NNN.jpg
Dev PC only. Requires: Pillow.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageOps

EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def prepare(src: Path, dst: Path, max_side: int = 1024) -> None:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")  # apply rotation, drop EXIF
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        im.save(dst, "JPEG", quality=85)  # saved without EXIF


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="eval_photos")
    ap.add_argument("--dst", default="eval_photos_prepared")
    a = ap.parse_args()
    src_root, dst_root = Path(a.src), Path(a.dst)
    total = 0
    for cat in sorted(p for p in src_root.iterdir() if p.is_dir()):
        out = dst_root / cat.name
        out.mkdir(parents=True, exist_ok=True)
        files = sorted(f for f in cat.iterdir() if f.suffix.lower() in EXTS)
        for i, f in enumerate(files, 1):
            try:
                prepare(f, out / f"{i:03d}.jpg")
            except OSError as e:
                print(f"skip {f}: {e}")
        print(f"{cat.name}: {len(files)}")
        total += len(files)
    print(f"total: {total} (target 60-100)")


if __name__ == "__main__":
    main()
