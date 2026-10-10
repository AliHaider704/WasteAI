#!/usr/bin/env bash
# File: scripts/make_audio_run.sh
# One command for the whole audio build: throw-away venv, voices, clips, cleanup. Use: bash scripts/make_audio_run.sh [--only <category_id>]
set -euo pipefail
cd "$(dirname "$0")/.."
avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
[ "$avail" -ge 300 ] || { echo "MemAvailable ${avail} MB is under 300 MB: stop"; exit 1; }
trap 'rm -rf /tmp/piper /tmp/voices' EXIT
python3 -m venv /tmp/piper
/tmp/piper/bin/pip install --quiet piper-tts
mkdir -p /tmp/voices
/tmp/piper/bin/python -m piper.download_voices --data-dir /tmp/voices ar_JO-kareem-medium en_US-lessac-medium
/tmp/piper/bin/python scripts/make_audio.py --voices /tmp/voices "$@"
du -sh frontend/audio
echo "AUDIO BUILD FINISHED"
