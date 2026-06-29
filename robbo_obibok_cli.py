"""Shared CLI bootstrap helpers for robbo-obibok entrypoints."""

from __future__ import annotations


def run_runtime_entrypoint(*, strict: bool = False) -> None:
    from robbo_obibok_runtime import main_strict, selected_main

    if strict:
        main_strict()
        return
    selected_main()()
