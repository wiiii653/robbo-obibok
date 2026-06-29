"""Central policy constructors for executable compatibility behavior."""

from __future__ import annotations

from dataclasses import dataclass, replace

from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES,
)


@dataclass(slots=True)
class EntrypointCompatPolicy:
    allow_deprecated_runtime_internal_attrs: bool = True
    allow_legacy_runtime_compat_attrs: bool = True
    allow_legacy_flip_runtime_compat_attrs: bool = False

    def allows_deprecated_runtime_internal_attr(self, name: str) -> bool:
        if name not in ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES:
            return False
        return self.allow_deprecated_runtime_internal_attrs

    def allows_legacy_runtime_compat_attr(self, name: str) -> bool:
        if name not in ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES:
            return False
        if name in ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES:
            return (
                self.allow_legacy_runtime_compat_attrs
                and self.allow_legacy_flip_runtime_compat_attrs
            )
        return self.allow_legacy_runtime_compat_attrs

def build_compat_policy(*, template: EntrypointCompatPolicy | None = None) -> EntrypointCompatPolicy:
    if template is None:
        return EntrypointCompatPolicy()
    return replace(template)


def build_strict_compat_policy() -> EntrypointCompatPolicy:
    return EntrypointCompatPolicy(
        allow_deprecated_runtime_internal_attrs=False,
        allow_legacy_runtime_compat_attrs=False,
        allow_legacy_flip_runtime_compat_attrs=False,
    )
