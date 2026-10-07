<!-- File: server/eval/README.md -->
Model evaluation for Phase A2 (decides D-009 / D-011). Runs on the **dev PC only**; never add torch/ultralytics to `server/requirements.txt`.

## Setup
```bash
cd server/eval
python3 -m venv .venv && source .venv/bin/activate
pip install onnxruntime numpy Pillow psutil
```

## Steps
1. Put 60-100 real photos in `eval_photos/<category_id>/` (ID from `contract/categories.json`; gitignored). Include common local waste, mixed lighting, cluttered backgrounds.
2. `python prepare_images.py` -> `eval_photos_prepared/` (EXIF stripped, <= 1024 px, JPEG q85, same as production).
3. Get each candidate as ONNX (export on a PC with torch/ultralytics if needed; keep that env separate). Check `config.json` `id2label` against `../data/model_labels.json`; add a label set if it differs.
4. Run each candidate:
```bash
python run_eval.py --name mobilenet_v2_garbage --model m.onnx --label-set garbage12 --size 224 --norm imagenet
python run_eval.py --name wastewise_yolov8n_cls --model w.onnx --label-set trashnet6 --size 224 --norm unit --resize crop
```
   Flags: `--norm imagenet|unit|raw`, `--layout nchw|nhwc`, `--resize squash|crop`. Wrong norm silently lowers accuracy: check the model card.
5. Copy the numbers from `runs/*.md` into `results.md`, record licenses of the model AND its dataset (AGPL / non-commercial = reject or flag), choose one model.
6. Set `"active"` in `../data/model_labels.json`, append a DECISIONS entry closing D-011, compute `sha256sum model.onnx` for `MODEL_URL` / `MODEL_SHA256` in `.env.example`.
