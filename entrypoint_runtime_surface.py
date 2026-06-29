"""Typed stable runtime-surface helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Mapping, Protocol

from app_config import AppConfig
from archive_runtime import ArchiveRuntimeConfig

if TYPE_CHECKING:
    import asyncio

    from bot_runtime import BotRuntime
    from entrypoint_runtime import AppAssembly
    from runtime_registration import RuntimeRegistration
    from runtime_composition import ComposedRuntime


class EntrypointRuntimeStateProtocol(Protocol):
    app: "AppAssembly | None"
    startup_env: object | None
    runtime_registration: "RuntimeRegistration | None"
    composed_runtime: "ComposedRuntime | None"
    runtime: "BotRuntime | None"
    collection_service: object | None
    playback_service: object | None
    lock_file: str | None
    shutdown_flag: "asyncio.Event | None"

    def cache_initialized_app(self, app: "AppAssembly") -> "AppAssembly": ...


class EntrypointBootstrapStateProtocol(Protocol):
    archives: object | None
    service_facade: object | None

    def runtime_metadata_index(self) -> dict[str, dict[str, str]]: ...

    def runtime_modarchive_name_map(self) -> Mapping[str, str]: ...

    def runtime_snes_metadata(self) -> Mapping[str, dict[str, object]]: ...


class EntrypointRuntimeInitializerStateProtocol(
    EntrypointRuntimeStateProtocol,
    EntrypointBootstrapStateProtocol,
    Protocol,
):
    pass

from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS,
    ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS,
    ENTRYPOINT_MODULE_STABLE_BINDINGS,
)


@dataclass(frozen=True, slots=True)
class EntrypointStableBindingSpec:
    binding_name: str
    method_name: str


@dataclass(frozen=True, slots=True)
class EntrypointCompatBindingSpec:
    binding_name: str


ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS = tuple(
    EntrypointStableBindingSpec(
        spec.export_name,
        spec.export_name,
    )
    for spec in ENTRYPOINT_MODULE_STABLE_BINDINGS
)
ENTRYPOINT_STABLE_RUNTIME_SURFACE_ALIAS_BINDINGS = tuple(
    EntrypointStableBindingSpec(
        spec.binding_name,
        spec.alias_name,
    )
    for spec in ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS
)
ENTRYPOINT_COMPAT_RUNTIME_SURFACE_BINDINGS = tuple(
    EntrypointCompatBindingSpec(spec.export_name)
    for spec in ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS
)

ENTRYPOINT_STABLE_RUNTIME_SURFACE_SPECS_BY_BINDING = {
    spec.binding_name: spec for spec in ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS
}
ENTRYPOINT_STABLE_RUNTIME_SURFACE_SPECS_BY_METHOD = {
    spec.method_name: spec
    for spec in (ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS + ENTRYPOINT_STABLE_RUNTIME_SURFACE_ALIAS_BINDINGS)
}
ENTRYPOINT_RUNTIME_STATE_BINDING_NAMES = frozenset(
    {
        "_STATE",
        "_app_cfg",
        "_archive_runtime_config",
    }
)
ENTRYPOINT_COMPAT_RUNTIME_SURFACE_NAMES = frozenset(
    spec.binding_name for spec in ENTRYPOINT_COMPAT_RUNTIME_SURFACE_BINDINGS
)


@dataclass(frozen=True, slots=True)
class EntrypointStableRuntimeSurface:
    bindings: Mapping[str, object]
    alias_bindings: Mapping[str, object] | None = None

    def resolve(self, name: str) -> object:
        try:
            spec = ENTRYPOINT_STABLE_RUNTIME_SURFACE_SPECS_BY_BINDING[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        return getattr(self, spec.method_name)()

    def resolve_alias(self, name: str) -> object:
        try:
            spec = ENTRYPOINT_STABLE_RUNTIME_SURFACE_SPECS_BY_METHOD[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        if self.alias_bindings is not None and spec.binding_name in self.alias_bindings:
            return self.alias_bindings[spec.binding_name]
        return getattr(self, spec.method_name)()


@dataclass(frozen=True, slots=True)
class EntrypointRuntimeStateSurface:
    bindings: Mapping[str, object]

    def state(self) -> EntrypointRuntimeStateProtocol:
        return self.bindings["_STATE"]

    def app_config(self) -> AppConfig:
        return self.bindings["_app_cfg"]()

    def archive_runtime_config(self) -> ArchiveRuntimeConfig:
        return self.bindings["_archive_runtime_config"]()


@dataclass(frozen=True, slots=True)
class EntrypointCompatRuntimeSurface:
    bindings: Mapping[str, object]

    def resolve(self, name: str) -> object:
        if name not in ENTRYPOINT_COMPAT_RUNTIME_SURFACE_NAMES:
            raise AttributeError(name)
        return self.bindings[name]


def build_stable_runtime_surface_bindings(
    source: object,
    *,
    resolver: Callable[[str], object] | None = None,
    binding_names: set[str] | None = None,
) -> dict[str, object]:
    if resolver is None:
        if isinstance(source, Mapping):
            resolver = source.__getitem__
        else:
            resolver = lambda name: getattr(source, name)
    selected_specs = ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS
    if binding_names is not None:
        selected_specs = tuple(
            spec for spec in ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS if spec.binding_name in binding_names
        )
    return {
        spec.binding_name: resolver(spec.binding_name)
        for spec in selected_specs
    }


def build_stable_runtime_surface(
    source: object,
    *,
    resolver: Callable[[str], object] | None = None,
    binding_names: set[str] | None = None,
    alias_source: object | None = None,
    alias_resolver: Callable[[str], object] | None = None,
) -> "EntrypointStableRuntimeSurface":
    if alias_source is None:
        alias_source = source
    if alias_resolver is None:
        if resolver is not None and alias_source is source:
            alias_resolver = resolver
        elif isinstance(alias_source, Mapping):
            alias_resolver = alias_source.__getitem__
        else:
            alias_resolver = lambda name: getattr(alias_source, name)
    return EntrypointStableRuntimeSurface(
        bindings=build_stable_runtime_surface_bindings(
            source,
            resolver=resolver,
            binding_names=binding_names,
        ),
        alias_bindings=_build_alias_bindings(alias_resolver),
    )


def build_runtime_state_surface(
    source: object,
    *,
    resolver: Callable[[str], object] | None = None,
) -> EntrypointRuntimeStateSurface:
    if resolver is None:
        if isinstance(source, Mapping):
            resolver = source.__getitem__
        else:
            resolver = lambda name: getattr(source, name)
    return EntrypointRuntimeStateSurface(
        bindings={name: resolver(name) for name in ENTRYPOINT_RUNTIME_STATE_BINDING_NAMES}
    )


def build_compat_runtime_surface(
    source: object,
    *,
    resolver: Callable[[str], object] | None = None,
) -> EntrypointCompatRuntimeSurface:
    if resolver is None:
        if isinstance(source, Mapping):
            resolver = source.__getitem__
        else:
            resolver = lambda name: getattr(source, name)
    return EntrypointCompatRuntimeSurface(
        bindings={name: resolver(name) for name in ENTRYPOINT_COMPAT_RUNTIME_SURFACE_NAMES}
    )


def _build_surface_method(spec: EntrypointStableBindingSpec):
    def _method(self: EntrypointStableRuntimeSurface) -> object:
        if self.alias_bindings is not None and spec.binding_name in self.alias_bindings:
            return self.alias_bindings[spec.binding_name]
        return self.bindings[spec.binding_name]

    return _method


def _build_alias_bindings(alias_resolver: Callable[[str], object]) -> dict[str, object]:
    alias_bindings: dict[str, object] = {}
    for spec in ENTRYPOINT_STABLE_RUNTIME_SURFACE_ALIAS_BINDINGS:
        try:
            alias_bindings[spec.binding_name] = alias_resolver(spec.binding_name)
        except (AttributeError, KeyError):
            continue
    return alias_bindings


for _spec in (ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS + ENTRYPOINT_STABLE_RUNTIME_SURFACE_ALIAS_BINDINGS):
    setattr(EntrypointStableRuntimeSurface, _spec.method_name, _build_surface_method(_spec))
