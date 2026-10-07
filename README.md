<!-- File: README.md -->
# WasteAI

Live site: https://wasteai.duckdns.org/

WasteAI is a web app that tells you how to dispose of an item. Upload a photo and it returns a waste category and disposal instructions. Arabic (RTL) and English, light and dark themes, works on phones, tablets and desktops.

> **Status:** under active development.
> Built as coursework in the Department of Artificial Intelligence, College of Science, Alkafeel University.

> **This is a guidance tool, not a legal authority.** Hazardous and medical waste always carry a "check your local authorities" note.

---

## Overview

Most people aren't sure which bin an item goes in, and wrong guesses end up contaminating recycling. WasteAI uses computer vision to sort items into 26 categories (plastics by resin code, paper, glass, metals, organic, e-waste, batteries, textiles, hazardous, medical and more), grouped into the broad families recyclable, organic, hazardous, general and e-waste, and shows disposal instructions for each.

Features:

* Classify an item from a photo: camera capture or upload (drag and drop supported).
* A reference section (Browse) covering the categories, disposal rules and recycling symbols, with search and group filters.
* Honest confidence: High / Medium / Not sure, with two alternatives when unsure.
* "Why?" panel showing the labels from each source, in the user's language.
* "This is wrong?" feedback with a full category picker.
* Arabic and English interface, 100% in each language (resin codes and file formats such as PET, HDPE, JPEG are the only Latin tokens inside Arabic text).
* Optional calm sound cues, WCAG AA contrast, keyboard navigation, reduced-motion support.
* Private: photos are never stored; buffers are deleted right after analysis.

## How it works

```
Browser -> Nginx (HTTPS) -> FastAPI -> local ONNX model + Azure AI Vision (+ optional ReciclAPI)
                                    -> rule-based mapper -> aggregator -> localized result
```

No generative AI is used for classification. Labels from the sources are mapped to categories with transparent JSON rules (`server/data/label_rules/`), then combined (0.6 local + 0.4 Azure). An optional free-tier LLM tiebreaker exists but is **off by default** and needs per-photo consent. See `docs/ARCHITECTURE.md`.

## Accuracy

Measured on our own field test of real photos. No marketing claims.

| Metric | Result |
| --- | --- |
| Photos tested | TBD (field test not run yet) |
| Top-1 accuracy | TBD |
| "Not sure" rate | TBD |
| Hazard categories recall | TBD |

Full report: `docs/FIELD_TEST_REPORT.md`. Weak spot: plastic resin types cannot be seen reliably, so the default is "Plastic (type unknown)".

## Authors

Ali Hayder and Muhammad Najm, Department of Artificial Intelligence, College of Science, Alkafeel University.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | Vanilla ES modules, CSS custom properties, no build step |
| Backend | Python 3.12, FastAPI, uvicorn (1 worker) |
| Database | SQLite (cache, quota, feedback) |
| ML | ONNX Runtime (CPU) with a converted trash classifier, Azure AI Vision (free tier), Pillow |
| Server | Ubuntu 24.04, Nginx, systemd, Certbot (no Docker, Redis or Node) |

---

## Getting Started

### Prerequisites

* Python 3.12
* Git
* A modern browser (the camera needs HTTPS or `localhost`)

### Setup

1. Clone the repository:

```bash
   git clone https://github.com/AliHaider704/WasteAI.git
   cd WasteAI
```

2. Copy the example environment file:

```bash
   cp server/.env.example server/.env
```

3. Fill in `server/.env` (secrets stay here only, it is git-ignored):

```env
   MODEL_PATH=models/model.onnx
   MODEL_LABELS_PATH=server/data/model_labels.json
   AZURE_VISION_ENDPOINT=
   AZURE_VISION_KEY=
   RECICLAPI_KEY=
   LOG_LEVEL=INFO
   LLM_TIEBREAKER_ENABLED=false
```

   Azure and ReciclAPI are disabled when their values are empty. `MODEL_URL` and `MODEL_SHA256` are used by the installer to download the model.

### Run locally

1. Install dependencies and start the server:

```bash
   cd server && python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --port 8100
```

2. In a second terminal, start the frontend (no build step):

```bash
   cd frontend
   python3 -m http.server 8000
```

3. Open http://localhost:8000. Until the server runs, add `?mock=1` to use the data in `frontend/mock/` (scenarios: `?scenario=uncertain|hazard|rate_limited|image_too_large|all_sources_failed`).

### Checks

```bash
cd server && pytest -q && ruff check . && cd ..
bash scripts/check_lines.sh               # every file under 500 lines
python3 scripts/check_paths.py            # line 1 names the file's own path
python3 content/tools/check_content.py    # ar/en parity, allow-list, label coverage
python3 content/tools/check_tokens.py     # CSS tokens, contrast, font licences
bash scripts/parity_check.sh              # local versus server parity (read-only)
```

### Deployment

One idempotent script for an Ubuntu 24.04 server: `bash deploy/install.sh --domain <DOMAIN> --email <EMAIL>`. Flags: `--status`, `--rollback`, `--fix-owner`, `--stop-containers`. Run it again after every `git pull`. Details: `docs/DEPLOYMENT.md`.

### API

Base path `/api/v1` (frozen contract in `contract/openapi.yaml`): `GET /health`, `GET /categories?lang=ar|en`, `POST /classify?lang=ar|en` (multipart field `image`, up to 2 MB), `POST /feedback`, `POST /log`. Rate limits apply (429 with `Retry-After`).

### Project structure

```
server/    FastAPI service, sources, mapper, aggregator, tests
frontend/  Vanilla ES modules, CSS tokens, i18n, mock data
content/   Disposal guidance (ar, en) and check tools
contract/  Frozen API contract (OpenAPI, categories, errors)
deploy/    Installer and templates
scripts/   Check scripts, field test, parity check
docs/      Architecture, decisions, deployment, field test
sessions/  Phase and session history files
```

## Privacy

Images are processed in memory and discarded. Only the result JSON is cached (7 days, keyed by image hash). Feedback stores the request ID and the chosen category. Server logs hold no IP address, no request body and no image. No accounts, no tracking.

## Roadmap

- [x] Project structure and backend API setup
- [ ] ML image classification integration (local model is live on the server; accuracy on real photos not measured yet)
- [ ] User dashboard and search history (not planned for v1: no accounts)
- [ ] Admin panel for content management
- [ ] Mobile layout and PWA support (mobile layout done in the CSS, PWA only after a real-phone camera test)
- [x] Multi-language support (Arabic and English)

## Contributing

See `CONTRIBUTING.md`. Rules: files under 500 lines, free and open-source dependencies only, all UI text in i18n files, RTL-safe CSS, English for code, comments, commits and logs.

## License

TBD (decided after the model and dataset license check, D-011 and D-016).

## Credits

Local model: `emilyyy04/trash_classifier`, converted to ONNX (D-011).
Fonts (SIL Open Font License, each with its `OFL.txt` in `frontend/assets/fonts/`): IBM Plex Sans, IBM Plex Sans Arabic, Newsreader, Noto Naskh Arabic.
Icons: Lucide (ISC) for interface glyphs; the category pictograms are drawn for this project.
