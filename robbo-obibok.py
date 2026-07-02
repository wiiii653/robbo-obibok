"""Compatibility launcher facade for the robbo-obibok runtime module."""

from __future__ import annotations

import importlib
import os
import sys

# Source-checkout compatibility; installed entry points do not need this.
_src = os.path.join(os.path.dirname(__file__), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

_runtime = importlib.import_module("robbo_obibok.robbo_obibok_runtime")

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
