"""Executable module binding helpers for the entrypoint script."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from entrypoint_compat_contract import ENTRYPOINT_COMPAT_RUNTIME_BINDINGS
from entrypoint_direct_export_contract import (
    ENTRYPOINT_DIRECT_EXPORT_BINDINGS,
    ENTRYPOINT_PRIVATE_DIRECT_EXPORT_BINDINGS,
    ENTRYPOINT_PUBLIC_DIRECT_EXPORT_BINDINGS,
)


@dataclass(frozen=True, slots=True)
class EntrypointBindingSpec:
    export_name: str
    copy_value: bool = False


@dataclass(frozen=True, slots=True)
class EntrypointSurfaceAliasSpec:
    alias_name: str
    binding_name: str


@dataclass(frozen=True, slots=True)
class EntrypointExportGraph:
    stable_binding_names: frozenset[str]
    legacy_compat_binding_names: frozenset[str]
    direct_names: frozenset[str]
    compat_names: frozenset[str]

    def bound_names(self) -> frozenset[str]:
        return self.stable_binding_names | self.direct_names

    def public_bound_names(self) -> frozenset[str]:
        return self.stable_binding_names | ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES

    def dynamic_names(self) -> frozenset[str]:
        return self.public_bound_names()

    def supported_names(self, *, dict_attr_names: frozenset[str]) -> frozenset[str]:
        return dict_attr_names | self.public_bound_names() | self.compat_names


ENTRYPOINT_MODULE_STABLE_BINDINGS = (
    EntrypointBindingSpec("bot"),
    EntrypointBindingSpec("single_guild_check"),
    EntrypointBindingSpec("get_guild_id_override"),
    EntrypointBindingSpec("set_guild_id_override"),
)

ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS = (
    EntrypointBindingSpec("_STATE"),
    EntrypointBindingSpec("_app_cfg"),
    EntrypointBindingSpec("_archive_runtime_config"),
    EntrypointBindingSpec("_FLIP_ORDER", copy_value=True),
    EntrypointBindingSpec("_FLIP_SEQ", copy_value=True),
)

ENTRYPOINT_MODULE_STABLE_NAMES = frozenset(spec.export_name for spec in ENTRYPOINT_MODULE_STABLE_BINDINGS)
ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES = frozenset(
    spec.export_name for spec in ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS
)

ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS = (
    EntrypointSurfaceAliasSpec("state", "_STATE"),
    EntrypointSurfaceAliasSpec("app_config", "_app_cfg"),
    EntrypointSurfaceAliasSpec("archive_runtime_config", "_archive_runtime_config"),
    EntrypointSurfaceAliasSpec("flip_order", "_FLIP_ORDER"),
    EntrypointSurfaceAliasSpec("flip_seq", "_FLIP_SEQ"),
)

ENTRYPOINT_EXPORT_GRAPH = EntrypointExportGraph(
    stable_binding_names=ENTRYPOINT_MODULE_STABLE_NAMES,
    legacy_compat_binding_names=ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES,
    direct_names=frozenset(spec.export_name for spec in ENTRYPOINT_DIRECT_EXPORT_BINDINGS),
    compat_names=frozenset(spec.export_name for spec in ENTRYPOINT_COMPAT_RUNTIME_BINDINGS),
)

ENTRYPOINT_EXECUTABLE_HELPER_ATTR_NAMES = frozenset(
    {
        "BOT_TOKEN",
        "initialize_runtime",
        "graceful_shutdown",
        "handle_signal",
        "main",
        "__getattr__",
        "_BINDINGS",
        "_COMPAT_BINDINGS",
    }
)

ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_ATTR_NAMES = frozenset(
    spec.alias_name for spec in ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS
)

ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES = frozenset(
    {
        "_FLIP_ORDER",
        "_FLIP_SEQ",
    }
)

ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES = frozenset(
    {
        "_STATE",
        "_app_cfg",
        "_archive_runtime_config",
    }
)

ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES = frozenset(
    ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES
)

ENTRYPOINT_EXECUTABLE_STABLE_INTERNAL_ATTR_NAMES = frozenset(
    {
        "_ASSEMBLY",
    }
)

ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES = frozenset(
    {
        "_LAUNCHER",
        "_LEGACY_RESOLVE",
        "_SURFACE",
        "_MODULE_DEPS",
    }
)

ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES = frozenset(
    spec.export_name for spec in ENTRYPOINT_PUBLIC_DIRECT_EXPORT_BINDINGS
)

ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES = (
    ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES | ENTRYPOINT_EXPORT_GRAPH.compat_names
)

ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES = ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES

ENTRYPOINT_EXECUTABLE_PRIVATE_DIRECT_ATTR_NAMES = (
    frozenset(spec.export_name for spec in ENTRYPOINT_PRIVATE_DIRECT_EXPORT_BINDINGS)
)

ENTRYPOINT_EXECUTABLE_PRIVATE_ATTR_NAMES = frozenset(
    {
        "_RUNTIME_HOLDER",
        "_build_executable_assembly",
        "_ensure_executable_assembly",
        "_command_prefix",
        "COLLECTION_FLIP_ORDER",
        "COLLECTION_FLIP_SEQ",
    }
)

ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES = (
    ENTRYPOINT_MODULE_STABLE_NAMES
    | ENTRYPOINT_EXECUTABLE_HELPER_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_STABLE_INTERNAL_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_ATTR_NAMES
)

ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES = (
    ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES
)

ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES = (
    ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES
)

ENTRYPOINT_EXECUTABLE_DICT_ATTR_NAMES = (
    ENTRYPOINT_EXECUTABLE_HELPER_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_STABLE_INTERNAL_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES
    | ENTRYPOINT_EXECUTABLE_PRIVATE_ATTR_NAMES
)

ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES = (
    ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES | ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES
)


class EntrypointModuleBindingSurface(Protocol):
    def export_map(self) -> Mapping[str, object]: ...

    def resolve(self, name: str) -> object: ...


class EntrypointCompatBindingSource(Protocol):
    def get(self, key: str, default: object = None) -> object: ...


def build_entrypoint_stable_module_bindings(surface: EntrypointModuleBindingSurface) -> dict[str, object]:
    exports = surface.export_map()
    bindings = {
        spec.export_name: _resolve_binding_value(surface, exports, spec)
        for spec in ENTRYPOINT_MODULE_STABLE_BINDINGS
    }
    bindings.update({name: exports[name] for name in ENTRYPOINT_EXPORT_GRAPH.direct_names})
    return bindings


def build_entrypoint_compat_module_bindings(
    source: EntrypointCompatBindingSource | EntrypointModuleBindingSurface,
    *,
    resolver: Callable[[str], object] | None = None,
) -> dict[str, object]:
    exports = _compat_binding_source_map(source)
    resolve = _compat_binding_resolver(source, resolver=resolver)
    return {
        spec.export_name: _resolve_compat_binding_value(resolve, exports, spec)
        for spec in ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS
    }


def resolve_compat_binding_attr(
    name: str,
    *,
    compat_bindings: Mapping[str, object],
) -> object:
    if name in ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES and name in compat_bindings:
        return compat_bindings[name]
    raise AttributeError(name)


def resolve_bound_entrypoint_module_attr(
    name: str,
    *,
    bindings: dict[str, object],
) -> object:
    if name in (ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES | ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES) and name in bindings:
        return bindings[name]
    raise AttributeError(name)


def resolve_compat_entrypoint_module_attr(
    name: str,
    *,
    fallback_resolver: Callable[[str], object],
) -> object:
    if name not in (
        ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES
        | ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES
    ):
        raise AttributeError(name)
    return fallback_resolver(name)


def is_supported_executable_attr(name: str) -> bool:
    return name in ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES


def is_stable_executable_attr(name: str) -> bool:
    return name in ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES


def is_deprecated_executable_attr(name: str) -> bool:
    return name in ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES


def supported_executable_dict_attrs(namespace: dict[str, object]) -> set[str]:
    return {name for name in namespace if name in ENTRYPOINT_EXECUTABLE_DICT_ATTR_NAMES}


def _resolve_binding_value(
    surface: EntrypointModuleBindingSurface,
    exports: Mapping[str, object],
    spec: EntrypointBindingSpec,
) -> object:
    value = exports.get(spec.export_name)
    if value is None:
        value = surface.resolve(spec.export_name)
    if spec.copy_value:
        return list(value)
    return value


def _resolve_compat_binding_value(
    resolver: Callable[[str], object],
    exports: EntrypointCompatBindingSource,
    spec: EntrypointBindingSpec,
) -> object:
    value = _compat_source_get(exports, spec.export_name)
    if value is None:
        value = resolver(spec.export_name)
    if spec.copy_value:
        return list(value)
    return value


def _compat_binding_source_map(
    source: EntrypointCompatBindingSource | EntrypointModuleBindingSurface,
) -> EntrypointCompatBindingSource:
    export_map = getattr(source, "export_map", None)
    if callable(export_map):
        return export_map()
    return source


def _compat_binding_resolver(
    source: EntrypointCompatBindingSource | EntrypointModuleBindingSurface,
    *,
    resolver: Callable[[str], object] | None,
) -> Callable[[str], object]:
    if resolver is not None:
        return resolver
    return source.resolve


def _compat_source_get(
    source: EntrypointCompatBindingSource,
    name: str,
) -> object:
    getter = getattr(source, "get", None)
    if callable(getter):
        return getter(name)
    return None
