"""Shared registry helpers for legacy entrypoint exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class EntrypointExportRegistry:
    eager_attrs: dict[str, Callable[[], object]] = field(default_factory=dict)
    lazy_attrs: dict[str, Callable[[], object]] = field(default_factory=dict)

    def register_eager(self, **attrs: Callable[[], object]) -> "EntrypointExportRegistry":
        self.eager_attrs.update(attrs)
        return self

    def register_lazy(self, **attrs: Callable[[], object]) -> "EntrypointExportRegistry":
        self.lazy_attrs.update(attrs)
        return self

    def resolve(self, name: str, ensure_components: Callable[[], None]) -> object:
        eager = self.eager_attrs.get(name)
        if eager is not None:
            return eager()
        lazy = self.lazy_attrs.get(name)
        if lazy is None:
            raise AttributeError(name)
        ensure_components()
        return lazy()

    def module_exports(self) -> dict[str, object]:
        return {name: resolver() for name, resolver in self.eager_attrs.items()}
