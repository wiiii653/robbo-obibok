"""Builders for entrypoint callback bundles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine

from bot_dependencies import CommandDecoratorFactory
from collection_service import CollectionArchiveProtocol
from domain_services import AppServicesProtocol
from domain_state import PlaylistState
from runtime_composition import (
    BootstrapCompositionCallbacks,
    CollectionCompositionCallbacks,
    LibraryCompositionCallbacks,
    PlaybackCommandCompositionCallbacks,
    PlaybackCompositionCallbacks,
    PlaybackHandlerCompositionCallbacks,
    PlaybackSessionCompositionCallbacks,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession
from runtime_protocols import (
    ArchiveRuntimeProtocol,
    PlaybackAssetsProtocol,
    PlaySubsongCallable,
    ServiceFacadeProtocol,
    StreamRuntimeProtocol,
)


def build_playback_composition_callbacks(
    *,
    archive_runtime: ArchiveRuntimeProtocol,
    playback_assets: PlaybackAssetsProtocol,
    service_facade: ServiceFacadeProtocol,
    stream_runtime: StreamRuntimeProtocol,
    app_services: AppServicesProtocol,
    apply_queue_state: Callable[[PlaylistState, dict[str, object]], bool],
    audacious_play: Callable[[str], None],
    audacious_song: Callable[[], str],
    audacious_stop: Callable[[], None],
    build_temp_path: Callable[[str], str],
    classify_track_route: Callable[..., dict[str, str]],
    clear_predownload_state: Callable[..., None],
    cleanup_subsong_temp_wavs: Callable[[PlaylistState], None],
    get_shared_session: Callable[[], Awaitable[ClientSession]],
    is_playing: Callable[[], bool],
    monitor_playback: Callable[..., Coroutine[Any, Any, None]],
    play_subsong: PlaySubsongCallable,
    play_via_audacious: Callable[..., Awaitable[None]],
    place_track_in_queue: Callable[[list[str], str], tuple[list[str], int]],
    prepare_playback_queue: Callable[..., dict[str, object]],
    queue_position: Callable[[PlaylistState], tuple[int, int]],
    send_now_playing_embed: Callable[..., Awaitable[None]],
    set_ym_last_wav_path: Callable[[str | None], None],
) -> PlaybackCompositionCallbacks:
    return PlaybackCompositionCallbacks(
        session=PlaybackSessionCompositionCallbacks(
            apply_queue_state=apply_queue_state,
            classify_track_route=classify_track_route,
            clear_predownload_state=clear_predownload_state,
            download_sap=playback_assets.download_sap,
            ensure_tracks=service_facade.ensure_tracks,
            filter_blacklisted=service_facade.filter_blacklisted,
            get_collection_info=service_facade.get_collection_info,
            load_asma_local_cache=archive_runtime.load_asma_local_cache,
            monitor_playback=monitor_playback,
            parse_sap_header=archive_runtime.parse_sap_header,
            place_track_in_queue=place_track_in_queue,
            prepare_playback_queue=prepare_playback_queue,
            register_np_message=app_services.register_now_playing_message,
        ),
        command=PlaybackCommandCompositionCallbacks(
            apply_queue_state=apply_queue_state,
            audacious_song=audacious_song,
            audacious_stop=audacious_stop,
            clear_predownload_state=clear_predownload_state,
            ensure_tracks=service_facade.ensure_tracks,
            fetch_metadata_batch=archive_runtime.fetch_metadata_batch,
            filter_blacklisted=service_facade.filter_blacklisted,
            get_collection_info=service_facade.get_collection_info,
            is_playing=is_playing,
            load_snes_cache=archive_runtime.load_snes_cache,
            load_tracks_for_mode=service_facade.load_tracks_for_mode,
            monitor_playback=monitor_playback,
            parse_sap_header=archive_runtime.parse_sap_header,
            parse_sid_header=archive_runtime.parse_sid_header,
            play_current_track=service_facade.play_current_track,
            prepare_playback_queue=prepare_playback_queue,
            register_np_message=app_services.register_now_playing_message,
            search_tracks=archive_runtime.search_tracks,
            skip_to_next=service_facade.skip_to_next,
        ),
        handler=PlaybackHandlerCompositionCallbacks(
            audacious_play=audacious_play,
            audacious_song=audacious_song,
            audacious_stop=audacious_stop,
            build_temp_path=build_temp_path,
            cleanup_subsong_temp_wavs=cleanup_subsong_temp_wavs,
            clear_predownload_state=clear_predownload_state,
            download_modarchive_module=archive_runtime.download_modarchive_module,
            download_sap=playback_assets.download_sap,
            download_spc_rsn=archive_runtime.download_spc_rsn,
            get_shared_session=get_shared_session,
            get_subsongs=service_facade.get_subsongs,
            parse_sap_header=archive_runtime.parse_sap_header,
            parse_sid_header=archive_runtime.parse_sid_header,
            play_subsong=play_subsong,
            play_via_audacious=play_via_audacious,
            queue_position=queue_position,
            register_np_message=app_services.register_now_playing_message,
            resolve_local_path=playback_assets.resolve_local_path,
            send_now_playing_embed=send_now_playing_embed,
            set_ym_last_wav_path=set_ym_last_wav_path,
            setup_monitor_source=stream_runtime.setup_monitor_source,
            ym_cleanup=playback_assets.ym_cleanup,
            ym_to_wav=playback_assets.ym_to_wav,
        ),
    )


def build_library_composition_callbacks(
    *,
    app_services: AppServicesProtocol,
    filter_blacklisted_track_entries: Callable[[list[dict], dict, int], list[dict]],
    load_user_tracks: Callable[[dict, int | str], list[dict]],
    remove_user_track: Callable[[dict, int | str, str], tuple[dict, bool]],
    toggle_user_track_entry: Callable[[dict, int | str, dict], tuple[dict, bool]],
) -> LibraryCompositionCallbacks:
    return LibraryCompositionCallbacks(
        ensure_playlist_dir=app_services.ensure_playlist_dir,
        filter_blacklisted_track_entries=filter_blacklisted_track_entries,
        list_playlists=app_services.list_playlists,
        load_blacklist=app_services.load_blacklist,
        load_favorites=app_services.load_favorites,
        load_playlist=app_services.load_playlist,
        load_user_tracks=load_user_tracks,
        remove_user_track=remove_user_track,
        save_blacklist=app_services.save_blacklist,
        save_favorites=app_services.save_favorites,
        save_playlist=app_services.save_playlist,
        toggle_user_track_entry=toggle_user_track_entry,
    )


def build_collection_composition_callbacks(
    *,
    archives: CollectionArchiveProtocol,
    archive_runtime: ArchiveRuntimeProtocol,
    service_facade: ServiceFacadeProtocol,
    stream_runtime: StreamRuntimeProtocol,
    auto_play_after_switch: Callable[[object, PlaylistState], Awaitable[None]],
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]],
    flip_sequence_formatter: Callable[[list[str], str], str],
    save_last_collection: Callable[[str], None],
    set_volume_for_collection: Callable[[str], None],
    stop_all_players: Callable[[], None],
    switch_collection: Callable[..., Awaitable[bool]],
) -> CollectionCompositionCallbacks:
    return CollectionCompositionCallbacks(
        archives=archives,
        auto_play_after_switch=auto_play_after_switch,
        build_collection_state_update=build_collection_state_update,
        flip_sequence_formatter=flip_sequence_formatter,
        get_all_cache_counts=service_facade.get_all_cache_counts,
        load_hvsc_local_cache=archive_runtime.load_hvsc_local_cache,
        save_last_collection=save_last_collection,
        set_volume_for_collection=set_volume_for_collection,
        stop_all_players=stop_all_players,
        stop_state_streams=stream_runtime.stop_state_streams,
        switch_collection=switch_collection,
    )


def build_bootstrap_composition_callbacks(
    *,
    archive_runtime: ArchiveRuntimeProtocol,
    cleanup_temp_dir: Callable[..., None],
    close_shared_session: Callable[[], Awaitable[None]],
    log_preloaded_cache: Callable[[str, list[str] | None], None],
    logger: logging.Logger,
    mod_only: CommandDecoratorFactory,
    release_process_lock: Callable[[str], None],
    run_startup_steps: Callable[..., Awaitable[None]],
    schedule_background_tasks: Callable[[list[Callable[[], Awaitable[None]]]], None],
) -> BootstrapCompositionCallbacks:
    return BootstrapCompositionCallbacks(
        cleanup_temp_dir=cleanup_temp_dir,
        close_shared_session=close_shared_session,
        log_preloaded_cache=log_preloaded_cache,
        logger=logger,
        mod_only=mod_only,
        release_process_lock=release_process_lock,
        run_startup_steps=run_startup_steps,
        save_metadata_cache=archive_runtime.save_metadata_cache,
        schedule_background_tasks=schedule_background_tasks,
    )
