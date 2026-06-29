"""Compatibility launcher facade for the robbo-obibok runtime module."""

from __future__ import annotations

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
