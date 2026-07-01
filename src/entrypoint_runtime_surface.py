"""Typed runtime-surface helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, cast

from domain_config import AppConfig
from archive_runtime import ArchiveRuntimeConfig
import entrypoint_state as state_protocols

from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS,
    ENTRYPOINT_MODULE_STABLE_BINDINGS,
)


@dataclass(frozen=True, slots=True)
class EntrypointStableBindingSpec:
    binding_name: str
    method_name: str


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


@dataclass(frozen=True, slots=True)
class EntrypointRuntimeSurface:
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

    def state(self) -> state_protocols.EntrypointRuntimeStateProtocol:
        return cast(state_protocols.EntrypointRuntimeStateProtocol, self.bindings["_STATE"])

    def app_config(self) -> AppConfig:
        factory = cast(Callable[[], AppConfig], self.bindings["_app_cfg"])
        return factory()

    def archive_runtime_config(self) -> ArchiveRuntimeConfig:
        factory = cast(Callable[[], ArchiveRuntimeConfig], self.bindings["_archive_runtime_config"])
        return factory()


def build_runtime_surface_bindings(
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


def build_runtime_surface(
    source: object,
    *,
    resolver: Callable[[str], object] | None = None,
    binding_names: set[str] | None = None,
    alias_source: object | None = None,
    alias_resolver: Callable[[str], object] | None = None,
) -> "EntrypointRuntimeSurface":
    if alias_source is None:
        alias_source = source
    if alias_resolver is None:
        if resolver is not None and alias_source is source:
            alias_resolver = resolver
        elif isinstance(alias_source, Mapping):
            alias_resolver = alias_source.__getitem__
        else:
            alias_resolver = lambda name: getattr(alias_source, name)
    return EntrypointRuntimeSurface(
        bindings=build_runtime_surface_bindings(
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


def _build_surface_method(
    spec: EntrypointStableBindingSpec,
) -> Callable[[EntrypointRuntimeSurface], object]:
    def _method(self: EntrypointRuntimeSurface) -> object:
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
    setattr(EntrypointRuntimeSurface, _spec.method_name, _build_surface_method(_spec))
