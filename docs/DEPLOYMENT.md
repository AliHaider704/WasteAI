# docs/DEPLOYMENT.md

Deploy on an Ubuntu 24.04 server with Nginx and a small amount of RAM. No Docker, Redis or Node is added.

## Requirements
- DNS A record for your subdomain pointing to the server (D-012).
- User `ubuntu` with sudo.
- Ports 80 and 443 open.

## Install
```bash
cd <repo>
bash deploy/install.sh --domain <SUBDOMAIN> --email you@example.com
```
Optional before the first run: set `MODEL_URL` and `MODEL_SHA256` (and `AZURE_VISION_KEY`) in `server/.env.example`, or edit `/home/ubuntu/waste_ai/server/.env` afterwards and re-run.

Steps done (each is skipped when already satisfied):
1. Install missing apt packages only.
2. Sync `server/`, `frontend/`, `content/`, `contract/` to `/home/ubuntu/waste_ai/` (`.env` and the SQLite DB are kept).
3. Create the venv; `pip install` only when `requirements.txt` changed.
4. Create `.env` (mode 600); download and verify the model (SHA256).
5. Install `wasteai.service` (127.0.0.1:8100, `MemoryHigh=350M`, `MemoryMax=450M`) and restart only that service. uvicorn runs with `--proxy-headers --forwarded-allow-ips 127.0.0.1` so the app limiter sees the client address.
6. Install the Nginx block `wasteai` and the shared header snippet `/etc/nginx/snippets/wasteai-headers.conf` (included in every location); `nginx -t && systemctl reload nginx` only. If `nginx -t` fails, the previous config is restored.
7. Certbot certificate for the domain.
8. Render the Nginx block again: with the certificate present it writes the 443 part (Certbot files) and the port 80 redirect itself, so later runs keep the hardening. Then health check.

A second run changes nothing.

## Flags
| Flag | Effect |
|---|---|
| `--status` | service, nginx, RAM, local health, state file |
| `--rollback` | disable and remove the unit, the Nginx block and the header snippet, reload Nginx; keeps app dir, `.env`, data, certificates |
| `--fix-owner` | `chown` repo and app dir to `ubuntu`, prints the count of foreign entries (must be 0) |
| `--stop-containers` | after typing `STOP`, runs `docker compose stop` for the AFPL stack. Never prune |

Run `bash deploy/install.sh --fix-owner` after any `sudo` file edit in the project.

## Edge hardening (A11)
- Every location sends the same headers: `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and a CSP with `script-src 'self'`, `style-src 'self'`, `base-uri 'none'`, `form-action 'self'`, `frame-ancestors 'none'`.
- Bodies over 3 MB get the contract JSON `image_too_large` (HTTP 413), in Arabic when `?lang=ar`.
- `/api/v1/classify`: 10 requests per minute per address, `burst=3 nodelay`; extra requests get HTTP 429, `Retry-After: 6` and the contract JSON `rate_limited`. The app limiter stays as second line.
- Checks: `curl -sI https://<DOMAIN>/assets/icons.svg | grep -i "content-security-policy\|x-content-type"`; `head -c 3500000 /dev/zero > /tmp/big.jpg; curl -s -F image=@/tmp/big.jpg https://<DOMAIN>/api/v1/classify`; 12 quick `curl` calls to `/api/v1/classify` end with 429.

## State
`/var/lib/wasteai/state.txt` (root, mode 600): domain, requirements hash, install timestamps, RAM before/after.

## Safety rules
- Nginx, Docker and the other services are never restarted; the existing Nginx server blocks are not edited.
- Secrets live only in `.env`. Images are never stored.

## Troubleshooting
- `journalctl -u wasteai -n 50`
- `curl http://127.0.0.1:8100/api/v1/health`
- Static files 403: `sudo setfacl -m u:www-data:x /home/ubuntu`
- Camera needs HTTPS: check the certificate step ran (`--email` given).
