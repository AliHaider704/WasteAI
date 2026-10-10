# File: scripts/make_audio.py
"""Builds the spoken audio for category names and steps once, offline, with Piper (MIT).
Output: frontend/audio/<lang>/<category_id>/<n>.(ogg|wav) and frontend/audio/manifest.json.
Run in a throw-away venv, never in the app venv:
  python3 -m venv /tmp/piper && /tmp/piper/bin/pip install piper-tts
  mkdir -p /tmp/voices && /tmp/piper/bin/python -m piper.download_voices --data-dir /tmp/voices ar_JO-kareem-medium en_US-lessac-medium
  /tmp/piper/bin/python scripts/make_audio.py --voices /tmp/voices [--only plastic_pet] [--dry]
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE = {"ar": "ar_JO-kareem-medium", "en": "en_US-lessac-medium"}
LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "إيه بي سي دي إي إف جي إتش آي جيه كيه إل إم إن أو بي كيو آر إس تي يو في دبليو إكس واي زد".split()))


def speakable(text, lang):
    s = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", text)).strip()
    if lang == "ar":  # same rule as frontend/js/speech.js
        s = re.sub(r"\b[A-Z]{2,6}\b", lambda m: " ".join(LETTERS.get(c, c) for c in m.group()), s)
        s = re.sub(r"\(\s*(\d)\s*\)", r"، \1", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voices", required=True, help="folder with the downloaded Piper voices")
    ap.add_argument("--only", help="one category id (for a first listen)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    out = ROOT / "frontend" / "audio"
    manifest = {"_path": "frontend/audio/manifest.json", "voices": VOICE}
    total = 0
    for lang in ("ar", "en"):
        cats = json.loads((ROOT / "content" / f"guidance.{lang}.json").read_text("utf-8"))["categories"]
        manifest[lang] = {}
        for cid, c in cats.items():
            if a.only and cid != a.only:
                continue
            files = []
            for n, text in enumerate([c["name"], *c["steps"]]):
                total += 1
                ext = "ogg" if ffmpeg else "wav"
                rel = f"{lang}/{cid}/{n}.{ext}"
                files.append(rel)
                if a.dry:
                    continue
                dest = out / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                wav = dest.with_suffix(".wav")
                subprocess.run([sys.executable, "-m", "piper", "-m", VOICE[lang], "--data-dir", a.voices, "-f", str(wav)],
                               input=speakable(text, lang).encode("utf-8"), check=True)
                if ffmpeg:
                    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libopus", "-b:a", "24k", str(dest)], check=True)
                    wav.unlink()
            manifest[lang][cid] = files
    if not a.dry:
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
    print(("dry run: " if a.dry else "done: ") + f"{total} clips, format {'ogg' if ffmpeg else 'wav (no ffmpeg)'}")


if __name__ == "__main__":
    main()
