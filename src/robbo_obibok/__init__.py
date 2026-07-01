"""
robbo_obibok — Discord chiptune radio bot.

All public modules are available directly under the ``robbo_obibok`` namespace:
``from robbo_obibok import bot_runtime``, ``from robbo_obibok.playback_commands import ...``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add this package directory to sys.path so flat imports
# (e.g. ``import bot_runtime``) work both in development
# (PYTHONPATH=src/robbo_obibok) and after pip install.
_pkg_dir = str(Path(__file__).resolve().parent)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

__all__: list[str] = []
