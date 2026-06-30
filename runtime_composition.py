"""Runtime composition helpers for the bot entrypoint."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine

import discord

from archive_catalog import CollectionInfo
from app_services import AppServicesProtocol
from app_state import PlaylistState
from bot_runtime import (
    BootstrapCallbacks,
    BotRuntime,
    CollectionCallbacks,
    LibraryCallbacks,
    PlaybackCallbacks,
    PlaybackCommandCallbacks,
    PlaybackHandlerCallbacks,
    PlaybackSessionCallbacks,
    RuntimeConfig,
    RuntimeState,
)
from collection_service import CollectionArchiveProtocol, CollectionService
from playback_service import PlaybackService
from runtime_protocols import CollectionRuntimeProtocol, ServiceFacadeProtocol, StreamRuntimeProtocol
from bot_dependencies import CommandDecoratorFactory, SearchTracksProtocol

if TYPE_CHECKING:
    from aiohttp import ClientSession


@dataclass(slots=True)
class ComposedRuntime:
    runtime: BotRuntime
    collection_service: CollectionService
    playback_service: PlaybackService


@dataclass(slots=True)
class PlaybackSessionCompositionCallbacks:
    apply_queue_state: Callable[[PlaylistState, dict[str, object]], bool]
    classify_track_route: Callable[..., dict[str, str]]
    clear_predownload_state: Callable[..., None]
    download_sap: Callable[..., Awaitable[str]]
    ensure_tracks: Callable[[PlaylistState], Awaitable[bool]]
    filter_blacklisted: Callable[[list[str], int | str], list[str]]
    get_collection_info: Callable[[str], CollectionInfo]
    load_asma_local_cache: Callable[[], list[str] | None]
    monitor_playback: Callable[..., Coroutine[Any, Any, None]]
    parse_sap_header: Callable[[str], dict[str, str]]
    place_track_in_queue: Callable[[list[str], str], tuple[list[str], int]]
    prepare_playback_queue: Callable[..., dict[str, object]]
    register_np_message: Callable[[int, str, str, str], None]


@dataclass(slots=True)
class PlaybackCommandCompositionCallbacks:
    apply_queue_state: Callable[[PlaylistState, dict[str, object]], bool]
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    clear_predownload_state: Callable[..., None]
    ensure_tracks: Callable[[PlaylistState], Awaitable[bool]]
    fetch_metadata_batch: Callable[..., Awaitable[dict[str, dict[str, str]]]]
    filter_blacklisted: Callable[[list[str], int | str], list[str]]
    get_collection_info: Callable[[str], CollectionInfo]
    is_playing: Callable[[], bool]
    load_snes_cache: Callable[[], list[str] | None]
    load_tracks_for_mode: Callable[[str], Awaitable[list[str] | None]]
    monitor_playback: Callable[..., Coroutine[Any, Any, None]]
    parse_sap_header: Callable[[str], dict[str, str]]
    parse_sid_header: Callable[[bytes], dict[str, str]]
    play_current_track: Callable[[object], Awaitable[bool]]
    prepare_playback_queue: Callable[..., dict[str, object]]
    register_np_message: Callable[[int, str, str, str], None]
    search_tracks: SearchTracksProtocol
    skip_to_next: Callable[[object], Awaitable[None]]


@dataclass(slots=True)
class PlaybackHandlerCompositionCallbacks:
    audacious_play: Callable[[str], None]
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    build_temp_path: Callable[[str], str]
    cleanup_subsong_temp_wavs: Callable[[PlaylistState], None]
    clear_predownload_state: Callable[..., None]
    download_modarchive_module: Callable[..., Awaitable[str]]
    download_sap: Callable[..., Awaitable[str]]
    download_spc_rsn: Callable[..., Awaitable[str | None]]
    get_shared_session: Callable[[], Awaitable[ClientSession]]
    get_subsongs: Callable[[str], list[float]]
    parse_sap_header: Callable[[str], dict[str, str]]
    parse_sid_header: Callable[[bytes], dict[str, str]]
    play_subsong: Callable[..., Awaitable[bool]]
    play_via_audacious: Callable[..., Awaitable[None]]
    queue_position: Callable[[PlaylistState], tuple[int, int]]
    register_np_message: Callable[[int, str, str, str], None]
    resolve_local_path: Callable[[str], str | None]
    send_now_playing_embed: Callable[..., Awaitable[None]]
    set_ym_last_wav_path: Callable[[str | None], None]
    setup_monitor_source: Callable[[object], None]
    ym_cleanup: Callable[[], None]
    ym_to_wav: Callable[[str], str]


@dataclass(slots=True)
class PlaybackCompositionCallbacks:
    session: PlaybackSessionCompositionCallbacks
    command: PlaybackCommandCompositionCallbacks
    handler: PlaybackHandlerCompositionCallbacks


@dataclass(slots=True)
class LibraryCompositionCallbacks:
    ensure_playlist_dir: Callable[[], None]
    filter_blacklisted_track_entries: Callable[[list[dict], dict, int], list[dict]]
    list_playlists: Callable[[], list[dict]]
    load_blacklist: Callable[[], dict]
    load_favorites: Callable[[], dict]
    load_playlist: Callable[[str], dict | None]
    load_user_tracks: Callable[[dict, int | str], list[dict]]
    remove_user_track: Callable[[dict, int | str, str], tuple[dict, bool]]
    save_blacklist: Callable[[dict], None]
    save_favorites: Callable[[dict], None]
    save_playlist: Callable[[str, list[dict], int, str], str]
    toggle_user_track_entry: Callable[[dict, int | str, dict], tuple[dict, bool]]


@dataclass(slots=True)
class CollectionCompositionCallbacks:
    archives: CollectionArchiveProtocol
    auto_play_after_switch: Callable[[object, PlaylistState], Awaitable[None]]
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]]
    flip_sequence_formatter: Callable[[list[str], str], str]
    get_all_cache_counts: Callable[[dict[str, tuple[str, str]]], dict[str, tuple[str, int | str]]]
    load_hvsc_local_cache: Callable[[], list[str] | None]
    save_last_collection: Callable[[str], None]
    set_volume_for_collection: Callable[[str], None]
    stop_all_players: Callable[[], None]
    stop_state_streams: Callable[[PlaylistState], Awaitable[None]]
    switch_collection: Callable[..., Awaitable[bool]]


@dataclass(slots=True)
class BootstrapCompositionCallbacks:
    cleanup_temp_dir: Callable[..., None]
    close_shared_session: Callable[[], Awaitable[None]]
    log_preloaded_cache: Callable[[str, list[str] | None], None]
    logger: logging.Logger
    mod_only: CommandDecoratorFactory
    release_process_lock: Callable[[str], None]
    run_startup_steps: Callable[..., Awaitable[None]]
    save_metadata_cache: Callable[[dict], None]
    schedule_background_tasks: Callable[[list[Callable[[], Awaitable[None]]]], None]


@dataclass(slots=True)
class AppCompositionCallbacks:
    playback: PlaybackCompositionCallbacks
    library: LibraryCompositionCallbacks
    collection: CollectionCompositionCallbacks
    bootstrap: BootstrapCompositionCallbacks


def _build_playback_embed(**kwargs: Any) -> discord.Embed:
    return discord.Embed(color=discord.Color.purple(), **kwargs)


def build_playback_callbacks(playback: PlaybackCompositionCallbacks) -> PlaybackCallbacks:
    return PlaybackCallbacks(
        session=PlaybackSessionCallbacks(
            apply_queue_state=playback.session.apply_queue_state,
            classify_track_route=playback.session.classify_track_route,
            clear_predownload_state=playback.session.clear_predownload_state,
            download_sap=playback.session.download_sap,
            embed_factory=_build_playback_embed,
            ensure_tracks=playback.session.ensure_tracks,
            filter_blacklisted=playback.session.filter_blacklisted,
            get_collection_info=playback.session.get_collection_info,
            load_asma_local_cache=playback.session.load_asma_local_cache,
            monitor_playback=playback.session.monitor_playback,
            parse_sap_header=playback.session.parse_sap_header,
            place_track_in_queue=playback.session.place_track_in_queue,
            prepare_playback_queue=playback.session.prepare_playback_queue,
            register_np_message=playback.session.register_np_message,
        ),
        command=PlaybackCommandCallbacks(
            apply_queue_state=playback.command.apply_queue_state,
            audacious_song=playback.command.audacious_song,
            audacious_stop=playback.command.audacious_stop,
            clear_predownload_state=playback.command.clear_predownload_state,
            ensure_tracks=playback.command.ensure_tracks,
            fetch_metadata_batch=playback.command.fetch_metadata_batch,
            filter_blacklisted=playback.command.filter_blacklisted,
            get_collection_info=playback.command.get_collection_info,
            is_playing=playback.command.is_playing,
            load_snes_cache=playback.command.load_snes_cache,
            load_tracks_for_mode=playback.command.load_tracks_for_mode,
            monitor_playback=playback.command.monitor_playback,
            parse_sap_header=playback.command.parse_sap_header,
            parse_sid_header=playback.command.parse_sid_header,
            play_current_track=playback.command.play_current_track,
            prepare_playback_queue=playback.command.prepare_playback_queue,
            register_np_message=playback.command.register_np_message,
            search_tracks=playback.command.search_tracks,
            skip_to_next=playback.command.skip_to_next,
        ),
        handler=PlaybackHandlerCallbacks(
            audacious_play=playback.handler.audacious_play,
            audacious_song=playback.handler.audacious_song,
            audacious_stop=playback.handler.audacious_stop,
            build_temp_path=playback.handler.build_temp_path,
            cleanup_subsong_temp_wavs=playback.handler.cleanup_subsong_temp_wavs,
            clear_predownload_state=playback.handler.clear_predownload_state,
            download_modarchive_module=playback.handler.download_modarchive_module,
            download_sap=playback.handler.download_sap,
            download_spc_rsn=playback.handler.download_spc_rsn,
            get_shared_session=playback.handler.get_shared_session,
            get_subsongs=playback.handler.get_subsongs,
            parse_sap_header=playback.handler.parse_sap_header,
            parse_sid_header=playback.handler.parse_sid_header,
            play_via_audacious=playback.handler.play_via_audacious,
            queue_position=playback.handler.queue_position,
            register_np_message=playback.handler.register_np_message,
            resolve_local_path=playback.handler.resolve_local_path,
            send_now_playing_embed=playback.handler.send_now_playing_embed,
            set_ym_last_wav_path=playback.handler.set_ym_last_wav_path,
            setup_monitor_source=playback.handler.setup_monitor_source,
            ym_cleanup=playback.handler.ym_cleanup,
            ym_to_wav=playback.handler.ym_to_wav,
        ),
    )


def compose_runtime(
    *,
    config: RuntimeConfig,
    state: RuntimeState,
    app_callbacks: AppCompositionCallbacks,
) -> ComposedRuntime:
    runtime = BotRuntime(
        config=config,
        state=state,
        playback=build_playback_callbacks(app_callbacks.playback),
        library=LibraryCallbacks(
            ensure_playlist_dir=app_callbacks.library.ensure_playlist_dir,
            filter_blacklisted_track_entries=app_callbacks.library.filter_blacklisted_track_entries,
            list_playlists=app_callbacks.library.list_playlists,
            load_blacklist=app_callbacks.library.load_blacklist,
            load_favorites=app_callbacks.library.load_favorites,
            load_playlist=app_callbacks.library.load_playlist,
            load_user_tracks=app_callbacks.library.load_user_tracks,
            remove_user_track=app_callbacks.library.remove_user_track,
            save_blacklist=app_callbacks.library.save_blacklist,
            save_favorites=app_callbacks.library.save_favorites,
            save_playlist=app_callbacks.library.save_playlist,
            toggle_user_track_entry=app_callbacks.library.toggle_user_track_entry,
        ),
        collection=CollectionCallbacks(
            auto_play_after_switch=app_callbacks.collection.auto_play_after_switch,
            build_collection_state_update=app_callbacks.collection.build_collection_state_update,
            flip_sequence_formatter=app_callbacks.collection.flip_sequence_formatter,
            get_all_cache_counts=app_callbacks.collection.get_all_cache_counts,
            load_hvsc_local_cache=app_callbacks.collection.load_hvsc_local_cache,
            save_last_collection=app_callbacks.collection.save_last_collection,
            set_volume_for_collection=app_callbacks.collection.set_volume_for_collection,
            stop_all_players=app_callbacks.collection.stop_all_players,
            stop_state_streams=app_callbacks.collection.stop_state_streams,
            switch_collection=app_callbacks.collection.switch_collection,
        ),
        bootstrap=BootstrapCallbacks(
            cleanup_temp_dir=app_callbacks.bootstrap.cleanup_temp_dir,
            close_shared_session=app_callbacks.bootstrap.close_shared_session,
            log_preloaded_cache=app_callbacks.bootstrap.log_preloaded_cache,
            logger=app_callbacks.bootstrap.logger,
            mod_only=app_callbacks.bootstrap.mod_only,
            release_process_lock=app_callbacks.bootstrap.release_process_lock,
            run_startup_steps=app_callbacks.bootstrap.run_startup_steps,
            save_metadata_cache=app_callbacks.bootstrap.save_metadata_cache,
            schedule_background_tasks=app_callbacks.bootstrap.schedule_background_tasks,
        ),
    )
    collection_service = runtime.build_collection_service(
        app_callbacks.collection.archives,
        status_count_cache=state.status_count_cache,
    )
    playback_service = PlaybackService(
        runtime=runtime,
        bot=state.bot,
        play_subsong=app_callbacks.playback.handler.play_subsong,
        cleanup_subsong_temp_wavs=app_callbacks.playback.handler.cleanup_subsong_temp_wavs,
    )
    return ComposedRuntime(
        runtime=runtime,
        collection_service=collection_service,
        playback_service=playback_service,
    )
