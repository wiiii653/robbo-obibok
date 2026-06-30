#!/usr/bin/env python3
"""CLI entry for the robbo-obibok bot."""

from __future__ import annotations


def main() -> None:
    from robbo_obibok_runtime import run_runtime_entrypoint

    run_runtime_entrypoint()


if __name__ == "__main__":
    main()
