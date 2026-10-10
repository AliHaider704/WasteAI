# File: scripts/build_clip_prompts.py
"""A40 (dev machine only): encode text prompts per category -> server/data/clip_text.json.

  pip install onnxruntime tokenizers numpy
  python3 scripts/build_clip_prompts.py --text-model text.onnx --tokenizer tokenizer.json --model-name <id>
The text encoder never ships to the server. It must take int64 input_ids [batch, 77] and return
embeddings [batch, dim] as its first output. Check the model card licence first (non-commercial: reject).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "server" / "data" / "clip_text.json"
PROMPTS = {
    "plastic_pet": ["a photo of a clear plastic water bottle, waste", "a photo of a crushed PET soda bottle"],
    "plastic_hdpe": ["a photo of an opaque plastic milk jug", "a photo of a plastic detergent bottle, waste"],
    "plastic_pvc": ["a photo of a PVC plastic pipe", "a photo of a rigid PVC plastic packaging, waste"],
    "plastic_ldpe": ["a photo of a thin plastic bag, waste", "a photo of crumpled plastic film"],
    "plastic_pp": ["a photo of a plastic food container with a lid", "a photo of a plastic bottle cap"],
    "plastic_ps": ["a photo of white styrofoam packaging", "a photo of a plastic foam cup, waste"],
    "plastic_other": ["a photo of mixed plastic waste", "a photo of a hard plastic item, waste"],
    "plastic_unknown": ["a photo of a plastic item, waste", "a photo of plastic packaging, waste"],
    "paper": ["a photo of old newspaper, waste", "a photo of crumpled paper sheets"],
    "cardboard": ["a photo of a flattened cardboard box", "a photo of corrugated cardboard, waste"],
    "carton_beverage": ["a photo of a milk or juice carton, waste", "a photo of a drink carton box"],
    "glass": ["a photo of an empty glass bottle, waste", "a photo of a glass jar"],
    "metal_aluminum": ["a photo of a crushed aluminium drink can", "a photo of aluminium foil, waste"],
    "metal_steel": ["a photo of a steel food tin can, waste", "a photo of a rusty steel can"],
    "metal_other": ["a photo of scrap metal, waste", "a photo of a metal object, waste"],
    "organic_food": ["a photo of food scraps, waste", "a photo of fruit and vegetable peels"],
    "organic_garden": ["a photo of garden waste, leaves and branches", "a photo of cut grass, waste"],
    "ewaste_small": ["a photo of an old mobile phone", "a photo of a charger and cables, e-waste"],
    "ewaste_large": ["a photo of a broken television", "a photo of an old washing machine or fridge"],
    "battery": ["a photo of used batteries", "a photo of a lithium battery pack"],
    "textile": ["a photo of old clothes, waste", "a photo of used fabric and shoes"],
    "hazardous_chemical": ["a photo of a paint can or chemical container", "a photo of a pesticide spray bottle"],
    "medical": ["a photo of used syringes and medical waste", "a photo of pill blister packs and bandages"],
    "wood": ["a photo of wood planks, waste", "a photo of broken wooden furniture"],
    "construction": ["a photo of concrete and brick rubble", "a photo of construction debris"],
    "general_residual": ["a photo of mixed household trash", "a photo of a dirty diaper or unrecyclable waste"],
}


def encode(session, tok, texts: list[str]) -> np.ndarray:
    ids = np.asarray([e.ids for e in tok.encode_batch(texts)], dtype=np.int64)
    out = np.asarray(session.run(None, {session.get_inputs()[0].name: ids})[0], dtype=np.float32)
    return out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-12)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--text-model", required=True, type=Path)
    ap.add_argument("--tokenizer", required=True, type=Path)
    ap.add_argument("--model-name", default="")
    ap.add_argument("--context", type=int, default=77)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    import onnxruntime as ort
    from tokenizers import Tokenizer

    wanted = {c["id"] for c in json.loads((ROOT / "contract" / "categories.json").read_text("utf-8"))["categories"]}
    if wanted != set(PROMPTS):
        print("FAIL: prompts do not match categories:", sorted(wanted ^ set(PROMPTS)))
        return 1
    tok = Tokenizer.from_file(str(a.tokenizer))
    tok.enable_padding(length=a.context)
    tok.enable_truncation(a.context)
    sess = ort.InferenceSession(str(a.text_model), providers=["CPUExecutionProvider"])
    cats = {}
    for cid, texts in sorted(PROMPTS.items()):
        v = encode(sess, tok, texts).mean(axis=0)
        cats[cid] = [round(float(x), 6) for x in v / (np.linalg.norm(v) + 1e-12)]
    a.out.write_text(json.dumps({"_path": "server/data/clip_text.json", "model": a.model_name,
                                 "categories": cats}) + "\n", "utf-8")
    print(f"wrote {len(cats)} category vectors (dim {len(next(iter(cats.values())))}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
