"""Central policy constructors for executable compatibility behavior."""

from __future__ import annotations

from dataclasses import dataclass, replace

from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES,
)


@dataclass(slots=True)
class EntrypointCompatPolicy:
    allow_deprecated_runtime_internal_attrs: bool = True

    def allows_deprecated_runtime_internal_attr(self, name: str) -> bool:
        if name not in ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES:
            return False
        return self.allow_deprecated_runtime_internal_attrs

def build_compat_policy(*, template: EntrypointCompatPolicy | None = None) -> EntrypointCompatPolicy:
    if template is None:
        return EntrypointCompatPolicy()
    return replace(template)


def build_strict_compat_policy() -> EntrypointCompatPolicy:
    return EntrypointCompatPolicy(
        allow_deprecated_runtime_internal_attrs=False,
    )
