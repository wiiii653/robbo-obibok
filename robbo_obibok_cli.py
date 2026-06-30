"""Shared CLI bootstrap helpers for robbo-obibok entrypoints."""

from __future__ import annotations


def run_runtime_entrypoint() -> None:
    from robbo_obibok_runtime import main

    main()
