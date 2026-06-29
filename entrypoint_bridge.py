"""Bridge helpers around cached entrypoint state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol

from app_services import AppServicesProtocol
from collection_specs import CollectionSpec

if TYPE_CHECKING:
    from playback_assets import PlaybackAssetRuntime
    from playback_helpers import NowPlayingDependencies
    from playback_service import PlaybackService
    from runtime_protocols import ArchiveRuntimeProtocol
    from runtime_service_facade import RuntimeServiceFacade
    from stream_runtime import MonitorAudioSource, StreamRuntime


class EntrypointComponentStateProtocol(Protocol):
    app_services: AppServicesProtocol
    service_facade: "RuntimeServiceFacade"
    stream_runtime: "StreamRuntime"
    archive_runtime: "ArchiveRuntimeProtocol"
    playback_assets: "PlaybackAssetRuntime"
    now_playing_deps: "NowPlayingDependencies"
    collections: dict[str, CollectionSpec]
    active_streams: dict[int, "MonitorAudioSource"]
    playback_service: "PlaybackService | None"
    legacy: object

    def component_bundle(self) -> "EntrypointComponents": ...


class EntrypointGlueStateProtocol(Protocol):
    """Minimal state interface for EntrypointGlue.

    EntrypointGlue stores the state reference but never reads from it
    directly — all access goes through EntrypointResources and
    EntrypointComponentAccess.
    """
    pass


class EntrypointSupportStateProtocol(Protocol):
    """State interface for EntrypointSupport storage.

    Covers fields accessed directly from support.state across
    all callers: EntrypointResources reads audio_runtime and
    subsongs_runtime; app wiring reads archive_runtime and
    service_facade. All other consumers receive support.state
    through their own protocol-based constructors.
    """
    audio_runtime: object | None
    subsongs_runtime: object | None
    archive_runtime: object | None
    service_facade: object | None


class EntrypointCompatStateProtocol(Protocol):
    """State interface for legacy compat access patterns.

    Attributes accessed dynamically via getattr in
    build_entrypoint_compat_registry_attrs.
    """
    stream_runtime: object | None
    now_playing_deps: object | None
    legacy: object | None
    app: object | None
    runtime_registration: object | None
    lock_file: str | None
    shutdown_flag: object | None


@dataclass(slots=True)
class EntrypointComponents:
    app_services: AppServicesProtocol
    service_facade: "RuntimeServiceFacade"
    stream_runtime: "StreamRuntime"
    archive_runtime: "ArchiveRuntimeProtocol"
    playback_assets: "PlaybackAssetRuntime"
    now_playing_deps: "NowPlayingDependencies"
    collections: dict[str, CollectionSpec]
    active_streams: dict[int, "MonitorAudioSource"]
    playback_service: "PlaybackService | None"
    legacy: object


@dataclass(slots=True)
class EntrypointComponentAccess:
    state: EntrypointComponentStateProtocol
    ensure_components: Callable[[], None]

    def require(self) -> EntrypointComponents:
        self.ensure_components()
        if hasattr(self.state, "component_bundle"):
            return self.state.component_bundle()
        return EntrypointComponents(
            app_services=self.state.app_services,
            service_facade=self.state.service_facade,
            stream_runtime=self.state.stream_runtime,
            archive_runtime=self.state.archive_runtime,
            playback_assets=self.state.playback_assets,
            now_playing_deps=self.state.now_playing_deps,
            collections=self.state.collections,
            active_streams=self.state.active_streams,
            playback_service=self.state.playback_service,
            legacy=self.state.legacy,
        )
