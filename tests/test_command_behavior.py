import sys
import asyncio
from pathlib import Path
from dataclasses import replace

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from domain_state import PlaylistState
from collection_catalog import FLIP_SEQ as COLLECTION_FLIP_SEQ
from test_support import FakeContext, RegistrationBot, patch, unittest
from test_runtime_context import command_test_context
import library_commands
import playback_commands


class AsyncTestCase(unittest.TestCase):
    def _callTestMethod(self, method):
        result = method()
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result


class CommandBehaviorTests(AsyncTestCase):
    async def test_play_numeric_query_uses_targeted_playback_session(self):
        with command_test_context() as runtime_ctx:
            state = PlaylistState()
            state.set_search_results(["track-2"])
            state.set_tracks(["track-1", "track-2"])
            started = []

            async def start_targeted(ctx, found_state, url):
                started.append((ctx.guild.id, found_state is state, url))
                return True

            deps = runtime_ctx.playback_command_deps(
                get_state=lambda guild_id: state,
                start_targeted_playback_session=start_targeted,
                ensure_tracks=lambda _state: self._true_async(),
            )
            fake_bot = RegistrationBot()
            playback_commands.register_playback_commands(fake_bot, deps)
            ctx = FakeContext()

            await fake_bot.commands["play"]["func"](ctx, query="1")

            self.assertEqual(started, [(1, True, "track-2")])
            self.assertEqual(ctx.sent, [])

    async def test_favplay_builds_queue_and_starts_monitoring(self):
        with command_test_context() as runtime_ctx:
            state = PlaylistState()
            state.set_tracks(["https://asma.atari.org/asma/A.sap", "https://asma.atari.org/asma/B.sap"])
            save_calls = []
            monitor_calls = []

            async def play_current_track(_ctx):
                return True

            async def monitor_playback(*args):
                monitor_calls.append(args)

            deps = runtime_ctx.library_command_deps(
                get_state=lambda guild_id: state,
                load_favorites=lambda: {},
                load_user_tracks=lambda _data, _user_id: [
                    {"url": "https://asma.atari.org/asma/A.sap", "name": "A"},
                    {"url": "https://asma.atari.org/asma/B.sap", "name": "B"},
                ],
                load_blacklist=lambda: {},
                filter_blacklisted_track_entries=lambda tracks, _blacklist, _user_id: tracks,
                ensure_tracks=self._true_async,
                clear_predownload_state=lambda _state, **_kwargs: None,
                play_current_track=play_current_track,
                save_queue=lambda found_state: save_calls.append(list(found_state.queue)),
                monitor_playback=monitor_playback,
            )
            fake_bot = RegistrationBot()
            library_commands.register_library_commands(fake_bot, deps)
            ctx = FakeContext()
            scheduled = []
            original_create_task = asyncio.create_task
            def tracking_create_task(coro):
                task = original_create_task(coro)
                scheduled.append(coro)
                return task

            with patch.object(library_commands.random, "shuffle", lambda items: None), \
                 patch("asyncio.create_task", side_effect=tracking_create_task):
                await fake_bot.commands["favplay"]["func"](ctx, number="")

            self.assertEqual(state.collection_mode, "asma")
            self.assertEqual(state.queue, ["https://asma.atari.org/asma/A.sap", "https://asma.atari.org/asma/B.sap"])
            self.assertEqual(state.index, 0)
            self.assertEqual(save_calls, [state.queue])
            self.assertEqual(len(scheduled), 1)
            self.assertIn("Playing 2 favorites", ctx.sent[0].content)

    async def test_flip_advances_to_next_collection(self):
        with command_test_context() as runtime_ctx:
            state = PlaylistState()
            state.set_collection_mode("asma")
            switched = []

            async def switch_collection(ctx, mode, *, flip_seq=None):
                switched.append((ctx.guild.id, mode, tuple(flip_seq or [])))
                return True

            deps = runtime_ctx.playback_command_deps(
                get_state=lambda guild_id: state,
                switch_collection=switch_collection,
            )
            fake_bot = RegistrationBot()
            playback_commands.register_playback_commands(fake_bot, deps)
            ctx = FakeContext()

            await fake_bot.commands["flip"]["func"](ctx)

            self.assertEqual(switched, [(1, "modarchive", tuple(COLLECTION_FLIP_SEQ))])

    async def test_snes_search_populates_results_and_sends_listing(self):
        with command_test_context() as runtime_ctx:
            state = PlaylistState()
            snes_metadata = {
                "https://example.com/game.rsn": {
                    "rsn_url": "https://example.com/game.rsn",
                    "name": "Legend of Testing",
                    "composers": ["Alice Example"],
                    "tracks": 12,
                }
            }

            deps = runtime_ctx.playback_command_deps(
                get_state=lambda guild_id: state,
                has_snes_metadata=lambda: bool(snes_metadata),
                iter_snes_metadata=lambda: snes_metadata.items(),
                load_snes_cache=lambda: list(snes_metadata),
            )
            fake_bot = RegistrationBot()
            playback_commands.register_playback_commands(fake_bot, deps)
            ctx = FakeContext()

            await fake_bot.commands["snes_cmd"]["func"](ctx, query="legend")

            self.assertEqual(state.search_results, ["https://example.com/game.rsn"])
            self.assertIn("Legend of Testing", ctx.sent[0].content)

    async def test_play_does_not_schedule_monitor_when_startup_playback_fails(self):
        with command_test_context() as runtime_ctx:
            state = PlaylistState()
            state.set_collection_mode("asma")
            state.set_tracks(["https://asma.atari.org/asma/A.sap"])
            save_calls = []

            async def play_current_track(_ctx):
                return False

            deps = runtime_ctx.playback_command_deps(
                get_state=lambda guild_id: state,
                clear_predownload_state=lambda _state, **_kwargs: None,
                ensure_tracks=self._true_async,
                load_queue=lambda _guild_id: None,
                play_current_track=play_current_track,
                save_queue=lambda found_state: save_calls.append(found_state.index),
            )
            fake_bot = RegistrationBot()
            playback_commands.register_playback_commands(fake_bot, deps)
            ctx = FakeContext()

            await fake_bot.commands["play"]["func"](ctx, query="")

            self.assertEqual(save_calls, [])
            self.assertEqual(fake_bot.scheduled, [])

    async def test_refresh_reports_missing_asma_cache(self):
        with command_test_context() as runtime_ctx:
            state = PlaylistState()
            deps = runtime_ctx.playback_command_deps(
                get_state=lambda guild_id: state,
                load_tracks_for_mode=self._none_async,
            )
            fake_bot = RegistrationBot()
            ctx = FakeContext()
            playback_commands.register_playback_commands(fake_bot, deps)

            await fake_bot.commands["refresh"]["func"](ctx)

            self.assertEqual(
                ctx.sent[-1].content,
                "❌ ASMA local cache not found. Run `python build_asma_index.py` first.",
            )

    async def test_switch_collection_flip_failure_keeps_previous_mode(self):
        with command_test_context() as runtime_ctx:
            state = PlaylistState()
            state.set_collection_mode("asma")
            ctx = FakeContext()
            override_collection = replace(
                runtime_ctx.collections["hvsc"],
                load_func=lambda: None,
                fallback_func=None,
            )
            with (
                runtime_ctx.scoped_attrs(
                    runtime_ctx.collection_service,
                    stop_all_players=lambda: None,
                    stop_state_streams=self._true_async,
                ),
                runtime_ctx.scoped_collection("hvsc", override_collection),
                runtime_ctx.scoped_guilds({ctx.guild.id: state}),
            ):
                result = await runtime_ctx.service_facade.switch_collection(
                    ctx,
                    "hvsc",
                    flip_seq=COLLECTION_FLIP_SEQ,
                )

            self.assertFalse(result)
            self.assertEqual(state.collection_mode, "asma")
            self.assertIn("Could not load HVSC", ctx.sent[-1].content)

    async def test_play_current_track_reports_handler_exception(self):
        with command_test_context() as runtime_ctx:
            state = PlaylistState()
            state.set_collection_mode("asma")
            state.set_queue_state(["bad.sap"], 0)
            ctx = FakeContext()

            async def boom(_ctx, _state, _url):
                raise RuntimeError("boom")

            with (
                runtime_ctx.scoped_playback_handlers({"asma": boom}),
                runtime_ctx.scoped_guilds({ctx.guild.id: state}),
            ):
                result = await runtime_ctx.service_facade.play_current_track(ctx)

            self.assertFalse(result)
            self.assertIn("Error playing `bad.sap`: boom", ctx.sent[-1].content)

    async def _true_async(self, *_args, **_kwargs):
        return True

    async def _none_async(self, *_args, **_kwargs):
        return None
