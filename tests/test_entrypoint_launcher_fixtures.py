import types


def _build_fake_runtime_exports():
    return types.SimpleNamespace(
        after_stream_end=lambda guild_id, error, source_id=0: (guild_id, error, source_id),
        monitor_playback=lambda: "monitor",
        fetch_metadata_background=lambda: "metadata",
        health_watchdog=lambda: "watchdog",
    )


def build_fake_launcher_module(
    *,
    runtime_app,
    init_calls,
    compat_calls,
    bot_calls,
):
    service_facade = types.SimpleNamespace(
        switch_collection=lambda ctx, mode, *, flip_seq=None: (ctx, mode, flip_seq),
        cleanup_subsong_temp_wavs=lambda: "cleanup_wavs",
    )
    legacy = types.SimpleNamespace(
        skip_to_next=lambda: "skip",
        cleanup_orphan_players=lambda: "cleanup",
        stop_all_players=lambda: "stop",
        auto_play_after_switch=lambda: "auto",
        play_subsong=lambda: "subsong",
    )
    runtime_initializer = types.SimpleNamespace(
        initialize_runtime=lambda: init_calls.append("init") or runtime_app
    )
    runtime_exports = _build_fake_runtime_exports()
    fake_app = types.SimpleNamespace(
        runtime_initializer=runtime_initializer,
        compat=types.SimpleNamespace(
            resolve=lambda name: compat_calls.append(name) or f"resolved:{name}"
        ),
    )
    return types.SimpleNamespace(
        support=types.SimpleNamespace(
            root_dir="/tmp/root",
            logger=types.SimpleNamespace(),
            session_runtime=types.SimpleNamespace(
                get_shared_session=lambda: None,
                close_shared_session=lambda: None,
            ),
            boot=types.SimpleNamespace(),
            state=types.SimpleNamespace(
                app=None,
                startup_env=None,
                legacy=legacy,
                service_facade=service_facade,
            ),
            resources=types.SimpleNamespace(
                app_cfg=lambda: types.SimpleNamespace(bot_token="cfg-token"),
                archive_runtime_config=lambda: types.SimpleNamespace(),
                setup_virtual_sink=lambda: None,
                ensure_audacious=lambda: None,
                setup_audacious_sid_config=lambda: None,
                set_volume_for_collection=lambda _mode: None,
                move_playback_to_sink=lambda: None,
                audacious_play=lambda _path: None,
                audacious_stop=lambda: None,
                audacious_song=lambda: "",
                is_playing=lambda: False,
                command_prefix=lambda _bot, _message: "!",
            ),
            guild_scope=types.SimpleNamespace(),
        ),
        bot=types.SimpleNamespace(
            ping=lambda: bot_calls.append("ping") or "pong",
        ),
        app=fake_app,
        single_guild_check=lambda _ctx: True,
        guild_id_getter=lambda: None,
        guild_id_setter=lambda _guild_id: None,
        status_count_cache={},
        exports={
            "_switch_collection": lambda ctx, mode, *, flip_seq=None: (ctx, mode, flip_seq),
            "_after_stream_end": runtime_exports.after_stream_end,
            "monitor_playback": runtime_exports.monitor_playback,
            "fetch_metadata_background": runtime_exports.fetch_metadata_background,
            "health_watchdog": runtime_exports.health_watchdog,
        },
    )
