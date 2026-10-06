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
5. Install `wasteai.service` (127.0.0.1:8100, `MemoryHigh=350M`, `MemoryMax=450M`) and restart only that service.
6. Install the Nginx block `wasteai`; `nginx -t && systemctl reload nginx` only.
7. Certbot certificate for the domain; health check.

A second run changes nothing.

## Flags
| Flag | Effect |
|---|---|
| `--status` | service, nginx, RAM, local health, state file |
| `--rollback` | disable and remove the unit and the Nginx block, reload Nginx; keeps app dir, `.env`, data, certificates |
| `--fix-owner` | `chown` repo and app dir to `ubuntu`, prints the count of foreign entries (must be 0) |
| `--stop-containers` | after typing `STOP`, runs `docker compose stop` for the AFPL stack. Never prune |

Run `bash deploy/install.sh --fix-owner` after any `sudo` file edit in the project.

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
