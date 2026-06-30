"""Deferred facades over composed runtime services for entrypoint wiring."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable, Iterable

from app_state import PlaylistState
from app_services import AppServicesProtocol
from archive_catalog import CollectionInfo
from runtime_protocols import CollectionRuntimeProtocol, PlaybackRuntimeProtocol, SubsongRuntimeProtocol


@dataclass(slots=True)
class RuntimeServiceFacade:
    app_services: AppServicesProtocol
    blacklist_loader: Callable[[], dict]
    blacklist_filter: Callable[[list[str], dict, int | str], list[str]]
    logger: logging.Logger
    stop_all_players_impl: Callable[[Iterable[PlaylistState], Callable[[PlaylistState], None]], None]
    subsongs: SubsongRuntimeProtocol
    collection_service: CollectionRuntimeProtocol | None = None
    playback_service: PlaybackRuntimeProtocol | None = None

    def bind(
        self,
        *,
        collection_service: CollectionRuntimeProtocol,
        playback_service: PlaybackRuntimeProtocol,
    ) -> None:
        self.collection_service = collection_service
        self.playback_service = playback_service

    def _collection(self) -> CollectionRuntimeProtocol:
        assert self.collection_service is not None
        return self.collection_service

    def _playback(self) -> PlaybackRuntimeProtocol:
        assert self.playback_service is not None
        return self.playback_service

    def get_collection_info(self, mode: str) -> CollectionInfo:
        return self._collection().get_collection_info(mode)

    async def load_tracks_for_mode(self, mode: str) -> list[str] | None:
        return await self._collection().load_tracks_for_mode(mode)

    async def ensure_tracks(self, state: PlaylistState) -> bool:
        return await self._collection().ensure_tracks(state)

    async def switch_collection(self, ctx: object, mode: str, *, flip_seq=None) -> bool:
        return await self._collection().switch_collection(ctx, mode, flip_seq=flip_seq)

    def get_cache_count(self, fname: str) -> int | str:
        return self._collection().get_cache_count(fname)

    def get_all_cache_counts(self, cache_map: dict[str, tuple[str, str]]) -> dict[str, tuple[str, int | str]]:
        return self._collection().get_all_cache_counts(cache_map)

    async def play_current_track(self, ctx: object) -> bool:
        return await self._playback().play_current_track(ctx)

    async def pre_download_next(self, state: PlaylistState) -> None:
        await self._playback().pre_download_next(state)

    async def start_targeted_playback_session(self, ctx: object, state: PlaylistState, url: str) -> bool:
        return await self._playback().start_targeted_playback_session(ctx, state, url)

    async def skip_to_next(self, ctx: object) -> None:
        await self._playback().skip_to_next(ctx)

    async def auto_play_after_switch(self, ctx: object, state: PlaylistState) -> None:
        await self._playback().auto_play_after_switch(ctx, state)

    async def fetch_metadata_background(self) -> None:
        await self._playback().fetch_metadata_background()

    def stop_all_players(self, cleanup_subsong_temp_wavs: Callable[[PlaylistState], None]) -> None:
        self.stop_all_players_impl(self.app_services.iter_guild_states(), cleanup_subsong_temp_wavs)

    def filter_blacklisted(self, tracks: list[str], user_id: int | str) -> list[str]:
        blacklist = self.blacklist_loader()
        filtered = self.blacklist_filter(tracks, blacklist, user_id)
        if len(filtered) < len(tracks):
            self.logger.info(
                "Filtered %d blacklisted tracks for user %s",
                len(tracks) - len(filtered),
                user_id,
            )
        return filtered

    def get_subsongs(self, filepath: str) -> list[float]:
        return self.subsongs.get_subsongs(filepath)

    def has_subsongs(self, filepath: str) -> bool:
        return self.subsongs.has_subsongs(filepath)

    def convert_subsong(self, filepath: str, subsong: int, output_path: str) -> bool:
        return self.subsongs.convert_subsong(filepath, subsong, output_path)

    def subsong_temp_path(self, filepath: str, subsong: int) -> str:
        return self.subsongs.subsong_temp_path(filepath, subsong)

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
        return await self.subsongs.play_subsong(
            ctx,
            state,
            subsong,
            audacious_stop=audacious_stop,
            audacious_play=audacious_play,
            setup_monitor_source=setup_monitor_source,
        )

    def cleanup_subsong_temp_wavs(self, state: PlaylistState) -> None:
        self.subsongs.cleanup_subsong_temp_wavs(state)
