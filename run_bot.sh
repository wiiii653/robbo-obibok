#!/usr/bin/env bash
# Wrapper to start the shared Python launcher
set -euo pipefail

cd "$(dirname "$0")"

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PWD/src"
exec ./venv/bin/python3 -u -m robbo_obibok.robbo_obibok_launcher
