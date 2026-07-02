"""Strict-compatibility launcher facade for the robbo-obibok runtime module."""

from __future__ import annotations

import importlib
import os
import sys

# Source-checkout compatibility; installed entry points do not need this.
_src = os.path.join(os.path.dirname(__file__), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

main_strict = importlib.import_module("robbo_obibok.robbo_obibok_runtime").main_strict


def main() -> None:
    main_strict()


if __name__ == "__main__":
    main()
