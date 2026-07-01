"""Cached mutable state for the entrypoint module."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import auto, Enum
from typing import TYPE_CHECKING, Iterable, Mapping, Protocol

from domain_context import ArchiveRegistryViews, BootstrappedApp
from domain_context import AppContext
from domain_services import AppServicesProtocol
from domain_state import AppRuntimeState
from archive_catalog import ArchiveCatalog
from archive_runtime import ArchiveRuntime
from bot_runtime import BotRuntime
from runtime_bootstrap import StartupEnvironment
from runtime_io import AudioProcessRuntime
from collection_specs import CollectionSpec
from playback_assets import PlaybackAssetRuntime
from playback_helpers import NowPlayingDependencies
from runtime_protocols import CollectionRuntimeProtocol, PlaybackRuntimeProtocol
from runtime_service_facade import RuntimeServiceFacade
from subsong_runtime import SubsongRuntime

if TYPE_CHECKING:
    from entrypoint_app import EntrypointComponents
    from runtime_bindings import LegacyRuntimeBindings
    from stream_runtime import MonitorAudioSource, StreamRuntime
    from runtime_registration import RuntimeRegistration
    from runtime_composition import ComposedRuntime
    from entrypoint_runtime import AppAssembly


class EntrypointComponentAccessStateProtocol(Protocol):
    """Initialized component state exposed to runtime consumers."""

    app_services: AppServicesProtocol | None
    service_facade: RuntimeServiceFacade | None
    stream_runtime: StreamRuntime | None
    archive_runtime: ArchiveRuntime | None
    playback_assets: PlaybackAssetRuntime | None
    now_playing_deps: NowPlayingDependencies | None
    collections: dict[str, CollectionSpec]
    active_streams: dict[int, MonitorAudioSource]
    playback_service: PlaybackRuntimeProtocol | None
    legacy: LegacyRuntimeBindings | None

    def component_bundle(self) -> EntrypointComponents: ...


class EntrypointComponentAssemblyStateProtocol(Protocol):
    """Mutable state populated by entrypoint component assembly."""

    bootstrapped_app: BootstrappedApp | None
    app_context: AppContext | None
    app_state: AppRuntimeState | None
    archives: ArchiveCatalog | None
    app_services: AppServicesProtocol | None
    archive_views: ArchiveRegistryViews | None
    service_facade: RuntimeServiceFacade | None
    stream_runtime: StreamRuntime | None
    active_streams: dict[int, MonitorAudioSource]
    archive_runtime: ArchiveRuntime | None
    playback_assets: PlaybackAssetRuntime | None
    now_playing_deps: NowPlayingDependencies | None
    collections: dict[str, CollectionSpec]
    legacy: LegacyRuntimeBindings | None

    def apply_bootstrap_registry(
        self,
        *,
        bootstrapped_app: BootstrappedApp,
        app_context: AppContext,
        app_state: AppRuntimeState,
        archives: ArchiveCatalog,
        app_services: AppServicesProtocol,
        archive_views: ArchiveRegistryViews,
    ) -> None: ...

    def apply_runtime_components(
        self,
        *,
        service_facade: RuntimeServiceFacade,
        stream_runtime: StreamRuntime,
        active_streams: dict[int, MonitorAudioSource],
        archive_runtime: ArchiveRuntime,
        playback_assets: PlaybackAssetRuntime,
        now_playing_deps: NowPlayingDependencies,
        collections: dict[str, CollectionSpec],
        legacy: LegacyRuntimeBindings,
    ) -> None: ...


class EntrypointResourceStateProtocol(Protocol):
    audio_runtime: AudioProcessRuntime | None
    subsongs_runtime: SubsongRuntime | None


class EntrypointGlueStateProtocol(Protocol):
    """Marker contract for state retained, but not read, by entrypoint glue."""


class EntrypointSupportStateProtocol(EntrypointResourceStateProtocol, Protocol):
    archive_runtime: ArchiveRuntime | None
    service_facade: RuntimeServiceFacade | None


class EntrypointCompatStateProtocol(Protocol):
    """State attributes exposed through the legacy compatibility surface."""

    stream_runtime: StreamRuntime | None
    now_playing_deps: NowPlayingDependencies | None
    legacy: LegacyRuntimeBindings | None
    app: AppAssembly | None
    runtime_registration: RuntimeRegistration | None
    lock_file: str | None
    shutdown_flag: asyncio.Event | None


class EntrypointRuntimeStateProtocol(Protocol):
    app: AppAssembly | None
    startup_env: StartupEnvironment | None
    runtime_registration: RuntimeRegistration | None
    composed_runtime: ComposedRuntime | None
    runtime: BotRuntime | None
    collection_service: CollectionRuntimeProtocol | None
    playback_service: PlaybackRuntimeProtocol | None
    lock_file: str | None
    shutdown_flag: asyncio.Event | None

    def cache_initialized_app(self, app: AppAssembly) -> AppAssembly: ...


class EntrypointBootstrapStateProtocol(Protocol):
    archives: ArchiveCatalog | None
    service_facade: RuntimeServiceFacade | None

    def runtime_metadata_index(self) -> dict[str, dict[str, str]]: ...

    def runtime_modarchive_name_map(self) -> Mapping[str, str]: ...

    def runtime_snes_metadata(self) -> Mapping[str, dict[str, object]]: ...


class EntrypointRuntimeInitializerStateProtocol(
    EntrypointRuntimeStateProtocol,
    EntrypointBootstrapStateProtocol,
    Protocol,
):
    pass


class EntrypointStateProtocol(
    EntrypointComponentAccessStateProtocol,
    EntrypointComponentAssemblyStateProtocol,
    EntrypointSupportStateProtocol,
    EntrypointCompatStateProtocol,
    EntrypointRuntimeInitializerStateProtocol,
    Protocol,
):
    """Complete state contract used by entrypoint composition roots."""


@dataclass(slots=True)
class EntrypointRuntimeComponentState:
    service_facade: RuntimeServiceFacade | None = None
    stream_runtime: "StreamRuntime | None" = None
    active_streams: dict[int, "MonitorAudioSource"] = field(default_factory=dict)
    archive_runtime: ArchiveRuntime | None = None
    playback_assets: PlaybackAssetRuntime | None = None
    now_playing_deps: NowPlayingDependencies | None = None
    collections: dict[str, CollectionSpec] = field(default_factory=dict)
    playback_service: PlaybackRuntimeProtocol | None = None
    legacy: "LegacyRuntimeBindings | None" = None


@dataclass(slots=True)
class EntrypointInitializedRuntimeState:
    app: "AppAssembly | None" = None
    startup_env: StartupEnvironment | None = None
    runtime_registration: "RuntimeRegistration | None" = None
    composed_runtime: "ComposedRuntime | None" = None
    runtime: BotRuntime | None = None
    collection_service: CollectionRuntimeProtocol | None = None
    lock_file: str | None = None
    shutdown_flag: asyncio.Event | None = None


@dataclass(slots=True)
class EntrypointBootstrapRegistryState:
    bootstrapped_app: BootstrappedApp | None = None
    app_context: AppContext | None = None
    app_state: AppRuntimeState | None = None
    archives: ArchiveCatalog | None = None
    app_services: AppServicesProtocol | None = None
    archive_views: ArchiveRegistryViews | None = None


@dataclass(slots=True)
class EntrypointArchiveMetadataState:
    fallback_metadata_index: dict[str, dict[str, str]] = field(default_factory=dict)
    fallback_modarchive_name_map: dict[str, str] = field(default_factory=dict)
    fallback_sid_durations: dict[str, int] = field(default_factory=dict)
    fallback_snes_metadata: dict[str, dict[str, object]] = field(default_factory=dict)


class EntrypointLifecycle(Enum):
    """Lifecycle phase of the entrypoint state machine.

    Transitions: UNINITIALIZED → BOOTSTRAP → COMPONENTS → RUNTIME → RUNNING → STOPPED
    """
    UNINITIALIZED = auto()
    BOOTSTRAP = auto()
    COMPONENTS = auto()
    RUNTIME = auto()
    RUNNING = auto()
    STOPPED = auto()


@dataclass(slots=True)
class EntrypointState:
    """Central mutable state hub for the entrypoint module.

    The launcher instantiates this concrete backing store, while consumers
    depend on focused contracts from entrypoint_state_protocols. Production
    writes primarily flow through apply_bootstrap_registry(),
    apply_runtime_components(), and cache_initialized_app(). Property setters
    retain compatibility with launcher caching and tests.

    Dedicated domain methods (runtime_metadata_index(), component_bundle(),
    etc.) replace direct field reads, reducing coupling to internal layout.
    """
    audio_runtime: AudioProcessRuntime | None = None
    subsongs_runtime: SubsongRuntime | None = None
    _bootstrap_registry_state: EntrypointBootstrapRegistryState = field(default_factory=EntrypointBootstrapRegistryState)
    _archive_metadata_state: EntrypointArchiveMetadataState = field(default_factory=EntrypointArchiveMetadataState)
    _component_state: EntrypointRuntimeComponentState = field(default_factory=EntrypointRuntimeComponentState)
    _initialized_runtime_state: EntrypointInitializedRuntimeState = field(
        default_factory=EntrypointInitializedRuntimeState
    )
    _lifecycle: EntrypointLifecycle = EntrypointLifecycle.UNINITIALIZED

    def __init__(
        self,
        audio_runtime: AudioProcessRuntime | None = None,
        subsongs_runtime: SubsongRuntime | None = None,
        *,
        bootstrapped_app: BootstrappedApp | None = None,
        app_context: AppContext | None = None,
        app_state: AppRuntimeState | None = None,
        archives: ArchiveCatalog | None = None,
        app_services: AppServicesProtocol | None = None,
        archive_views: ArchiveRegistryViews | None = None,
        service_facade: RuntimeServiceFacade | None = None,
        stream_runtime: "StreamRuntime | None" = None,
        active_streams: dict[int, "MonitorAudioSource"] | None = None,
        archive_runtime: ArchiveRuntime | None = None,
        playback_assets: PlaybackAssetRuntime | None = None,
        now_playing_deps: NowPlayingDependencies | None = None,
        collections: dict[str, CollectionSpec] | None = None,
        playback_service: PlaybackRuntimeProtocol | None = None,
        legacy: "LegacyRuntimeBindings | None" = None,
        app: "AppAssembly | None" = None,
        startup_env: StartupEnvironment | None = None,
        runtime_registration: "RuntimeRegistration | None" = None,
        composed_runtime: "ComposedRuntime | None" = None,
        runtime: BotRuntime | None = None,
        collection_service: CollectionRuntimeProtocol | None = None,
        lock_file: str | None = None,
        shutdown_flag: asyncio.Event | None = None,
    ) -> None:
        self.audio_runtime = audio_runtime
        self.subsongs_runtime = subsongs_runtime
        self._bootstrap_registry_state = EntrypointBootstrapRegistryState(
            bootstrapped_app=bootstrapped_app,
            app_context=app_context,
            app_state=app_state,
            archives=archives,
            app_services=app_services,
            archive_views=archive_views,
        )
        self._archive_metadata_state = EntrypointArchiveMetadataState()
        self._component_state = EntrypointRuntimeComponentState(
            service_facade=service_facade,
            stream_runtime=stream_runtime,
            active_streams={} if active_streams is None else active_streams,
            archive_runtime=archive_runtime,
            playback_assets=playback_assets,
            now_playing_deps=now_playing_deps,
            collections={} if collections is None else collections,
            playback_service=playback_service,
            legacy=legacy,
        )
        self._initialized_runtime_state = EntrypointInitializedRuntimeState(
            app=app,
            startup_env=startup_env,
            runtime_registration=runtime_registration,
            composed_runtime=composed_runtime,
            runtime=runtime,
            collection_service=collection_service,
            lock_file=lock_file,
            shutdown_flag=shutdown_flag,
        )
        self._lifecycle = EntrypointLifecycle.UNINITIALIZED

    @property
    def service_facade(self) -> RuntimeServiceFacade | None:
        return self._component_state.service_facade

    @service_facade.setter
    def service_facade(self, value: RuntimeServiceFacade | None) -> None:
        self._component_state.service_facade = value

    @property
    def bootstrapped_app(self) -> BootstrappedApp | None:
        return self._bootstrap_registry_state.bootstrapped_app

    @bootstrapped_app.setter
    def bootstrapped_app(self, value: BootstrappedApp | None) -> None:
        self._bootstrap_registry_state.bootstrapped_app = value

    @property
    def app_context(self) -> AppContext | None:
        return self._bootstrap_registry_state.app_context

    @app_context.setter
    def app_context(self, value: AppContext | None) -> None:
        self._bootstrap_registry_state.app_context = value

    @property
    def app_state(self) -> AppRuntimeState | None:
        return self._bootstrap_registry_state.app_state

    @app_state.setter
    def app_state(self, value: AppRuntimeState | None) -> None:
        self._bootstrap_registry_state.app_state = value

    @property
    def archives(self) -> ArchiveCatalog | None:
        return self._bootstrap_registry_state.archives

    @archives.setter
    def archives(self, value: ArchiveCatalog | None) -> None:
        self._bootstrap_registry_state.archives = value

    @property
    def app_services(self) -> AppServicesProtocol | None:
        return self._bootstrap_registry_state.app_services

    @app_services.setter
    def app_services(self, value: AppServicesProtocol | None) -> None:
        self._bootstrap_registry_state.app_services = value

    @property
    def archive_views(self) -> ArchiveRegistryViews | None:
        return self._bootstrap_registry_state.archive_views

    @archive_views.setter
    def archive_views(self, value: ArchiveRegistryViews | None) -> None:
        self._bootstrap_registry_state.archive_views = value

    @property
    def stream_runtime(self) -> "StreamRuntime | None":
        return self._component_state.stream_runtime

    @stream_runtime.setter
    def stream_runtime(self, value: "StreamRuntime | None") -> None:
        self._component_state.stream_runtime = value

    @property
    def active_streams(self) -> dict[int, "MonitorAudioSource"]:
        return self._component_state.active_streams

    @active_streams.setter
    def active_streams(self, value: dict[int, "MonitorAudioSource"]) -> None:
        self._component_state.active_streams = value

    @property
    def archive_runtime(self) -> ArchiveRuntime | None:
        return self._component_state.archive_runtime

    @archive_runtime.setter
    def archive_runtime(self, value: ArchiveRuntime | None) -> None:
        self._component_state.archive_runtime = value

    @property
    def playback_assets(self) -> PlaybackAssetRuntime | None:
        return self._component_state.playback_assets

    @playback_assets.setter
    def playback_assets(self, value: PlaybackAssetRuntime | None) -> None:
        self._component_state.playback_assets = value

    @property
    def now_playing_deps(self) -> NowPlayingDependencies | None:
        return self._component_state.now_playing_deps

    @now_playing_deps.setter
    def now_playing_deps(self, value: NowPlayingDependencies | None) -> None:
        self._component_state.now_playing_deps = value

    @property
    def collections(self) -> dict[str, CollectionSpec]:
        return self._component_state.collections

    @collections.setter
    def collections(self, value: dict[str, CollectionSpec]) -> None:
        self._component_state.collections = value

    @property
    def playback_service(self) -> PlaybackRuntimeProtocol | None:
        return self._component_state.playback_service

    @playback_service.setter
    def playback_service(self, value: PlaybackRuntimeProtocol | None) -> None:
        self._component_state.playback_service = value

    @property
    def legacy(self) -> "LegacyRuntimeBindings | None":
        return self._component_state.legacy

    @legacy.setter
    def legacy(self, value: "LegacyRuntimeBindings | None") -> None:
        self._component_state.legacy = value

    @property
    def app(self) -> "AppAssembly | None":
        return self._initialized_runtime_state.app

    @app.setter
    def app(self, value: "AppAssembly | None") -> None:
        self._initialized_runtime_state.app = value

    @property
    def startup_env(self) -> StartupEnvironment | None:
        return self._initialized_runtime_state.startup_env

    @startup_env.setter
    def startup_env(self, value: StartupEnvironment | None) -> None:
        self._initialized_runtime_state.startup_env = value

    @property
    def runtime_registration(self) -> "RuntimeRegistration | None":
        return self._initialized_runtime_state.runtime_registration

    @runtime_registration.setter
    def runtime_registration(self, value: "RuntimeRegistration | None") -> None:
        self._initialized_runtime_state.runtime_registration = value

    @property
    def composed_runtime(self) -> "ComposedRuntime | None":
        return self._initialized_runtime_state.composed_runtime

    @composed_runtime.setter
    def composed_runtime(self, value: "ComposedRuntime | None") -> None:
        self._initialized_runtime_state.composed_runtime = value

    @property
    def runtime(self) -> BotRuntime | None:
        return self._initialized_runtime_state.runtime

    @runtime.setter
    def runtime(self, value: BotRuntime | None) -> None:
        self._initialized_runtime_state.runtime = value

    @property
    def collection_service(self) -> CollectionRuntimeProtocol | None:
        return self._initialized_runtime_state.collection_service

    @collection_service.setter
    def collection_service(self, value: CollectionRuntimeProtocol | None) -> None:
        self._initialized_runtime_state.collection_service = value

    @property
    def lock_file(self) -> str | None:
        return self._initialized_runtime_state.lock_file

    @lock_file.setter
    def lock_file(self, value: str | None) -> None:
        self._initialized_runtime_state.lock_file = value

    @property
    def shutdown_flag(self) -> asyncio.Event | None:
        return self._initialized_runtime_state.shutdown_flag

    @shutdown_flag.setter
    def shutdown_flag(self, value: asyncio.Event | None) -> None:
        self._initialized_runtime_state.shutdown_flag = value

    # ── Bulk mutation methods ────────────────────────────────────
    # All production writes flow through these methods. Individual
    # property setters exist for test convenience but are unused in
    # production — component wiring goes through apply_* methods
    # and consumers use Protocol-based interfaces exclusively.

    def apply_bootstrap_registry(
        self,
        *,
        bootstrapped_app: BootstrappedApp,
        app_context: AppContext,
        app_state: AppRuntimeState,
        archives: ArchiveCatalog,
        app_services: AppServicesProtocol,
        archive_views: ArchiveRegistryViews,
    ) -> None:
        assert self._lifecycle == EntrypointLifecycle.UNINITIALIZED, \
            f"cannot apply bootstrap in {self._lifecycle}"
        self.bootstrapped_app = bootstrapped_app
        self.app_context = app_context
        self.app_state = app_state
        self.archives = archives
        self.app_services = app_services
        self.archive_views = archive_views
        self._lifecycle = EntrypointLifecycle.BOOTSTRAP

    def apply_runtime_components(
        self,
        *,
        service_facade: RuntimeServiceFacade,
        stream_runtime: "StreamRuntime",
        active_streams: dict[int, "MonitorAudioSource"],
        archive_runtime: ArchiveRuntime,
        playback_assets: PlaybackAssetRuntime,
        now_playing_deps: NowPlayingDependencies,
        collections: dict[str, CollectionSpec],
        legacy: "LegacyRuntimeBindings",
    ) -> None:
        assert self._lifecycle in (EntrypointLifecycle.BOOTSTRAP, EntrypointLifecycle.UNINITIALIZED), \
            f"cannot apply runtime components in {self._lifecycle}"
        self.service_facade = service_facade
        self.stream_runtime = stream_runtime
        self.active_streams = active_streams
        self.archive_runtime = archive_runtime
        self.playback_assets = playback_assets
        self.now_playing_deps = now_playing_deps
        self.collections = collections
        self.legacy = legacy
        self._lifecycle = EntrypointLifecycle.COMPONENTS

    def cache_initialized_app(self, app: "AppAssembly") -> "AppAssembly":
        assert self._lifecycle in (EntrypointLifecycle.COMPONENTS, EntrypointLifecycle.BOOTSTRAP, EntrypointLifecycle.UNINITIALIZED), \
            f"cannot cache initialized app in {self._lifecycle}"
        self.app = app
        self.startup_env = app.startup_env
        self.lock_file = self.startup_env.lock_file
        self.shutdown_flag = self.startup_env.shutdown_flag
        self.runtime_registration = app.runtime_registration
        self.composed_runtime = self.runtime_registration.composed
        self.runtime = self.runtime_registration.runtime
        self.collection_service = app.collection_service
        self.playback_service = app.playback_service
        self._lifecycle = EntrypointLifecycle.RUNTIME
        return app

    def component_bundle(self) -> "EntrypointComponents":
        from entrypoint_app import EntrypointComponents

        assert self.app_services is not None
        assert self.service_facade is not None
        assert self.stream_runtime is not None
        assert self.archive_runtime is not None
        assert self.playback_assets is not None
        assert self.now_playing_deps is not None
        assert self.legacy is not None
        return EntrypointComponents(
            app_services=self.app_services,
            service_facade=self.service_facade,
            stream_runtime=self.stream_runtime,
            archive_runtime=self.archive_runtime,
            playback_assets=self.playback_assets,
            now_playing_deps=self.now_playing_deps,
            collections=self.collections,
            active_streams=self.active_streams,
            playback_service=self.playback_service,
            legacy=self.legacy,
        )

    def runtime_metadata_index(self) -> dict[str, dict[str, str]]:
        if self.archives is not None:
            return self.archives.metadata_index
        return self._archive_metadata_state.fallback_metadata_index

    def metadata_entry(self, url: str) -> dict[str, str] | None:
        return self.runtime_metadata_index().get(url)

    def runtime_modarchive_name_map(self) -> Mapping[str, str]:
        if self.archives is not None:
            return self.archives.modarchive_name_map_view
        if self.archive_views is not None:
            return self.archive_views.modarchive_name_map
        return self._archive_metadata_state.fallback_modarchive_name_map

    def modarchive_track_name(self, url: str) -> str | None:
        return self.runtime_modarchive_name_map().get(url)

    def runtime_snes_metadata(self) -> Mapping[str, dict[str, object]]:
        if self.archives is not None:
            return self.archives.snes_metadata_view
        if self.archive_views is not None:
            return self.archive_views.snes_metadata
        return self._archive_metadata_state.fallback_snes_metadata

    def runtime_sid_durations(self) -> Mapping[str, int]:
        if self.archives is not None:
            return self.archives.sid_durations_view
        if self.archive_views is not None:
            return self.archive_views.sid_durations
        return self._archive_metadata_state.fallback_sid_durations

    def has_snes_metadata(self) -> bool:
        return bool(self.runtime_snes_metadata())

    def snes_game_entry(self, url: str) -> dict[str, object] | None:
        return self.runtime_snes_metadata().get(url)

    def iter_snes_games(self) -> Iterable[tuple[str, dict[str, object]]]:
        return self.runtime_snes_metadata().items()


if TYPE_CHECKING:
    def _assert_entrypoint_state_contracts(state: EntrypointState) -> None:
        component_access: EntrypointComponentAccessStateProtocol = state
        component_assembly: EntrypointComponentAssemblyStateProtocol = state
        resources: EntrypointResourceStateProtocol = state
        glue: EntrypointGlueStateProtocol = state
        support: EntrypointSupportStateProtocol = state
        compat: EntrypointCompatStateProtocol = state
        runtime: EntrypointRuntimeStateProtocol = state
        bootstrap: EntrypointBootstrapStateProtocol = state
        initializer: EntrypointRuntimeInitializerStateProtocol = state
        complete: EntrypointStateProtocol = state
