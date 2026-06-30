"""Callback-oriented runtime builders for entrypoint app assembly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from bot_dependencies import PlaybackHandlerDependencies, PlaybackHandlerMap

from entrypoint_callback_groups import (
    AppEntrypointCallbacks,
    BootstrapEntrypointCallbacks,
    CollectionEntrypointCallbacks,
    EntrypointRawCallbacks,
    LibraryEntrypointCallbacks,
    PlaybackEntrypointCallbacks,
)
from entrypoint_glue import EntrypointGlue
from entrypoint_runtime_init import EntrypointRuntimeInitializer, RuntimeRegistrationHooks
from entrypoint_runtime_tasks import EntrypointRuntimeTasks

if TYPE_CHECKING:
    from discord.ext import commands
    from entrypoint_app import EntrypointComponentAccess, EntrypointFacade
    from entrypoint_launcher_loader import EntrypointSupport


def build_entrypoint_runtime_callbacks(
    *,
    raw_callbacks: EntrypointRawCallbacks,
    clear_predownload_state: Callable[..., None],
    facade: EntrypointFacade,
    glue: EntrypointGlue,
    runtime_tasks: EntrypointRuntimeTasks,
) -> AppEntrypointCallbacks:
    return AppEntrypointCallbacks(
        playback=PlaybackEntrypointCallbacks(
            apply_queue_state=glue.apply_queue_state,
            audacious_play=raw_callbacks.playback.audacious_play,
            audacious_song=raw_callbacks.playback.audacious_song,
            audacious_stop=raw_callbacks.playback.audacious_stop,
            build_temp_path=glue.build_temp_path,
            classify_track_route=raw_callbacks.playback.classify_track_route,
            clear_predownload_state=clear_predownload_state,
            cleanup_subsong_temp_wavs=facade.cleanup_subsong_temp_wavs,
            get_shared_session=raw_callbacks.playback.get_shared_session,
            is_playing=raw_callbacks.playback.is_playing,
            monitor_playback=runtime_tasks.monitor_playback,
            play_subsong=facade.play_subsong,
            play_via_audacious=glue.play_via_audacious,
            place_track_in_queue=glue.place_track_in_queue,
            prepare_playback_queue=raw_callbacks.playback.prepare_playback_queue,
            queue_position=glue.queue_position,
            send_now_playing_embed=glue.send_now_playing_embed,
        ),
        library=LibraryEntrypointCallbacks(
            filter_blacklisted_track_entries=raw_callbacks.library.filter_blacklisted_track_entries,
            load_user_tracks=raw_callbacks.library.load_user_tracks,
            remove_user_track=raw_callbacks.library.remove_user_track,
            toggle_user_track_entry=raw_callbacks.library.toggle_user_track_entry,
        ),
        collection=CollectionEntrypointCallbacks(
            auto_play_after_switch=facade.auto_play_after_switch,
            build_collection_state_update=raw_callbacks.collection.build_collection_state_update,
            format_flip_sequence=raw_callbacks.collection.format_flip_sequence,
            save_last_collection=raw_callbacks.collection.save_last_collection,
            set_volume_for_collection=raw_callbacks.collection.set_volume_for_collection,
            stop_all_players=facade.stop_all_players,
            switch_collection=facade.switch_collection,
        ),
        bootstrap=BootstrapEntrypointCallbacks(
            close_shared_session=raw_callbacks.bootstrap.close_shared_session,
            mod_only=raw_callbacks.bootstrap.mod_only,
            cleanup_orphan_players=facade.cleanup_orphan_players,
            setup_virtual_sink=raw_callbacks.bootstrap.setup_virtual_sink,
            ensure_audacious=raw_callbacks.bootstrap.ensure_audacious,
            setup_audacious_sid_config=raw_callbacks.bootstrap.setup_audacious_sid_config,
        ),
    )


def build_entrypoint_runtime_initializer(
    *,
    bot: commands.Bot,
    support: EntrypointSupport,
    status_count_cache: dict[str, tuple[float, int | str]],
    flip_order: list[str],
    flip_seq: list[str],
    validate_runtime_dependencies: Callable[[], None],
    component_access: EntrypointComponentAccess,
    build_playback_handlers: Callable[[PlaybackHandlerDependencies], PlaybackHandlerMap],
    register_core_events: Callable[..., None],
    register_playback_commands: Callable[..., None],
    register_library_commands: Callable[..., None],
    runtime_tasks: EntrypointRuntimeTasks,
    runtime_callbacks: AppEntrypointCallbacks,
) -> EntrypointRuntimeInitializer:
    return EntrypointRuntimeInitializer(
        root_dir=support.root_dir,
        logger=support.logger,
        bot=bot,
        state=support.state,
        resources=support.resources,
        status_count_cache=status_count_cache,
        flip_order=flip_order,
        flip_seq=flip_seq,
        validate_runtime_dependencies=validate_runtime_dependencies,
        components=component_access,
        registration_hooks=RuntimeRegistrationHooks(
            build_playback_handlers=build_playback_handlers,
            register_core_events=register_core_events,
            register_playback_commands=register_playback_commands,
            register_library_commands=register_library_commands,
            health_watchdog=runtime_tasks.health_watchdog,
            fetch_metadata_background=runtime_tasks.fetch_metadata_background,
        ),
        callbacks=runtime_callbacks,
    )
