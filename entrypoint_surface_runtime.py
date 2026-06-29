"""Runtime-facing helpers for executable entrypoint surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from entrypoint_module_bindings import ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES


@dataclass(slots=True)
class EntrypointModuleSurface:
    exports: Mapping[str, object]
    resolve_fallback: Callable[[str], object]
    allowed_fallback_names: frozenset[str] = ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES

    def export_map(self) -> Mapping[str, object]:
        return self.exports

    def resolve(self, name: str) -> object:
        direct = self.exports.get(name)
        if direct is not None:
            return direct
        if name not in self.allowed_fallback_names:
            raise AttributeError(name)
        return self.resolve_fallback(name)
