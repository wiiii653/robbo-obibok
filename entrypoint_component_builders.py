"""Narrow builders for entrypoint component assembly."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from app_services import AppServicesProtocol
from archive_catalog import ArchiveCatalog
from archive_runtime import ArchiveRuntime
from archive_runtime import ArchiveRuntimeConfig
from collection_catalog import build_collections
from playback_assets import PlaybackAssetRuntime
from playback_helpers import NowPlayingDependencies
from runtime_protocols import SubsongRuntimeProtocol
from runtime_service_facade import RuntimeServiceFacade
from stream_runtime import StreamRuntime

if TYPE_CHECKING:
    from aiohttp import ClientSession


def _build_now_playing_embed(**kwargs):
    import discord

    return discord.Embed(**kwargs)


def build_service_facade(
    *,
    app_services: AppServicesProtocol,
    blacklist_filter: Callable[[list[str], dict, int | str], list[str]],
    logger: logging.Logger,
    stop_all_players_impl,
    subsongs: SubsongRuntimeProtocol,
) -> RuntimeServiceFacade:
    return RuntimeServiceFacade(
        app_services=app_services,
        blacklist_loader=app_services.load_blacklist,
        blacklist_filter=blacklist_filter,
        logger=logger,
        stop_all_players_impl=stop_all_players_impl,
        subsongs=subsongs,
    )


def build_stream_runtime(
    *,
    sink_name: str,
    audio_format: str,
    sample_rate: int,
    channels: int,
    logger: logging.Logger,
    clear_predownload_state: Callable[..., None],
) -> StreamRuntime:
    return StreamRuntime(
        sink_name=sink_name,
        audio_format=audio_format,
        sample_rate=sample_rate,
        channels=channels,
        logger=logger,
        clear_predownload_state=clear_predownload_state,
    )


def build_archive_runtime(
    *,
    archives: ArchiveCatalog,
    logger: logging.Logger,
    snes_spc_dir: str,
    temp_dir: str,
    build_temp_path: Callable[[str], str],
    get_shared_session: Callable[[], Awaitable[ClientSession]],
    config: ArchiveRuntimeConfig,
) -> ArchiveRuntime:
    return ArchiveRuntime(
        archives=archives,
        logger=logger,
        snes_spc_dir=snes_spc_dir,
        temp_dir=temp_dir,
        build_temp_path=build_temp_path,
        get_shared_session=get_shared_session,
        config=config,
    )


def build_playback_assets(
    *,
    asma_base: str,
    asma_dir: str,
    hvsc_base: str,
    hvsc_dir: str,
    ym_temp_dir: str,
    logger: logging.Logger,
    build_temp_path: Callable[[str], str],
    get_shared_session: Callable[[], Awaitable[ClientSession]],
) -> PlaybackAssetRuntime:
    return PlaybackAssetRuntime(
        asma_base=asma_base,
        asma_dir=asma_dir,
        hvsc_base=hvsc_base,
        hvsc_dir=hvsc_dir,
        ym_temp_dir=ym_temp_dir,
        logger=logger,
        build_temp_path=build_temp_path,
        get_shared_session=get_shared_session,
    )


def build_now_playing_dependencies(
    *,
    audacious_play: Callable[[str], None],
    audacious_stop: Callable[[], None],
    register_np_message: Callable[[int, str, str, str], None],
    setup_monitor_source: Callable[[object], None],
) -> NowPlayingDependencies:
    return NowPlayingDependencies(
        audacious_play=audacious_play,
        audacious_stop=audacious_stop,
        embed_factory=_build_now_playing_embed,
        register_np_message=register_np_message,
        setup_monitor_source=setup_monitor_source,
    )


def build_collection_loaders(
    *,
    archive_runtime: ArchiveRuntime,
):
    return build_collections(
        load_asma_local_cache=archive_runtime.load_asma_local_cache,
        load_hvsc_local_cache=archive_runtime.load_hvsc_local_cache,
        load_modarchive_cache=archive_runtime.load_modarchive_cache,
        load_ay_cache=archive_runtime.load_ay_cache,
        load_ym_cache=archive_runtime.load_ym_cache,
        load_tiny_cache=archive_runtime.load_tiny_cache,
        load_snes_cache=archive_runtime.load_snes_cache,
    )
