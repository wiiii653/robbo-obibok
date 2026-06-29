"""Helper builders for entrypoint module bootstrap."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from app_state import PlaylistState
from entrypoint_callback_groups import (
    BootstrapStaticCallbacks,
    CollectionStaticCallbacks,
    EntrypointRawCallbacks,
    LibraryStaticCallbacks,
    PlaybackStaticCallbacks,
)
from entrypoint_components import EntrypointComponentDeps
from entrypoint_legacy import build_legacy_bindings
from playback_process import stop_all_players as runtime_stop_all_players

if TYPE_CHECKING:
    from entrypoint_launcher_support import EntrypointSupport


def build_module_component_deps(
    *,
    support: EntrypointSupport,
    clear_predownload_state: Callable[..., None],
    filter_blacklisted_track_urls: Callable[[list[str], int | str], list[str]],
) -> Callable[[], EntrypointComponentDeps]:
    def component_deps() -> EntrypointComponentDeps:
        return EntrypointComponentDeps(
            boot_builder=support.boot,
            logger=support.logger,
            sink_name=support.resources.app_cfg().sink_name,
            audio_format=support.resources.config()["audio"]["format"],
            sample_rate=support.resources.config()["audio"]["sample_rate"],
            channels=support.resources.config()["audio"]["channels"],
            temp_dir=support.resources.app_cfg().temp_dir,
            archive_runtime_config=support.resources.archive_runtime_config(),
            subsongs=support.resources.get_subsongs_runtime(),
            build_temp_path=support.resources.build_temp_path,
            get_shared_session=support.session_runtime.get_shared_session,
            clear_predownload_state=lambda state: clear_predownload_state(state),
            blacklist_filter=filter_blacklisted_track_urls,
            stop_all_players_impl=runtime_stop_all_players,
            audacious_play=support.resources.audacious_play,
            audacious_stop=support.resources.audacious_stop,
            cleanup_subsong_temp_wavs_impl=lambda state: support.state.service_facade.cleanup_subsong_temp_wavs(state),
            build_legacy_bindings=build_legacy_bindings,
        )

    return component_deps


def build_module_raw_callbacks(
    *,
    support: EntrypointSupport,
    clear_predownload_state: Callable[..., None],
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]],
    classify_track_route: Callable[..., dict[str, str]],
    format_flip_sequence: Callable[[list[str], str], str],
    prepare_playback_queue: Callable[..., dict[str, object]],
    save_last_collection: Callable[[str, str], None],
    set_volume_for_collection: Callable[[str], None],
    filter_blacklisted_track_entries: Callable[[list[dict], dict, int], list[dict]],
    load_user_tracks: Callable[[dict, int | str], list[dict]],
    remove_user_track: Callable[[dict, int | str, str], tuple[dict, bool]],
    toggle_user_track_entry: Callable[[dict, int | str, dict], tuple[dict, bool]],
    mod_only: Callable[[], object],
) -> EntrypointRawCallbacks:
    return EntrypointRawCallbacks(
        playback=PlaybackStaticCallbacks(
            audacious_play=support.resources.audacious_play,
            audacious_song=support.resources.audacious_song,
            audacious_stop=support.resources.audacious_stop,
            classify_track_route=classify_track_route,
            clear_predownload_state=lambda state, *, keep_file=False: clear_predownload_state(state, keep_file=keep_file),
            get_shared_session=support.session_runtime.get_shared_session,
            is_playing=support.resources.is_playing,
            prepare_playback_queue=prepare_playback_queue,
        ),
        library=LibraryStaticCallbacks(
            filter_blacklisted_track_entries=filter_blacklisted_track_entries,
            load_user_tracks=load_user_tracks,
            remove_user_track=remove_user_track,
            toggle_user_track_entry=toggle_user_track_entry,
        ),
        collection=CollectionStaticCallbacks(
            build_collection_state_update=build_collection_state_update,
            format_flip_sequence=format_flip_sequence,
            save_last_collection=save_last_collection,
            set_volume_for_collection=set_volume_for_collection,
        ),
        bootstrap=BootstrapStaticCallbacks(
            close_shared_session=support.session_runtime.close_shared_session,
            mod_only=mod_only,
            setup_virtual_sink=support.resources.setup_virtual_sink,
            ensure_audacious=support.resources.ensure_audacious,
            setup_audacious_sid_config=support.resources.setup_audacious_sid_config,
        ),
    )
