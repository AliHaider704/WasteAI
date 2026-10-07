# AI Waste Segregation System

Take or upload a photo of a waste item and get the waste category, the right bin, and clear disposal steps. Arabic (RTL) and English, light and dark themes, works on phones, tablets and desktops.

> **This is a guidance tool, not a legal authority.** Hazardous and medical waste always carry a "check your local authorities" note.

## Screenshots
<!-- TODO(M7): add ar/en and light/dark screenshots in docs/img/ -->

## Features
- Camera capture or photo upload (drag and drop supported)
- 26 categories: plastics by resin code, paper, glass, metals, organic, e-waste, batteries, textiles, hazardous, medical, and more
- Honest confidence: High / Medium / Not sure, with two alternatives when unsure
- "Why?" panel showing the raw labels from each source
- "This is wrong?" feedback to improve the rules
- Calm optional sound design (synthesized in the browser, no audio files)
- Accessible: WCAG AA contrast, keyboard navigation, reduced-motion support
- Private: photos are never stored; buffers are deleted right after analysis

## How it works
```
Browser -> Nginx (HTTPS) -> FastAPI -> local ONNX model + Azure AI Vision (+ optional ReciclAPI)
                                    -> rule-based mapper -> aggregator -> localized result
```
No generative AI is used for classification. Labels from the sources are mapped to our categories with transparent JSON rules (`backend/data/label_rules/`), then combined (0.6 local + 0.4 Azure). See `docs/ARCHITECTURE.md`.

## Accuracy
Measured on our own field test of real photos. No marketing claims.

| Metric | Result |
|---|---|
| Photos tested | TBD (S3 field test) |
| Top-1 accuracy | TBD |
| "Not sure" rate | TBD |
| Hazard categories recall | TBD |

Full report: `docs/FIELD_TEST_REPORT.md`. Weak spots: plastic resin types cannot be seen reliably, so the default is "Plastic (type unknown)" unless a label says otherwise.

## Quick start (development)
```bash
git clone https://github.com/AliHaider704/WasteAI.git && cd WasteAI
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set MODEL_PATH, optional AZURE_VISION_KEY
uvicorn app.main:app --port 8100
# Frontend (no build step)
cd ../frontend && python3 -m http.server 8000
```
Open `http://localhost:8000`. The camera needs HTTPS or `localhost`. Until the backend runs, the frontend can use `frontend/mock/` data.

## Deployment
One idempotent script for an Ubuntu 24.04 server: `bash deploy/install.sh`. Flags: `--status`, `--rollback`, `--fix-owner`, `--stop-containers`. Details: `docs/DEPLOYMENT.md`.

## Configuration
| Variable | Purpose |
|---|---|
| `MODEL_PATH` | Local ONNX model file |
| `AZURE_VISION_ENDPOINT`, `AZURE_VISION_KEY` | Azure AI Vision (free F0 tier); disabled if empty |
| `RECICLAPI_KEY` | Optional third source; off by default |
| `MODEL_URL`, `MODEL_SHA256` | Used by the installer to download the model |

Secrets live only in `.env` (git-ignored).

## Project structure
```
backend/   FastAPI service, sources, mapper, aggregator, tests
frontend/  Vanilla ES modules, CSS tokens, i18n, mock data
content/   Disposal guidance (ar, en)
contract/  Frozen API contract (OpenAPI, categories, errors)
deploy/    Installer and templates
docs/      Architecture, decisions, deployment, field test
```

## Privacy
Images are processed in memory and discarded. Only the result JSON is cached (7 days, keyed by image hash). Feedback stores the request ID and the chosen category. No accounts, no tracking.

## Contributing
See `CONTRIBUTING.md`. Rules: files <= 500 lines, free and open-source dependencies only, all UI text in i18n files, RTL-safe CSS.

## License
TBD (decided in Phase M7 after the model and dataset license check, D-011).

## Credits
Models, datasets, fonts (IBM Plex Sans Arabic, Inter) and icons (Lucide) with their licenses: filled in Phase M7.
