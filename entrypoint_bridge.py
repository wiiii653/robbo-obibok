"""Bridge helpers around cached entrypoint state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from app_services import AppServicesProtocol
from app_state import PlaylistState
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


@dataclass(slots=True)
class EntrypointFacade:
    components: EntrypointComponentAccess

    async def switch_collection(
        self,
        ctx: object,
        mode: str,
        *,
        flip_seq: list[str] | None = None,
    ) -> bool:
        return await self.components.require().service_facade.switch_collection(ctx, mode, flip_seq=flip_seq)

    async def skip_to_next(self, ctx: object) -> None:
        await self.components.require().service_facade.skip_to_next(ctx)

    def cleanup_subsong_temp_wavs(self, state: PlaylistState) -> None:
        self.components.require().service_facade.cleanup_subsong_temp_wavs(state)

    def cleanup_orphan_players(self) -> None:
        self.components.require().legacy.cleanup_orphan_players()

    def stop_all_players(self) -> None:
        self.components.require().legacy.stop_all_players()

    async def auto_play_after_switch(self, ctx: object, state: PlaylistState) -> None:
        await self.components.require().legacy.auto_play_after_switch(ctx, state)

    async def play_subsong(
        self,
        ctx: object,
        state: PlaylistState,
        subsong: int,
        *,
        audacious_stop: Callable[[], None],
        audacious_play: Callable[[str], None],
        setup_monitor_source: Callable[[object], None],
    ) -> bool:
        return await self.components.require().legacy.play_subsong(
            ctx,
            state,
            subsong,
            audacious_stop=audacious_stop,
            audacious_play=audacious_play,
            setup_monitor_source=setup_monitor_source,
        )
