#!/usr/bin/env bash
# Wrapper to start the shared Python launcher
set -euo pipefail

cd "$(dirname "$0")"

exec ./venv/bin/python3 -u robbo_obibok_launcher.py
