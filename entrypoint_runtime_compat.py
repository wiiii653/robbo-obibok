"""Compatibility helpers for legacy runtime-module attribute access."""

from __future__ import annotations

from typing import Callable

from entrypoint_compat_policy import EntrypointCompatPolicy
from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES,
)

RUNTIME_INTERNAL_ATTR_NAMES = frozenset(
    {
        "_ASSEMBLY",
        "_BINDINGS",
        "_COMPAT_BINDINGS",
    }
    | ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES
)


def resolve_runtime_internal_attr(
    name: str,
    *,
    assembly_peek: Callable[[], object],
    bindings_getter: Callable[[], object],
    compat_bindings_getter: Callable[[], object],
    compat_policy_getter: Callable[[], EntrypointCompatPolicy],
    launcher_getter: Callable[[], object],
    deps_getter: Callable[[], object],
    legacy_resolve_getter: Callable[[], object],
    surface_getter: Callable[[], object],
) -> object:
    stable_getters = {
        "_ASSEMBLY": assembly_peek,
        "_BINDINGS": bindings_getter,
        "_COMPAT_BINDINGS": compat_bindings_getter,
    }
    if name in stable_getters:
        return stable_getters[name]()

    deprecated_getters = {
        "_LAUNCHER": launcher_getter,
        "_MODULE_DEPS": deps_getter,
        "_LEGACY_RESOLVE": legacy_resolve_getter,
        "_SURFACE": surface_getter,
    }
    getter = deprecated_getters.get(name)
    if getter is None:
        raise AttributeError(name)
    if not compat_policy_getter().allows_deprecated_runtime_internal_attr(name):
        raise AttributeError(name)
    _warn_deprecated_internal_attr(name)
    return getter()


def is_runtime_internal_attr(name: str) -> bool:
    return name in RUNTIME_INTERNAL_ATTR_NAMES


def _warn_deprecated_internal_attr(name: str) -> None:
    import warnings

    assert name in ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES
    warnings.warn(
        f"{name} is a deprecated runtime compatibility attribute and will be removed in a future refactor",
        DeprecationWarning,
        stacklevel=3,
    )
