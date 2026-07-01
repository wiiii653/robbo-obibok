"""Assembly helpers for executable entrypoint surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, Mapping, Protocol

from entrypoint_module_bindings import (
    ENTRYPOINT_COMPAT_RUNTIME_BINDINGS,
    ENTRYPOINT_DIRECT_EXPORT_BINDINGS,
    ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES,
    ENTRYPOINT_MODULE_STABLE_NAMES,
    EntrypointDirectExportSpec,
    SurfaceExportResolver,
)
from entrypoint_runtime_surface import build_runtime_surface_bindings


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


if TYPE_CHECKING:
    from entrypoint_launcher_loader import LazyEntrypointLauncher
    from entrypoint_state import EntrypointCompatStateProtocol


class LazyCallableExport:
    def __init__(self, resolver: Callable[[], Callable[..., object]]):
        self._resolver = resolver

    def _target(self) -> Callable[..., object]:
        return self._resolver()

    def __call__(self, *args, **kwargs):
        return self._target()(*args, **kwargs)


class EntrypointSurfaceLoaderProtocol(Protocol):
    def resolve_legacy(self, name: str) -> object: ...

    def collection_export(self, spec: str | EntrypointDirectExportSpec) -> Callable[..., object]: ...

    def runtime_export(self, spec: str | EntrypointDirectExportSpec) -> Callable[..., object]: ...


def build_entrypoint_compat_registry_attrs(
    *,
    state: EntrypointCompatStateProtocol,
    guild_id_getter: Callable[[], int | None],
) -> dict[str, Callable[[], object]]:
    def state_attr_getter(attr: str) -> Callable[[], object]:
        return lambda: getattr(state, attr)

    registry_attrs: dict[str, Callable[[], object]] = {}
    for spec in ENTRYPOINT_COMPAT_RUNTIME_BINDINGS:
        if spec.export_name == "GUILD_ID":
            registry_attrs[spec.export_name] = guild_id_getter
            continue
        assert spec.state_attr is not None
        registry_attrs[spec.export_name] = state_attr_getter(spec.state_attr)
    return registry_attrs


def build_entrypoint_direct_export_map(
    *,
    resolve_collection: Callable[[EntrypointDirectExportSpec], Callable[..., object]],
    resolve_runtime: Callable[[EntrypointDirectExportSpec], Callable[..., object]],
) -> dict[str, object]:
    exports: dict[str, object] = {}
    for spec in ENTRYPOINT_DIRECT_EXPORT_BINDINGS:
        if spec.source_name == "collection":
            exports[spec.export_name] = resolve_collection(spec)
            continue
        exports[spec.export_name] = resolve_runtime(spec)
    return exports


@dataclass(frozen=True, slots=True)
class EntrypointSurfaceExportAdapter:
    loader: EntrypointSurfaceLoaderProtocol

    def resolve_legacy(self, name: str) -> object:
        return self.loader.resolve_legacy(name)

    def resolve_collection(self, spec: EntrypointDirectExportSpec) -> Callable[..., object]:
        return self.loader.collection_export(spec)

    def resolve_runtime(self, spec: EntrypointDirectExportSpec) -> Callable[..., object]:
        return self.loader.runtime_export(spec)


def build_entrypoint_surface_exports(*, resolver: SurfaceExportResolver) -> Mapping[str, object]:
    def lazy_collection(spec: EntrypointDirectExportSpec) -> LazyCallableExport:
        return LazyCallableExport(lambda: resolver.resolve_collection(spec))

    def lazy_runtime(spec: EntrypointDirectExportSpec) -> LazyCallableExport:
        return LazyCallableExport(lambda: resolver.resolve_runtime(spec))

    direct_exports = build_entrypoint_direct_export_map(
        resolve_collection=lazy_collection,
        resolve_runtime=lazy_runtime,
    )
    return MappingProxyType(
        build_runtime_surface_bindings(
            resolver,
            resolver=resolver.resolve_legacy,
            binding_names=set(ENTRYPOINT_MODULE_STABLE_NAMES),
        )
        | direct_exports
    )


def build_entrypoint_module_surface(
    *,
    launcher: LazyEntrypointLauncher,
    resolve_fallback: Callable[[str], object],
) -> EntrypointModuleSurface:
    return EntrypointModuleSurface(
        exports=build_entrypoint_surface_exports(
            resolver=EntrypointSurfaceExportAdapter(loader=launcher.loader),
        ),
        resolve_fallback=resolve_fallback,
    )
