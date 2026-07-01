"""Strict-compatibility launcher facade for the robbo-obibok runtime module."""

from __future__ import annotations

import sys
import os

# Add src/robbo_obibok/ to sys.path so flat imports work from the package
_src = os.path.join(os.path.dirname(__file__), "src", "robbo_obibok")
if _src not in sys.path:
    sys.path.insert(0, _src)

from robbo_obibok_runtime import run_runtime_entrypoint


def main() -> None:
    run_runtime_entrypoint()


if __name__ == "__main__":
    main()
