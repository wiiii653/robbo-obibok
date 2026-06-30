"""Structural contracts for consumers of mutable entrypoint state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Protocol

if TYPE_CHECKING:
    import asyncio

    from app_bootstrap import ArchiveRegistryViews, BootstrappedApp
    from app_context import AppContext
    from app_services import AppServicesProtocol
    from app_state import AppRuntimeState
    from archive_catalog import ArchiveCatalog
    from archive_runtime import ArchiveRuntime
    from bot_runtime import BotRuntime
    from runtime_bootstrap import StartupEnvironment
    from collection_specs import CollectionSpec
    from entrypoint_bridge import EntrypointComponents as EntrypointAccessComponents
    from entrypoint_runtime import AppAssembly
    from legacy_runtime_bindings import LegacyRuntimeBindings
    from playback_assets import PlaybackAssetRuntime
    from playback_helpers import NowPlayingDependencies
    from runtime_composition import ComposedRuntime
    from runtime_io import AudioProcessRuntime
    from runtime_protocols import CollectionRuntimeProtocol, PlaybackRuntimeProtocol
    from runtime_registration import RuntimeRegistration
    from runtime_service_facade import RuntimeServiceFacade
    from stream_runtime import MonitorAudioSource, StreamRuntime
    from subsong_runtime import SubsongRuntime


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

    def component_bundle(self) -> EntrypointAccessComponents: ...


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
