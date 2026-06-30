"""Compatibility bindings for legacy entrypoint helper names."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from archive_catalog import CollectionInfo
from app_state import PlaylistState
from runtime_protocols import ArchiveRuntimeProtocol, PlaybackAssetsProtocol, ServiceFacadeProtocol

if TYPE_CHECKING:
    from aiohttp import ClientSession


@dataclass(slots=True)
class LegacyRuntimeBindings:
    archive_runtime: ArchiveRuntimeProtocol
    playback_assets: PlaybackAssetsProtocol
    service_facade: ServiceFacadeProtocol
    cleanup_subsong_temp_wavs_impl: Callable[[PlaylistState], None]

    def ym_to_wav(self, ym_path: str) -> str:
        return self.playback_assets.ym_to_wav(ym_path)

    def ym_cleanup(self) -> None:
        self.playback_assets.ym_cleanup()

    def resolve_local_path(self, url: str) -> str | None:
        return self.playback_assets.resolve_local_path(url)

    async def download_sap(self, url: str, retries: int = 2) -> str:
        return await self.playback_assets.download_sap(url, retries=retries)

    def parse_sap_header(self, filepath: str) -> dict[str, str]:
        return self.archive_runtime.parse_sap_header(filepath)

    def load_metadata_cache(self) -> dict[str, dict[str, str]]:
        return self.archive_runtime.load_metadata_cache()

    def save_metadata_cache(self, index: dict[str, dict[str, str]]) -> None:
        self.archive_runtime.save_metadata_cache(index)

    async def fetch_metadata_batch(
        self,
        session: ClientSession,
        urls: list[str],
        *,
        batch_size: int = 20,
    ) -> dict[str, dict[str, str]]:
        return await self.archive_runtime.fetch_metadata_batch(session, urls, batch_size=batch_size)

    def search_tracks(self, query: str, tracks: list[str], limit: int = 10) -> list[str]:
        return self.archive_runtime.search_tracks(query, tracks, limit=limit)

    async def refresh_tracklist(self) -> list[str]:
        return await self.archive_runtime.refresh_tracklist()

    def load_cached_tracklist(self) -> list[str] | None:
        return self.archive_runtime.load_cached_tracklist()

    def get_collection_info(self, mode: str) -> CollectionInfo:
        return self.service_facade.get_collection_info(mode)

    async def load_tracks_for_mode(self, mode: str) -> list[str] | None:
        return await self.service_facade.load_tracks_for_mode(mode)

    async def ensure_tracks(self, state: PlaylistState) -> bool:
        return await self.service_facade.ensure_tracks(state)

    async def play_current_track(self, ctx: object) -> bool:
        return await self.service_facade.play_current_track(ctx)

    async def skip_to_next(self, ctx: object) -> None:
        await self.service_facade.skip_to_next(ctx)

    def filter_blacklisted(self, tracks: list[str], user_id: int | str) -> list[str]:
        return self.service_facade.filter_blacklisted(tracks, user_id)

    def parse_songlengths_to_tracks(self, data: str) -> list[str]:
        return self.archive_runtime.parse_songlengths_to_tracks(data)

    def download_hvsc_index(self) -> list[str] | None:
        return self.archive_runtime.download_hvsc_index()

    def load_cached_hvsc(self) -> list[str] | None:
        return self.archive_runtime.load_cached_hvsc()

    def load_modarchive_cache(self) -> list[str] | None:
        return self.archive_runtime.load_modarchive_cache()

    def load_ay_cache(self) -> list[str] | None:
        return self.archive_runtime.load_ay_cache()

    def load_ym_cache(self) -> list[str] | None:
        return self.archive_runtime.load_ym_cache()

    def load_tiny_cache(self) -> list[str] | None:
        return self.archive_runtime.load_tiny_cache()

    def load_asma_local_cache(self) -> list[str] | None:
        return self.archive_runtime.load_asma_local_cache()

    def load_hvsc_local_cache(self) -> list[str] | None:
        return self.archive_runtime.load_hvsc_local_cache()

    def load_snes_cache(self) -> list[str] | None:
        return self.archive_runtime.load_snes_cache()

    async def download_spc_rsn(self, rsn_url: str, spc_now: str, game_name: str) -> str | None:
        return await self.archive_runtime.download_spc_rsn(rsn_url, spc_now, game_name)

    async def download_modarchive_module(self, url: str, retries: int = 2) -> str:
        return await self.archive_runtime.download_modarchive_module(url, retries=retries)

    def parse_sid_header(self, data: bytes) -> dict[str, str]:
        return self.archive_runtime.parse_sid_header(data)

    def cleanup_orphan_players(self) -> None:
        self.archive_runtime.cleanup_orphan_players()

    def stop_all_players(self) -> None:
        self.service_facade.stop_all_players(self.cleanup_subsong_temp_wavs_impl)

    async def switch_collection(
        self,
        ctx: object,
        mode: str,
        *,
        flip_seq: list[str] | None = None,
    ) -> bool:
        return await self.service_facade.switch_collection(ctx, mode, flip_seq=flip_seq)

    def get_cache_count(self, fname: str) -> int | str:
        return self.service_facade.get_cache_count(fname)

    def get_all_cache_counts(self, cache_map: dict[str, tuple[str, str]]) -> dict[str, tuple[str, int | str]]:
        return self.service_facade.get_all_cache_counts(cache_map)

    async def auto_play_after_switch(self, ctx: object, state: PlaylistState) -> None:
        await self.service_facade.auto_play_after_switch(ctx, state)

    def get_subsongs(self, filepath: str) -> list[float]:
        return self.service_facade.get_subsongs(filepath)

    def has_subsongs(self, filepath: str) -> bool:
        return self.service_facade.has_subsongs(filepath)

    def convert_subsong(self, filepath: str, subsong: int, output_path: str) -> bool:
        return self.service_facade.convert_subsong(filepath, subsong, output_path)

    def subsong_temp_path(self, filepath: str, subsong: int) -> str:
        return self.service_facade.subsong_temp_path(filepath, subsong)

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
        return await self.service_facade.play_subsong(
            ctx,
            state,
            subsong,
            audacious_stop=audacious_stop,
            audacious_play=audacious_play,
            setup_monitor_source=setup_monitor_source,
        )

    def cleanup_subsong_temp_wavs(self, state: PlaylistState) -> None:
        self.service_facade.cleanup_subsong_temp_wavs(state)
