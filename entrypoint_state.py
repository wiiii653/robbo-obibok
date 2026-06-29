"""Cached mutable state for the entrypoint module."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Mapping

from app_bootstrap import ArchiveRegistryViews, BootstrappedApp
from app_context import AppContext
from app_services import AppServicesProtocol
from app_state import AppRuntimeState
from archive_catalog import ArchiveCatalog
from archive_runtime import ArchiveRuntime
from bot_runtime import BotRuntime
from boot_runtime import StartupEnvironment
from runtime_io import AudioProcessRuntime
from collection_service import CollectionService
from collection_specs import CollectionSpec
from playback_assets import PlaybackAssetRuntime
from playback_helpers import NowPlayingDependencies
from playback_service import PlaybackService
from runtime_service_facade import RuntimeServiceFacade
from subsong_runtime import SubsongRuntime

if TYPE_CHECKING:
    from entrypoint_bridge import EntrypointComponents
    from stream_runtime import MonitorAudioSource, StreamRuntime
    from runtime_registration import RuntimeRegistration
    from runtime_composition import ComposedRuntime
    from entrypoint_runtime import AppAssembly


@dataclass(slots=True)
class EntrypointRuntimeComponentState:
    service_facade: RuntimeServiceFacade | None = None
    stream_runtime: "StreamRuntime | None" = None
    active_streams: dict[int, "MonitorAudioSource"] = field(default_factory=dict)
    archive_runtime: ArchiveRuntime | None = None
    playback_assets: PlaybackAssetRuntime | None = None
    now_playing_deps: NowPlayingDependencies | None = None
    collections: dict[str, CollectionSpec] = field(default_factory=dict)
    playback_service: PlaybackService | None = None
    legacy: object | None = None


@dataclass(slots=True)
class EntrypointInitializedRuntimeState:
    app: "AppAssembly | None" = None
    startup_env: StartupEnvironment | None = None
    runtime_registration: "RuntimeRegistration | None" = None
    composed_runtime: "ComposedRuntime | None" = None
    runtime: BotRuntime | None = None
    collection_service: CollectionService | None = None
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


@dataclass(slots=True)
class EntrypointState:
    audio_runtime: AudioProcessRuntime | None = None
    subsongs_runtime: SubsongRuntime | None = None
    _bootstrap_registry_state: EntrypointBootstrapRegistryState = field(default_factory=EntrypointBootstrapRegistryState)
    _archive_metadata_state: EntrypointArchiveMetadataState = field(default_factory=EntrypointArchiveMetadataState)
    _component_state: EntrypointRuntimeComponentState = field(default_factory=EntrypointRuntimeComponentState)
    _initialized_runtime_state: EntrypointInitializedRuntimeState = field(
        default_factory=EntrypointInitializedRuntimeState
    )

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
        playback_service: PlaybackService | None = None,
        legacy: object | None = None,
        app: "AppAssembly | None" = None,
        startup_env: StartupEnvironment | None = None,
        runtime_registration: "RuntimeRegistration | None" = None,
        composed_runtime: "ComposedRuntime | None" = None,
        runtime: BotRuntime | None = None,
        collection_service: CollectionService | None = None,
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
    def playback_service(self) -> PlaybackService | None:
        return self._component_state.playback_service

    @playback_service.setter
    def playback_service(self, value: PlaybackService | None) -> None:
        self._component_state.playback_service = value

    @property
    def legacy(self) -> object | None:
        return self._component_state.legacy

    @legacy.setter
    def legacy(self, value: object | None) -> None:
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
    def collection_service(self) -> CollectionService | None:
        return self._initialized_runtime_state.collection_service

    @collection_service.setter
    def collection_service(self, value: CollectionService | None) -> None:
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

    @property
    def _fallback_metadata_index(self) -> dict[str, dict[str, str]]:
        return self._archive_metadata_state.fallback_metadata_index

    @_fallback_metadata_index.setter
    def _fallback_metadata_index(self, value: dict[str, dict[str, str]]) -> None:
        self._archive_metadata_state.fallback_metadata_index = value

    @property
    def _fallback_modarchive_name_map(self) -> dict[str, str]:
        return self._archive_metadata_state.fallback_modarchive_name_map

    @_fallback_modarchive_name_map.setter
    def _fallback_modarchive_name_map(self, value: dict[str, str]) -> None:
        self._archive_metadata_state.fallback_modarchive_name_map = value

    @property
    def _fallback_sid_durations(self) -> dict[str, int]:
        return self._archive_metadata_state.fallback_sid_durations

    @_fallback_sid_durations.setter
    def _fallback_sid_durations(self, value: dict[str, int]) -> None:
        self._archive_metadata_state.fallback_sid_durations = value

    @property
    def _fallback_snes_metadata(self) -> dict[str, dict[str, object]]:
        return self._archive_metadata_state.fallback_snes_metadata

    @_fallback_snes_metadata.setter
    def _fallback_snes_metadata(self, value: dict[str, dict[str, object]]) -> None:
        self._archive_metadata_state.fallback_snes_metadata = value

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
        self.bootstrapped_app = bootstrapped_app
        self.app_context = app_context
        self.app_state = app_state
        self.archives = archives
        self.app_services = app_services
        self.archive_views = archive_views

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
        legacy: object,
    ) -> None:
        self.service_facade = service_facade
        self.stream_runtime = stream_runtime
        self.active_streams = active_streams
        self.archive_runtime = archive_runtime
        self.playback_assets = playback_assets
        self.now_playing_deps = now_playing_deps
        self.collections = collections
        self.legacy = legacy

    def cache_initialized_app(self, app: "AppAssembly") -> "AppAssembly":
        self.app = app
        self.startup_env = app.startup_env
        self.lock_file = self.startup_env.lock_file
        self.shutdown_flag = self.startup_env.shutdown_flag
        self.runtime_registration = app.runtime_registration
        self.composed_runtime = self.runtime_registration.composed
        self.runtime = self.runtime_registration.runtime
        self.collection_service = app.collection_service
        self.playback_service = app.playback_service
        return app

    def component_bundle(self) -> "EntrypointComponents":
        from entrypoint_bridge import EntrypointComponents

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
        return self._fallback_metadata_index

    def metadata_entry(self, url: str) -> dict[str, str] | None:
        return self.runtime_metadata_index().get(url)

    def runtime_modarchive_name_map(self) -> Mapping[str, str]:
        if self.archives is not None:
            return self.archives.modarchive_name_map_view
        if self.archive_views is not None:
            return self.archive_views.modarchive_name_map
        return self._fallback_modarchive_name_map

    def modarchive_track_name(self, url: str) -> str | None:
        return self.runtime_modarchive_name_map().get(url)

    def runtime_snes_metadata(self) -> Mapping[str, dict[str, object]]:
        if self.archives is not None:
            return self.archives.snes_metadata_view
        if self.archive_views is not None:
            return self.archive_views.snes_metadata
        return self._fallback_snes_metadata

    def runtime_sid_durations(self) -> Mapping[str, int]:
        if self.archives is not None:
            return self.archives.sid_durations_view
        if self.archive_views is not None:
            return self.archive_views.sid_durations
        return self._fallback_sid_durations

    def has_snes_metadata(self) -> bool:
        return bool(self.runtime_snes_metadata())

    def snes_game_entry(self, url: str) -> dict[str, object] | None:
        return self.runtime_snes_metadata().get(url)

    def iter_snes_games(self) -> Iterable[tuple[str, dict[str, object]]]:
        return self.runtime_snes_metadata().items()
