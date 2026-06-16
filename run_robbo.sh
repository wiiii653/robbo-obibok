#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")" || exit 1
source venv/bin/activate
exec python3 -u asma-bot.py 2>&1 | tee /tmp/robbo.log
