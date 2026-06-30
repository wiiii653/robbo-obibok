"""Bridge helpers around cached entrypoint state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from app_services import AppServicesProtocol
from collection_specs import CollectionSpec
import entrypoint_state_protocols as state_protocols

if TYPE_CHECKING:
    from legacy_runtime_bindings import LegacyRuntimeBindings
    from playback_assets import PlaybackAssetRuntime
    from playback_helpers import NowPlayingDependencies
    from runtime_protocols import ArchiveRuntimeProtocol, PlaybackRuntimeProtocol
    from runtime_service_facade import RuntimeServiceFacade
    from stream_runtime import MonitorAudioSource, StreamRuntime


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
    playback_service: "PlaybackRuntimeProtocol | None"
    legacy: "LegacyRuntimeBindings"


@dataclass(slots=True)
class EntrypointComponentAccess:
    state: state_protocols.EntrypointComponentAccessStateProtocol
    ensure_components: Callable[[], None]

    def require(self) -> EntrypointComponents:
        self.ensure_components()
        if hasattr(self.state, "component_bundle"):
            return self.state.component_bundle()
        assert self.state.app_services is not None
        assert self.state.service_facade is not None
        assert self.state.stream_runtime is not None
        assert self.state.archive_runtime is not None
        assert self.state.playback_assets is not None
        assert self.state.now_playing_deps is not None
        assert self.state.legacy is not None
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
