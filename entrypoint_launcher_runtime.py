"""Launcher composition for lazy entrypoint loading and runtime access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from entrypoint_launcher_loader import EntrypointModuleLoader
from entrypoint_launcher_state import EntrypointRuntimeController

if TYPE_CHECKING:
    from entrypoint_module import EntrypointModule


@dataclass(slots=True)
class LazyEntrypointLauncher:
    loader: EntrypointModuleLoader
    runtime: EntrypointRuntimeController

    @classmethod
    def create(
        cls,
        *,
        module_factory: Callable[[], EntrypointModule],
        flip_order: list[str],
        flip_seq: list[str],
    ) -> "LazyEntrypointLauncher":
        loader = EntrypointModuleLoader(
            module_factory=module_factory,
            flip_order=flip_order,
            flip_seq=flip_seq,
        )
        return cls(
            loader=loader,
            runtime=EntrypointRuntimeController(loader=loader),
        )
