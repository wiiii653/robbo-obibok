"""Compatibility launcher facade for the robbo-obibok runtime module."""

from __future__ import annotations

import sys
import os

# Add src/robbo_obibok/ to sys.path so flat imports work from the package
_src = os.path.join(os.path.dirname(__file__), "src", "robbo_obibok")
if _src not in sys.path:
    sys.path.insert(0, _src)

import robbo_obibok_runtime as _runtime

initialize_runtime = _runtime.initialize_runtime
graceful_shutdown = _runtime.graceful_shutdown
handle_signal = _runtime.handle_signal
main = _runtime.main
main_strict = _runtime.main_strict
selected_main = _runtime.selected_main


def __getattr__(name: str):
    return getattr(_runtime, name)


if __name__ == "__main__":
    selected_main()()
