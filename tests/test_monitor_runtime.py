import asyncio
import sys
import types
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_state import PlaylistState
import playback_runtime
from entrypoint_glue import clear_predownload_state
from test_support import FakeVoiceClient, patch, unittest


class PredownloadStateTests(unittest.TestCase):
    def test_clear_predownload_state_resets_bookkeeping(self):
        state = PlaylistState()
        state.set_predownload("/tmp/nonexistent-track.sap", "https://example.com/track.sap")
        state.set_predownload_task(unittest.mock.MagicMock(done=lambda: True))

        clear_predownload_state(state)

        self.assertIsNone(state.pre_downloaded)
        self.assertIsNone(state.pre_downloaded_url)
        self.assertIsNone(state.pre_download_task)


class AsyncTestCase(unittest.TestCase):
    def _callTestMethod(self, method):
        result = method()
        if asyncio.iscoroutine(result):
            return asyncio.run(result)
        return result


class MonitorRuntimeTests(AsyncTestCase):
    async def test_monitor_advances_to_next_track_when_playback_stops(self):
        messages = []
        skipped = []
        state = types.SimpleNamespace(
            current_sap_path=None,
            queue=["a", "b"],
            index=0,
            loop=False,
            pre_downloaded=None,
            pre_download_task=None,
        )
        vc = FakeVoiceClient()
        shutdown_state = {"value": False}
        shutdown_flag = types.SimpleNamespace(is_set=lambda: shutdown_state["value"])

        async def skip_to_next(_ctx):
            skipped.append(True)
            vc.disconnected = True
            shutdown_state["value"] = True

        deps = playback_runtime.MonitorDependencies(
            ACTIVE_STREAMS={},
            AUTO_EMPTY_TIMEOUT=60,
            SINK_NAME="asma_bot",
            audacious_song=lambda: "",
            audacious_stop=lambda: None,
            compute_timeout_seconds=lambda *_args, **_kwargs: 135,
            get_state=lambda guild_id: state,
            is_gme_format_path=lambda path: False,
            is_playing=lambda: False,
            pre_download_next=lambda _state: None,
            save_queue=lambda _state: None,
            should_advance_after_stop=lambda since, now, grace_seconds, still_loaded=False: (True, None),
            should_confirm_output_drop=lambda *args, **kwargs: (False, None),
            should_disconnect_for_empty_channel=lambda *args, **kwargs: (False, None),
            should_force_timeout_stop=lambda *_args: False,
            should_start_predownload=lambda *args, **kwargs: False,
            shutdown_flag=shutdown_flag,
            skip_to_next=skip_to_next,
            stop_all_players=lambda: None,
            get_output_length=lambda: -1,
            get_song_length=lambda: -1,
            logger=types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None),
            run_sync=self._run_sync,
        )
        ctx = types.SimpleNamespace(send=self._capture_send(messages))

        with patch.object(playback_runtime.asyncio, "sleep", self._fast_sleep):
            await asyncio.wait_for(playback_runtime.monitor_playback(ctx, vc, 1, deps), timeout=0.5)

        self.assertEqual(skipped, [True])
        self.assertEqual(messages, [])

    async def test_monitor_reports_playlist_end_when_no_more_tracks(self):
        messages = []
        state = types.SimpleNamespace(
            current_sap_path=None,
            queue=["a"],
            index=0,
            loop=False,
            pre_downloaded=None,
            pre_download_task=None,
        )
        vc = FakeVoiceClient()
        shutdown_state = {"value": False}
        shutdown_flag = types.SimpleNamespace(is_set=lambda: shutdown_state["value"])

        deps = playback_runtime.MonitorDependencies(
            ACTIVE_STREAMS={},
            AUTO_EMPTY_TIMEOUT=60,
            SINK_NAME="asma_bot",
            audacious_song=lambda: "",
            audacious_stop=lambda: None,
            compute_timeout_seconds=lambda *_args, **_kwargs: 135,
            get_state=lambda guild_id: state,
            is_gme_format_path=lambda path: False,
            is_playing=lambda: False,
            pre_download_next=lambda _state: None,
            save_queue=lambda _state: None,
            should_advance_after_stop=lambda since, now, grace_seconds, still_loaded=False: (True, None),
            should_confirm_output_drop=lambda *args, **kwargs: (False, None),
            should_disconnect_for_empty_channel=lambda *args, **kwargs: (False, None),
            should_force_timeout_stop=lambda *_args: False,
            should_start_predownload=lambda *args, **kwargs: False,
            shutdown_flag=shutdown_flag,
            skip_to_next=self._unreachable_async,
            stop_all_players=lambda: None,
            get_output_length=lambda: -1,
            get_song_length=lambda: -1,
            logger=types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None),
            run_sync=self._run_sync,
        )
        ctx = types.SimpleNamespace(send=self._capture_send(messages))

        with patch.object(playback_runtime.asyncio, "sleep", self._fast_sleep):
            await asyncio.wait_for(playback_runtime.monitor_playback(ctx, vc, 1, deps), timeout=0.5)

        self.assertTrue(vc.disconnected)
        self.assertIn("Playlist ended. Use !play to restart.", messages[-1])

    async def _fast_sleep(self, *_args, **_kwargs):
        return None

    async def _unreachable_async(self, *_args, **_kwargs):
        raise AssertionError("skip_to_next should not be called")

    async def _run_sync(self, func, *args):
        return func(*args)

    def _capture_send(self, sink):
        async def sender(content=None, embed=None):
            sink.append(content if content is not None else embed)
        return sender
