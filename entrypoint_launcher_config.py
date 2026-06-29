"""Composition helpers for the entrypoint launcher module."""

from __future__ import annotations

from typing import Any, Callable

from entrypoint_module import EntrypointModuleDeps
from entrypoint_launcher_runtime import LazyEntrypointLauncher
from entrypoint_module import build_entrypoint_module


def build_entrypoint_launcher(
    *,
    module_path: str,
    logger_name: str,
    load_last_collection: Callable[[str], str | None],
    save_last_collection: Callable[[str, str], None],
    atomic_json_write: Callable[[str, Any, Any], None],
    command_prefix: Callable[[Any, Any], Any],
    deps: EntrypointModuleDeps,
    flip_order: list[str],
    flip_seq: list[str],
) -> LazyEntrypointLauncher:
    module_builder = build_entrypoint_module

    def module_factory():
        return module_builder(
            module_path=module_path,
            logger_name=logger_name,
            load_last_collection=load_last_collection,
            save_last_collection=save_last_collection,
            atomic_json_write=atomic_json_write,
            command_prefix=command_prefix,
            deps=deps,
        )

    launcher = LazyEntrypointLauncher.create(
        module_factory=module_factory,
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    return launcher
