#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x "venv/bin/python3" ]; then
    echo "venv/bin/python3 is missing. Create the virtualenv first."
    exit 1
fi

exec ./venv/bin/python3 -m unittest -v \
    tests.test_robbo_obibok_launch \
    tests.test_robbo_obibok_logged_launcher \
    tests.test_runner_smoke \
    tests.test_install_assets
