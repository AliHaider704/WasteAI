# File: content/tools/fix_camera_ar.py
"""One-off: wrap Latin tokens in two Arabic camera strings in <bdi dir="ltr"> and allow them."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOKENS = ["brave://settings/content/camera", "Brave", "Shields"]

ar_path = ROOT / "frontend" / "i18n" / "ar.json"
ar = json.loads(ar_path.read_text("utf-8"))
def wrap(tok):
    return f'<bdi dir="ltr">{tok}</bdi>'


for key in ("camera.blocked", "camera.dismissed"):
    text = ar[key]
    if "<bdi" not in text:
        text = text.replace(TOKENS[0], "\0")
        text = text.replace("Brave", wrap("Brave")).replace("Shields", wrap("Shields"))
        text = text.replace("\0", wrap(TOKENS[0]))
        ar[key] = text
ar_path.write_text(json.dumps(ar, ensure_ascii=False, indent=2) + "\n", "utf-8")

al_path = ROOT / "content" / "tools" / "allowlist.json"
al = json.loads(al_path.read_text("utf-8"))
for tok in TOKENS:
    if tok not in al["tokens"]:
        al["tokens"].append(tok)
al_path.write_text(json.dumps(al, ensure_ascii=False, indent=2) + "\n", "utf-8")
print("done")
