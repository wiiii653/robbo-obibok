import types

from entrypoint_module import (
    EntrypointModuleCollectionDeps,
    EntrypointModuleDeps,
    EntrypointModuleRuntimeDeps,
)


def build_fake_module_deps():
    return EntrypointModuleDeps(
        runtime=EntrypointModuleRuntimeDeps(
            build_playback_handlers=lambda *_args, **_kwargs: None,
            register_core_events=lambda *_args, **_kwargs: None,
            register_playback_commands=lambda *_args, **_kwargs: None,
            register_library_commands=lambda *_args, **_kwargs: None,
            validate_runtime_dependencies=lambda: [],
            classify_track_route=lambda *_args, **_kwargs: {},
            compute_timeout_seconds=lambda *_args, **_kwargs: 0,
            is_gme_format_path=lambda _path: False,
            should_advance_after_stop=lambda *_args, **_kwargs: (False, None),
            should_confirm_output_drop=lambda *_args, **_kwargs: (False, None),
            should_disconnect_for_empty_channel=lambda *_args, **_kwargs: (False, None),
            should_force_timeout_stop=lambda *_args, **_kwargs: False,
            should_start_predownload=lambda *_args, **_kwargs: False,
            mod_only=lambda: None,
        ),
        collection=EntrypointModuleCollectionDeps(
            build_collection_state_update=lambda mode, tracks: {
                "collection_mode": mode,
                "loaded_collection": mode,
                "tracks": tracks,
                "queue": tracks,
                "index": 0,
            },
            format_flip_sequence=lambda *_args, **_kwargs: "",
            prepare_playback_queue=lambda *_args, **_kwargs: {},
            remove_user_track=lambda *_args, **_kwargs: None,
            filter_blacklisted_track_entries=lambda *_args, **_kwargs: [],
            filter_blacklisted_track_urls=lambda *_args, **_kwargs: [],
            load_user_tracks=lambda *_args, **_kwargs: [],
            toggle_user_track_entry=lambda *_args, **_kwargs: None,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        ),
    )


def build_fake_module_support():
    return types.SimpleNamespace(
        root_dir="/tmp/root",
        logger=types.SimpleNamespace(),
        session_runtime=types.SimpleNamespace(
            get_shared_session=lambda: None,
            close_shared_session=lambda: None,
        ),
        boot=types.SimpleNamespace(),
        state=types.SimpleNamespace(
            service_facade=types.SimpleNamespace(cleanup_subsong_temp_wavs=lambda _state: None)
        ),
        resources=types.SimpleNamespace(
            app_cfg=lambda: types.SimpleNamespace(guild_id=123, sink_name="sink"),
            config=lambda: {"audio": {"format": "f32le", "sample_rate": 48000, "channels": 2}},
            archive_runtime_config=lambda: types.SimpleNamespace(),
            get_subsongs_runtime=lambda: types.SimpleNamespace(),
            build_temp_path=lambda url: f"/tmp/{url}",
            audacious_play=lambda _path: None,
            audacious_stop=lambda: None,
            audacious_song=lambda: "",
            is_playing=lambda: False,
            set_volume_for_collection=lambda _mode: None,
            setup_virtual_sink=lambda: None,
            ensure_audacious=lambda: None,
            setup_audacious_sid_config=lambda: None,
            command_prefix=lambda _bot, _message: "!",
        ),
        guild_scope=types.SimpleNamespace(
            resolve=lambda guild_id: guild_id,
            set_override=lambda _guild_id: None,
            get_override=lambda: None,
        ),
    )


def build_fake_module_bootstrap(*, support):
    return types.SimpleNamespace(
        support=support,
        bot=types.SimpleNamespace(check=lambda func: func),
        single_guild_check=lambda _ctx: True,
        guild_id_getter=lambda: None,
        guild_id_setter=lambda _guild_id: None,
        status_count_cache={},
        clear_predownload_state=lambda _state, keep_file=False: None,
    )
