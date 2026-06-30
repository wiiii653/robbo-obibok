"""Entrypoint runtime assembly helpers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable, Mapping

from boot_runtime import StartupEnvironment, initialize_startup_environment
from bot_dependencies import PlaybackHandlerDependencies
from bot_runtime import RuntimeConfig, RuntimeState
from app_services import AppServicesProtocol
from collection_specs import CollectionSpec
from collection_service import CollectionArchiveProtocol
from entrypoint_callback_groups import AppEntrypointCallbacks
from playback_assets import PlaybackAssetRuntime
from runtime_bootstrap import (
    acquire_process_lock,
    cleanup_temp_dir,
    log_preloaded_cache,
    release_process_lock,
    run_startup_steps,
    schedule_background_tasks,
)
from runtime_callback_builders import (
    build_bootstrap_composition_callbacks,
    build_collection_composition_callbacks,
    build_library_composition_callbacks,
    build_playback_composition_callbacks,
)
from runtime_composition import AppCompositionCallbacks
from runtime_protocols import (
    ArchiveRuntimeProtocol,
    CollectionRuntimeProtocol,
    PlaybackRuntimeProtocol,
    ServiceFacadeProtocol,
    StreamRuntimeProtocol,
)
from runtime_service_facade import RuntimeServiceFacade
from runtime_registration import RuntimeRegistration, build_registered_runtime

if TYPE_CHECKING:
    from discord.ext import commands
    from stream_runtime import MonitorAudioSource


@dataclass(slots=True)
class AppAssembly:
    startup_env: StartupEnvironment
    runtime_registration: RuntimeRegistration
    collection_service: CollectionRuntimeProtocol
    playback_service: PlaybackRuntimeProtocol


def build_startup_env(
    *,
    bot_token: str | None,
    root_dir: str,
    validate_runtime_dependencies: Callable[[], None],
) -> StartupEnvironment:
    return initialize_startup_environment(
        bot_token=bot_token,
        root_dir=root_dir,
        validate_runtime_dependencies=validate_runtime_dependencies,
        acquire_process_lock=acquire_process_lock,
        process_name="robbo-obibok.py",
    )


def build_runtime_config(
    *,
    asma_base: str,
    asma_dir: str,
    auto_start_channel: str | None,
    ay_dir: str,
    flip_order: list[str],
    flip_seq: list[str],
    hvsc_dir: str,
    lock_file: str,
    playback_loop: bool,
    playback_shuffle: bool,
    playlist_dir: str,
    root_dir: str,
    sink_name: str,
    temp_dir: str,
    tiny_dir: str,
    ym_dir: str,
) -> RuntimeConfig:
    return RuntimeConfig(
        ASMA_BASE=asma_base,
        ASMA_DIR=asma_dir,
        AUTO_START_CHANNEL=auto_start_channel,
        AY_DIR=ay_dir,
        FLIP_ORDER=flip_order,
        FLIP_SEQ=flip_seq,
        HVSC_DIR=hvsc_dir,
        LOCK_FILE=lock_file,
        PLAYBACK_LOOP=playback_loop,
        PLAYBACK_SHUFFLE=playback_shuffle,
        PLAYLIST_DIR=playlist_dir,
        ROOT_DIR=root_dir,
        SINK_NAME=sink_name,
        TEMP_DIR=temp_dir,
        TINY_DIR=tiny_dir,
        YM_DIR=ym_dir,
    )


def build_runtime_state(
    *,
    active_streams: dict[int, MonitorAudioSource],
    app_services: AppServicesProtocol,
    bot: commands.Bot,
    collections: dict[str, CollectionSpec],
    metadata_index: dict[str, dict[str, str]],
    modarchive_name_map: Mapping[str, str],
    shutdown_flag: asyncio.Event,
    snes_metadata: Mapping[str, dict[str, object]],
    status_count_cache: dict[str, tuple[float, int | str]],
) -> RuntimeState:
    return RuntimeState(
        active_streams=active_streams,
        app_services=app_services,
        bot=bot,
        collections=collections,
        metadata_index=metadata_index,
        modarchive_name_map=modarchive_name_map,
        shutdown_flag=shutdown_flag,
        snes_metadata=snes_metadata,
        status_count_cache=status_count_cache,
    )


def build_app_callbacks(
    *,
    app_services: AppServicesProtocol,
    archive_runtime: ArchiveRuntimeProtocol,
    playback_assets: PlaybackAssetRuntime,
    service_facade: RuntimeServiceFacade,
    stream_runtime: StreamRuntimeProtocol,
    callbacks: AppEntrypointCallbacks,
    set_ym_last_wav_path: Callable[[str | None], None],
    archives: CollectionArchiveProtocol,
    last_collection_file: str,
    logger: logging.Logger,
    loop: asyncio.AbstractEventLoop,
) -> AppCompositionCallbacks:
    return AppCompositionCallbacks(
        playback=build_playback_composition_callbacks(
            archive_runtime=archive_runtime,
            playback_assets=playback_assets,
            service_facade=service_facade,
            stream_runtime=stream_runtime,
            app_services=app_services,
            apply_queue_state=callbacks.playback.apply_queue_state,
            audacious_play=callbacks.playback.audacious_play,
            audacious_song=callbacks.playback.audacious_song,
            audacious_stop=callbacks.playback.audacious_stop,
            build_temp_path=callbacks.playback.build_temp_path,
            classify_track_route=callbacks.playback.classify_track_route,
            clear_predownload_state=callbacks.playback.clear_predownload_state,
            cleanup_subsong_temp_wavs=callbacks.playback.cleanup_subsong_temp_wavs,
            get_shared_session=callbacks.playback.get_shared_session,
            is_playing=callbacks.playback.is_playing,
            monitor_playback=callbacks.playback.monitor_playback,
            play_subsong=callbacks.playback.play_subsong,
            play_via_audacious=callbacks.playback.play_via_audacious,
            place_track_in_queue=callbacks.playback.place_track_in_queue,
            prepare_playback_queue=callbacks.playback.prepare_playback_queue,
            queue_position=callbacks.playback.queue_position,
            send_now_playing_embed=callbacks.playback.send_now_playing_embed,
            set_ym_last_wav_path=set_ym_last_wav_path,
        ),
        library=build_library_composition_callbacks(
            app_services=app_services,
            filter_blacklisted_track_entries=callbacks.library.filter_blacklisted_track_entries,
            load_user_tracks=callbacks.library.load_user_tracks,
            remove_user_track=callbacks.library.remove_user_track,
            toggle_user_track_entry=callbacks.library.toggle_user_track_entry,
        ),
        collection=build_collection_composition_callbacks(
            archives=archives,
            archive_runtime=archive_runtime,
            service_facade=service_facade,
            stream_runtime=stream_runtime,
            auto_play_after_switch=callbacks.collection.auto_play_after_switch,
            build_collection_state_update=callbacks.collection.build_collection_state_update,
            flip_sequence_formatter=callbacks.collection.format_flip_sequence,
            save_last_collection=lambda mode: callbacks.collection.save_last_collection(last_collection_file, mode),
            set_volume_for_collection=callbacks.collection.set_volume_for_collection,
            stop_all_players=callbacks.collection.stop_all_players,
            switch_collection=callbacks.collection.switch_collection,
        ),
        bootstrap=build_bootstrap_composition_callbacks(
            archive_runtime=archive_runtime,
            cleanup_temp_dir=cleanup_temp_dir,
            close_shared_session=callbacks.bootstrap.close_shared_session,
            log_preloaded_cache=lambda label, tracks: log_preloaded_cache(label, tracks, logger=logger),
            logger=logger,
            mod_only=callbacks.bootstrap.mod_only,
            release_process_lock=release_process_lock,
            run_startup_steps=lambda: run_startup_steps(
                [
                    ("cleanup_orphan_players", callbacks.bootstrap.cleanup_orphan_players),
                    ("setup_virtual_sink", callbacks.bootstrap.setup_virtual_sink),
                    ("ensure_audacious", callbacks.bootstrap.ensure_audacious),
                    ("setup_audacious_sid_config", callbacks.bootstrap.setup_audacious_sid_config),
                ],
                logger=logger,
            ),
            schedule_background_tasks=lambda tasks: schedule_background_tasks(tasks, loop=loop),
        ),
    )


def create_app(
    *,
    startup_env: StartupEnvironment,
    config: RuntimeConfig,
    state: RuntimeState,
    app_callbacks: AppCompositionCallbacks,
    bot: commands.Bot,
    build_playback_handlers: Callable[[PlaybackHandlerDependencies], dict[str, Callable[..., Awaitable[bool]]]],
    register_core_events: Callable[..., None],
    register_playback_commands: Callable[..., None],
    register_library_commands: Callable[..., None],
    health_watchdog: Callable[[], Awaitable[None]],
    fetch_metadata_background: Callable[[], Awaitable[None]],
    service_facade: ServiceFacadeProtocol,
) -> AppAssembly:
    runtime_registration = build_registered_runtime(
        config=config,
        state=state,
        app_callbacks=app_callbacks,
        bot=bot,
        build_playback_handlers=build_playback_handlers,
        register_core_events=register_core_events,
        register_playback_commands=register_playback_commands,
        register_library_commands=register_library_commands,
        health_watchdog=health_watchdog,
        fetch_metadata_background=fetch_metadata_background,
    )
    composed = runtime_registration.composed
    service_facade.bind(
        collection_service=composed.collection_service,
        playback_service=composed.playback_service,
    )
    return AppAssembly(
        startup_env=startup_env,
        runtime_registration=runtime_registration,
        collection_service=composed.collection_service,
        playback_service=composed.playback_service,
    )
