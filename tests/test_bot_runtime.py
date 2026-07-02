import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robbo_obibok import bot_runtime, domain_state


class BotRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_graceful_shutdown_disconnects_clients_and_cleans_streams(self):
        calls = []
        runtime = self._build_runtime(calls)
        state = runtime.state.app_services.get_state(1)
        state.set_guild_id(1)
        runtime.state.app_services.app_state.register_guild_state(1, state)

        class FakeSource:
            def cleanup(self):
                calls.append("source")

        class FakeVoice:
            async def disconnect(self):
                calls.append("voice")

        runtime.state.active_streams = {1: FakeSource()}
        runtime.state.bot.voice_clients = [FakeVoice()]

        await runtime.graceful_shutdown()

        self.assertIn("source", calls)
        self.assertIn("voice", calls)
        self.assertIn("audacious", calls)
        self.assertIn("session", calls)
        self.assertIn("temp", calls)
        self.assertIn("lock", calls)
        self.assertIn("flag", calls)

    def test_handle_signal_schedules_shutdown_and_close(self):
        calls = []
        runtime = self._build_runtime(calls)

        class FakeLoop:
            def is_running(self):
                return True

            def call_soon_threadsafe(self, callback):
                calls.append("call_soon_threadsafe")
                callback()

        async def close_bot():
            return None

        def record_shutdown(coro, _loop):
            calls.append("shutdown")
            coro.close()
            return object()

        def record_future(coro):
            calls.append("ensure_future")
            coro.close()
            return object()

        loop = FakeLoop()
        runtime.state.bot.close = close_bot

        with (
            patch.object(bot_runtime.asyncio, "get_running_loop", return_value=loop),
            patch.object(bot_runtime.asyncio, "run_coroutine_threadsafe", side_effect=record_shutdown),
            patch.object(bot_runtime.asyncio, "ensure_future", side_effect=record_future),
        ):
            runtime.handle_signal(15, None)

        self.assertEqual(calls, ["shutdown", "call_soon_threadsafe", "ensure_future"])

    def _build_runtime(self, calls):
        async def true_async(*_args, **_kwargs):
            return True

        runtime_state = domain_state.AppRuntimeState(
            queue_dir="/tmp/unused",
            default_collection_mode="asma",
            json_writer=lambda *_args, **_kwargs: None,
        )

        return bot_runtime.BotRuntime(
            config=bot_runtime.RuntimeConfig(
                ASMA_BASE="asma",
                ASMA_DIR="asma-dir",
                AUTO_START_CHANNEL="radio",
                AY_DIR="ay-dir",
                FLIP_ORDER=["asma"],
                FLIP_SEQ=["ASMA"],
                HVSC_DIR="hvsc-dir",
                LOCK_FILE="lock.pid",
                PLAYBACK_LOOP=True,
                PLAYBACK_SHUFFLE=True,
                PLAYLIST_DIR="playlists",
                ROOT_DIR="root",
                SINK_NAME="sink",
                TEMP_DIR="tmp",
                TINY_DIR="tiny-dir",
                YM_DIR="ym-dir",
                KGEN_DIR="kgen-dir",
            ),
            state=bot_runtime.RuntimeState(
                active_streams={},
                app_services=types.SimpleNamespace(
                    app_state=runtime_state,
                    get_state=runtime_state.get_state,
                    get_message_track=runtime_state.message_track_map.get,
                    iter_guild_states=runtime_state.guilds.values,
                    load_queue=runtime_state.load_queue,
                    save_queue=runtime_state.save_queue,
                ),
                bot=types.SimpleNamespace(voice_clients=[]),
                collections={},
                metadata_index={},
                modarchive_name_map={},
                shutdown_flag=types.SimpleNamespace(set=lambda: calls.append("flag")),
                snes_metadata={},
                status_count_cache={},
            ),
            playback=bot_runtime.PlaybackCallbacks(
                session=bot_runtime.PlaybackSessionCallbacks(
                    apply_queue_state=lambda *_args, **_kwargs: False,
                    classify_track_route=lambda *_args, **_kwargs: {},
                    clear_predownload_state=lambda *_args, **_kwargs: None,
                    download_sap=true_async,
                    embed_factory=lambda **_kwargs: object(),
                    ensure_tracks=true_async,
                    filter_blacklisted=lambda tracks, _user_id: tracks,
                    get_collection_info=lambda *_args, **_kwargs: object(),
                    load_asma_local_cache=lambda: [],
                    monitor_playback=true_async,
                    parse_sap_header=lambda *_args, **_kwargs: {},
                    place_track_in_queue=lambda queue, _url: (queue, 0),
                    prepare_playback_queue=lambda *_args, **_kwargs: {},
                    register_np_message=lambda *_args, **_kwargs: None,
                ),
                command=bot_runtime.PlaybackCommandCallbacks(
                    apply_queue_state=lambda *_args, **_kwargs: False,
                    audacious_song=lambda: "",
                    audacious_stop=lambda: calls.append("audacious"),
                    clear_predownload_state=lambda *_args, **_kwargs: None,
                    ensure_tracks=true_async,
                    fetch_metadata_batch=true_async,
                    filter_blacklisted=lambda tracks, _user_id: tracks,
                    get_collection_info=lambda *_args, **_kwargs: object(),
                    is_playing=lambda: False,
                    load_snes_cache=lambda: [],
                    load_tracks_for_mode=true_async,
                    monitor_playback=true_async,
                    parse_sap_header=lambda *_args, **_kwargs: {},
                    parse_sid_header=lambda *_args, **_kwargs: {},
                    play_current_track=true_async,
                    prepare_playback_queue=lambda *_args, **_kwargs: {},
                    register_np_message=lambda *_args, **_kwargs: None,
                    search_tracks=lambda *_args, **_kwargs: [],
                    skip_to_next=true_async,
                ),
                handler=bot_runtime.PlaybackHandlerCallbacks(
                    audacious_play=lambda *_args, **_kwargs: None,
                    audacious_song=lambda: "",
                    audacious_stop=lambda: calls.append("audacious"),
                    build_temp_path=lambda url: url,
                    cleanup_subsong_temp_wavs=lambda *_args, **_kwargs: None,
                    clear_predownload_state=lambda *_args, **_kwargs: None,
                    download_modarchive_module=true_async,
                    download_sap=true_async,
                    download_spc_rsn=true_async,
                    get_shared_session=true_async,
                    get_subsongs=lambda *_args, **_kwargs: [],
                    parse_sap_header=lambda *_args, **_kwargs: {},
                    parse_sid_header=lambda *_args, **_kwargs: {},
                    play_via_audacious=true_async,
                    queue_position=lambda *_args, **_kwargs: (1, 1),
                    register_np_message=lambda *_args, **_kwargs: None,
                    resolve_local_path=lambda *_args, **_kwargs: None,
                    send_now_playing_embed=true_async,
                    set_ym_last_wav_path=lambda *_args, **_kwargs: None,
                    setup_monitor_source=lambda *_args, **_kwargs: None,
                    ym_cleanup=lambda: None,
                    ym_to_wav=lambda path: path,
                ),
            ),
            library=bot_runtime.LibraryCallbacks(
                ensure_playlist_dir=lambda: None,
                filter_blacklisted_track_entries=lambda entries, _blacklist, _user_id: entries,
                list_playlists=lambda: [],
                load_blacklist=lambda: {},
                load_favorites=lambda: {},
                load_playlist=lambda *_args, **_kwargs: None,
                load_user_tracks=lambda *_args, **_kwargs: [],
                remove_user_track=lambda collection, _user_id, _url: (collection, True),
                save_blacklist=lambda *_args, **_kwargs: None,
                save_favorites=lambda *_args, **_kwargs: None,
                save_playlist=lambda *_args, **_kwargs: "playlist",
                toggle_user_track_entry=lambda collection, _user_id, _entry: (collection, True),
            ),
            collection=bot_runtime.CollectionCallbacks(
                auto_play_after_switch=true_async,
                build_collection_state_update=lambda *_args, **_kwargs: {},
                flip_sequence_formatter=lambda seq, current: f"{seq}:{current}",
                get_all_cache_counts=lambda *_args, **_kwargs: {},
                load_hvsc_local_cache=lambda: [],
                save_last_collection=lambda *_args, **_kwargs: None,
                set_volume_for_collection=lambda *_args, **_kwargs: None,
                stop_all_players=lambda: None,
                stop_state_streams=lambda *_args, **_kwargs: self._record_async(calls, "stop_state"),
                switch_collection=true_async,
            ),
            bootstrap=bot_runtime.BootstrapCallbacks(
                cleanup_temp_dir=lambda *_args, **_kwargs: calls.append("temp"),
                close_shared_session=lambda: self._record_async(calls, "session"),
                log_preloaded_cache=lambda *_args, **_kwargs: None,
                logger=types.SimpleNamespace(info=lambda *_args, **_kwargs: None),
                mod_only=lambda: (lambda fn: fn),
                release_process_lock=lambda *_args, **_kwargs: calls.append("lock"),
                run_startup_steps=true_async,
                save_metadata_cache=lambda *_args, **_kwargs: None,
                schedule_background_tasks=lambda *_args, **_kwargs: None,
            ),
        )

    async def _record_async(self, calls, item):
        calls.append(item)
        return None
