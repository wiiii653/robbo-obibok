#!/usr/bin/env bash
cd ~/robbo-obibot || exit 1
source venv/bin/activate
export DISCORD_BOT_TOKEN="MTUx..."
exec python3 -u asma-bot.py > /tmp/robbo.log 2>&1
