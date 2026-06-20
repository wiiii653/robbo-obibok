#!/usr/bin/env bash
# Wrapper to load .env and start the bot
cd "$(dirname "$0")"
set -a
source .env
set +a
exec ./venv/bin/python3 -u robbo-obibok.py
