import types
from dataclasses import dataclass


@dataclass(slots=True)
class FakePlaybackCallbacks:
    audacious_song: object = "song"
    audacious_stop: object = "stop"
    is_playing: object = "playing"
    audacious_play: object = "play"
    classify_track_route: object = "route"
    get_shared_session: object = "session"
    prepare_playback_queue: object = "prepare"


@dataclass(slots=True)
class FakeBootstrapCallbacks:
    ensure_audacious: object = "ensure"
    setup_virtual_sink: object = "sink"
    close_shared_session: object = "close_session"
    mod_only: object = "mod_only"
    setup_audacious_sid_config: object = "sid_cfg"


@dataclass(slots=True)
class FakeCollectionCallbacks:
    build_collection_state_update: object = "state_update"
    format_flip_sequence: object = "flip_fmt"
    save_last_collection: object = "save_last"
    set_volume_for_collection: object = "set_volume"


@dataclass(slots=True)
class FakeLibraryCallbacks:
    filter_blacklisted_track_entries: object = "filter_entries"
    load_user_tracks: object = "load_tracks"
    remove_user_track: object = "remove_track"
    toggle_user_track_entry: object = "toggle_track"


class FakeRuntimeTaskInputs:
    def __init__(self):
        self.app_cfg_getter = lambda: types.SimpleNamespace()
        self.component_access = object()
        self.support = types.SimpleNamespace(state="state", logger="logger")
        self.raw_callbacks = types.SimpleNamespace(
            playback=FakePlaybackCallbacks(),
            bootstrap=FakeBootstrapCallbacks(),
        )
        self.facade = types.SimpleNamespace(skip_to_next="skip", stop_all_players="stop_all")
        self.glue = types.SimpleNamespace(pre_download_next="predownload")


class FakeRuntimeCallbackInputs:
    def __init__(self):
        self.runtime_tasks = types.SimpleNamespace(
            monitor_playback="monitor",
            health_watchdog="watchdog",
            fetch_metadata_background="fetch_metadata",
        )
        self.raw_callbacks = types.SimpleNamespace(
            playback=FakePlaybackCallbacks(),
            library=FakeLibraryCallbacks(),
            collection=FakeCollectionCallbacks(),
            bootstrap=FakeBootstrapCallbacks(),
        )
        self.facade = types.SimpleNamespace(
            cleanup_subsong_temp_wavs="cleanup_wavs",
            play_subsong="play_subsong",
            auto_play_after_switch="auto_play",
            stop_all_players="stop_all",
            switch_collection="switch_collection",
            cleanup_orphan_players="cleanup_orphans",
        )
        self.glue = types.SimpleNamespace(
            apply_queue_state="apply_queue",
            build_temp_path="temp_path",
            play_via_audacious="play_via",
            place_track_in_queue="place_track",
            queue_position="queue_pos",
            send_now_playing_embed="now_playing",
        )
        self.initializer_support = types.SimpleNamespace(
            root_dir="/tmp/root",
            logger="logger",
            state="state",
            resources="resources",
        )


def build_runtime_task_inputs():
    return FakeRuntimeTaskInputs()


def build_runtime_callback_inputs():
    return FakeRuntimeCallbackInputs()
