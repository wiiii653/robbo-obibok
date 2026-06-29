"""Lazy module loader support for the entrypoint launcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Mapping, Protocol
from entrypoint_runtime_surface import (
    EntrypointCompatRuntimeSurface,
    EntrypointRuntimeStateSurface,
    EntrypointStableRuntimeSurface,
    build_runtime_state_surface,
    build_stable_runtime_surface,
)

if TYPE_CHECKING:
    from entrypoint_module import EntrypointModule

from entrypoint_compat_contract import (
    ENTRYPOINT_COMPAT_APP,
    ENTRYPOINT_COMPAT_GUILD_ID,
    ENTRYPOINT_COMPAT_LEGACY,
    ENTRYPOINT_COMPAT_LOCK_FILE,
    ENTRYPOINT_COMPAT_NOW_PLAYING_DEPS,
    ENTRYPOINT_COMPAT_RUNTIME_REGISTRATION,
    ENTRYPOINT_COMPAT_SHUTDOWN_FLAG,
    ENTRYPOINT_COMPAT_STREAM_RUNTIME,
    ENTRYPOINT_COMPAT_VIEW_SPECS_BY_NAME,
    EntrypointCompatBindingSpec,
)
from entrypoint_direct_export_contract import (
    EntrypointDirectExportSpec,
    ENTRYPOINT_DIRECT_EXPORT_SPECS_BY_NAME,
)
from entrypoint_legacy_bindings import EntrypointLegacyBindings, build_entrypoint_legacy_bindings
from entrypoint_module_bindings import ENTRYPOINT_EXPORT_GRAPH


class CollectionLegacyProtocol(Protocol):
    skip_to_next: object
    cleanup_orphan_players: object
    stop_all_players: object
    auto_play_after_switch: object
    play_subsong: object


class CollectionServiceFacadeProtocol(Protocol):
    cleanup_subsong_temp_wavs: object
    switch_collection: object


class CollectionStateProtocol(Protocol):
    legacy: CollectionLegacyProtocol
    service_facade: CollectionServiceFacadeProtocol


class EntrypointCompatResolverProtocol(Protocol):
    def resolve(self, name: str) -> object: ...


class EntrypointModuleAppProtocol(Protocol):
    compat: EntrypointCompatResolverProtocol


class EntrypointLoadedModuleProtocol(Protocol):
    app: EntrypointModuleAppProtocol


class EntrypointLegacyExportsBindingsProtocol(Protocol):
    exports: Mapping[str, object]

    def resolve(self, name: str) -> object: ...


class LazyModuleAttr:
    def __init__(self, getter: Callable[[], object], attr_name: str):
        self._getter = getter
        self._attr_name = attr_name

    def _target(self) -> object:
        return getattr(self._getter(), self._attr_name)

    def __getattr__(self, name: str) -> object:
        return getattr(self._target(), name)

    def __call__(self, *args, **kwargs):
        return self._target()(*args, **kwargs)


@dataclass(frozen=True, slots=True)
class EntrypointCompatView:
    resolve_compat: Callable[[str], object]

    def resolve_spec(self, spec: EntrypointCompatBindingSpec) -> object:
        return self.resolve_compat(spec.export_name)

    def resolve_view(self, view_name: str) -> object:
        try:
            spec = ENTRYPOINT_COMPAT_VIEW_SPECS_BY_NAME[view_name]
        except KeyError as exc:
            raise AttributeError(view_name) from exc
        return self.resolve_spec(spec)


@dataclass(slots=True)
class EntrypointModuleLoader:
    module_factory: Callable[[], "EntrypointModule"]
    flip_order: list[str]
    flip_seq: list[str]
    module: "EntrypointModule | None" = None
    bindings: EntrypointLegacyBindings | None = None

    def ensure_module(self) -> "EntrypointModule":
        if self.module is None:
            self.module = self.module_factory()
            self.bindings = build_entrypoint_legacy_bindings(
                entrypoint_module=self.module,
                flip_order=self.flip_order,
                flip_seq=self.flip_seq,
            )
        return self.module

    def legacy_bindings(self) -> EntrypointLegacyBindings:
        self.ensure_module()
        assert self.bindings is not None
        return self.bindings

    def resolve_legacy(self, name: str) -> object:
        return self.legacy_bindings().resolve(name)

    def resolve_compat(self, name: str) -> object:
        return self.ensure_module().app.compat.resolve(name)

    def bootstrap_app(self) -> object:
        return self.legacy_bindings().state._APP

    def compat(self) -> EntrypointCompatView:
        return EntrypointCompatView(resolve_compat=self.resolve_compat)

    def resolve_compat_view(self, view_name: str) -> object:
        return self.compat().resolve_view(view_name)

    def stable_runtime_surface(self) -> EntrypointStableRuntimeSurface:
        return build_stable_runtime_surface(
            self.legacy_bindings(),
            resolver=self.resolve_legacy,
        )

    def runtime_state_surface(self) -> EntrypointRuntimeStateSurface:
        return build_runtime_state_surface(
            self.legacy_bindings(),
            resolver=self.resolve_legacy,
        )

    def collection_state(self) -> CollectionStateProtocol:
        return self.resolve_legacy("_STATE")

    def collection_export(self, spec: str | EntrypointDirectExportSpec) -> object:
        binding = self._direct_export_spec(spec)
        state = self.collection_state()
        target = state
        for attr_name in binding.attr_path:
            target = getattr(target, attr_name)
        return target

    def runtime_export(self, spec: str | EntrypointDirectExportSpec) -> object:
        binding = self._direct_export_spec(spec)
        exports = self.legacy_bindings().exports
        try:
            return exports[binding.export_name]
        except KeyError as exc:
            raise AttributeError(binding.export_name) from exc

    def resolve(self, name: str) -> object:
        try:
            return self.resolve_legacy(name)
        except AttributeError:
            if name not in ENTRYPOINT_EXPORT_GRAPH.compat_names:
                raise
            return self.resolve_compat(name)

    def proxy(self, attr_name: str) -> LazyModuleAttr:
        return LazyModuleAttr(self.ensure_module, attr_name)

    def _direct_export_spec(self, spec: str | EntrypointDirectExportSpec) -> EntrypointDirectExportSpec:
        if isinstance(spec, EntrypointDirectExportSpec):
            return spec
        try:
            return ENTRYPOINT_DIRECT_EXPORT_SPECS_BY_NAME[spec]
        except KeyError as exc:
            raise AttributeError(spec) from exc


def _build_compat_view_method(spec: EntrypointCompatBindingSpec) -> Callable[[EntrypointCompatView], object]:
    def _method(self: EntrypointCompatView) -> object:
        return self.resolve_spec(spec)

    return _method


def _build_loader_compat_method(spec: EntrypointCompatBindingSpec) -> Callable[[EntrypointModuleLoader], object]:
    def _method(self: EntrypointModuleLoader) -> object:
        return self.resolve_compat_view(spec.view_name)

    return _method


for _compat_spec in (
    ENTRYPOINT_COMPAT_GUILD_ID,
    ENTRYPOINT_COMPAT_STREAM_RUNTIME,
    ENTRYPOINT_COMPAT_NOW_PLAYING_DEPS,
    ENTRYPOINT_COMPAT_LEGACY,
    ENTRYPOINT_COMPAT_APP,
    ENTRYPOINT_COMPAT_RUNTIME_REGISTRATION,
    ENTRYPOINT_COMPAT_LOCK_FILE,
    ENTRYPOINT_COMPAT_SHUTDOWN_FLAG,
):
    setattr(EntrypointCompatView, _compat_spec.view_name, _build_compat_view_method(_compat_spec))
    setattr(EntrypointModuleLoader, _compat_spec.view_name, _build_loader_compat_method(_compat_spec))
