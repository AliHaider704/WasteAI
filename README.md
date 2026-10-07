<!-- File: README.md -->
# AI Waste Segregation System

Live site: https://wasteai.duckdns.org/

Take or upload a photo of a waste item and get the waste category, the right bin, and clear disposal steps. Arabic (RTL) and English, light and dark themes, works on phones, tablets and desktops.

> **This is a guidance tool, not a legal authority.** Hazardous and medical waste always carry a "check your local authorities" note.

## Screenshots
<!-- TODO(M16): add ar/en and light/dark screenshots in docs/img/ -->

## Features
- Camera capture or photo upload (drag and drop supported)
- 26 categories: plastics by resin code, paper, glass, metals, organic, e-waste, batteries, textiles, hazardous, medical, and more
- Honest confidence: High / Medium / Not sure, with two alternatives when unsure
- "Why?" panel showing the labels from each source
- "This is wrong?" feedback to improve the rules
- Calm optional sound design (synthesized in the browser, no audio files)
- Accessible: WCAG AA contrast, keyboard navigation, reduced-motion support
- Private: photos are never stored; buffers are deleted right after analysis

## How it works
```
Browser -> Nginx (HTTPS) -> FastAPI -> local ONNX model + Azure AI Vision (+ optional ReciclAPI)
                                    -> rule-based mapper -> aggregator -> localized result
```
No generative AI is used for classification. Labels from the sources are mapped to our categories with transparent JSON rules (`server/data/label_rules/`, 10 files), then combined (0.6 local + 0.4 Azure, renormalized over the sources that answered). See `docs/ARCHITECTURE.md`.

Local model: `emilyyy04/trash_classifier`, converted to ONNX (decision D-011). It is chosen by our own photo evaluation, not by published accuracy. Its license is MIT on the model card only and its training data is undocumented; this is rechecked before the project license is fixed.

## Accuracy
Measured on our own field test of real photos. No marketing claims.

| Metric | Result |
|---|---|
| Photos tested | TBD (S3 field test) |
| Top-1 accuracy | TBD |
| "Not sure" rate | TBD |
| Hazard categories recall | TBD |

Full report: `docs/FIELD_TEST_REPORT.md`. Weak spots: plastic resin types cannot be seen reliably, so the default is "Plastic (type unknown)" unless a label says otherwise.

Model selection run (A2, 8 photos per category, local model alone, **not** the system test above): top-1 39.6%, top-3 61.5%, group accuracy 50.0%, p95 latency 11 ms, RSS 89 MB (peak 110 MB). The official baseline on about 100 owner photos has not been run yet.

## Quick start (development)
```bash
git clone https://github.com/AliHaider704/WasteAI.git && cd WasteAI
# Server
cd server && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set MODEL_PATH, optional AZURE_VISION_KEY
uvicorn app.main:app --port 8100 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1
# Frontend (no build step), in a second terminal
cd frontend && python3 -m http.server 8000
```
Open `http://localhost:8000`. The camera needs HTTPS or `localhost`. Until the server runs, the frontend can use `frontend/mock/` data.

## API
Base path `/api/v1`. The contract is frozen in `contract/openapi.yaml`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness and source status (`up`, `down`, `quota`, `disabled`) |
| GET | `/categories?lang=ar\|en` | category list with localized names and guidance |
| POST | `/classify?lang=ar\|en` | multipart field `image` (jpeg, png, webp, up to 2 MB) |
| POST | `/feedback` | correct a result (only for a `request_id` the server issued in the last 7 days, one per id) |
| POST | `/log` | client error log sink (20 per minute per client, 204) |

Errors use one JSON shape with a stable `code` and a localized `message`; 429 carries `Retry-After`.

## Checks
Run from the repository root.

```bash
cd server && pytest -q && ruff check . && cd ..
bash scripts/check_lines.sh          # every file under 500 lines
python3 scripts/check_paths.py       # line 1 of each file names its own path
python3 content/tools/check_content.py   # ar/en parity, allow-list, categories
bash scripts/parity_check.sh --public-base https://wasteai.duckdns.org   # local vs host parity, read-only
```
`parity_check.sh` prints PASS, FAIL or SKIP per item and exits 1 on any FAIL. Run it on the laptop and again on the host.

## Deployment
One idempotent script for an Ubuntu 24.04 server: `bash deploy/install.sh --domain <DOMAIN> --email <EMAIL>`. Flags: `--status`, `--rollback`, `--fix-owner`, `--stop-containers`. Run it again after every `git pull`: Nginx serves the synced copy in `/home/ubuntu/waste_ai/`, not the clone. Details: `docs/DEPLOYMENT.md`.

Edge protection (Nginx): one security-header snippet included in every location, a CSP with explicit `script-src 'self'`, JSON `image_too_large` for uploads above 3 MB, and a rate limit of 10 requests per minute on `/api/v1/classify` returning 429 with `Retry-After`. The app has its own per-client limiter as a second layer.

## Configuration
| Variable | Purpose |
|---|---|
| `MODEL_PATH` | Local ONNX model file |
| `MODEL_LABELS_PATH` | Label list for the active model (`server/data/model_labels.json`) |
| `AZURE_VISION_ENDPOINT`, `AZURE_VISION_KEY` | Azure AI Vision (free F0 tier); disabled if empty |
| `RECICLAPI_KEY` | Optional third source; off by default |
| `MODEL_URL`, `MODEL_SHA256` | Used by the installer to download and verify the model |
| `LOG_LEVEL` | Server log level, default `INFO` |

Secrets live only in `.env` (git-ignored). Note: `server/.env.example` still names the hash `MODEL_SHA`; the installer reads `MODEL_SHA256` (fix pending).

## Project structure
```
server/    FastAPI service, sources, mapper, aggregator, tests
frontend/  Vanilla ES modules, CSS tokens, i18n, mock data
content/   Disposal guidance (ar, en) and content checks
contract/  Frozen API contract (OpenAPI, categories, errors)
deploy/    Installer and templates
scripts/   Checks (lines, path headers, parity) and field tests
docs/      Architecture, decisions, deployment, field test
sessions/  Phase plans and session history
```

## Privacy
Images are processed in memory and discarded. Only the result JSON is cached (7 days, keyed by image hash). Feedback stores the request ID and the chosen category. Server logs are JSON in English and hold no client IP, no request body and no image. No accounts, no tracking.

## Contributing
See `CONTRIBUTING.md`. Rules: files < 500 lines, free and open-source dependencies only, all UI text in i18n files, RTL-safe CSS, line 1 of every file names its own path.

## License
TBD (decided after the model and dataset license check, D-011 and D-016). No `LICENSE` file is added until then.

## Credits
Models, datasets, fonts and icons with their licenses: filled in Phase M16. Currently planned: IBM Plex Sans Arabic and IBM Plex Sans, Noto Naskh Arabic and Newsreader (category names), Lucide icons (ISC) for interface glyphs. Font license files are checked when the fonts are added.
