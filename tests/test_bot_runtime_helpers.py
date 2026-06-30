import sys
import json
import types
from pathlib import Path
import tempfile

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_support import install_discord_stubs


install_discord_stubs()

from entrypoint_glue import build_temp_path, place_track_in_queue
from archive_catalog import ArchiveCatalog
from archive_runtime import ArchiveRuntime, ArchiveRuntimeConfig
from stream_runtime import StreamRuntime
from test_runtime_context import build_runtime_test_context
from test_support import patch, unittest

import runtime_support


def build_archive_runtime_fixture(*, hvsc_base="https://hvsc.example/", ym_cache=""):
    logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )
    config = ArchiveRuntimeConfig(
        hvsc_base=hvsc_base,
        ym_cache=ym_cache,
    )
    archives = ArchiveCatalog(paths=config, logger=logger)
    archive_runtime = ArchiveRuntime(
        archives=archives,
        logger=logger,
        snes_spc_dir="",
        temp_dir="/tmp",
        build_temp_path=lambda url: f"/tmp/{Path(url).name}",
        get_shared_session=lambda: None,
        config=config,
    )
    return types.SimpleNamespace(
        archives=archives,
        archive_runtime=archive_runtime,
        config=config,
    )


class RuntimeSupportTests(unittest.TestCase):
    def test_cached_json_state_is_unchanged_when_write_fails(self):
        cache_state = {"data": {"old": True}, "mtime": 1.0}

        def fail_writer(_path, _data):
            raise OSError("disk full")

        with self.assertRaises(OSError):
            runtime_support.save_cached_json_file(
                "/tmp/unused.json",
                {"new": True},
                cache_state,
                writer=fail_writer,
            )

        self.assertEqual(cache_state, {"data": {"old": True}, "mtime": 1.0})

    def test_can_restore_queue_requires_matching_collection_and_track(self):
        saved = {"queue": ["track-1", "track-2"], "collection_mode": "asma"}

        self.assertTrue(runtime_support.can_restore_queue(saved, ["track-1", "track-3"], "asma"))
        self.assertFalse(runtime_support.can_restore_queue(saved, ["track-9"], "asma"))
        self.assertFalse(runtime_support.can_restore_queue(saved, ["track-1"], "hvsc"))

    def test_can_restore_queue_honors_minimum_length(self):
        saved = {"queue": ["track-1"], "collection_mode": "asma"}

        self.assertFalse(runtime_support.can_restore_queue(saved, ["track-1"], "asma", min_queue_length=2))

    def test_format_flip_sequence_highlights_current_collection(self):
        seq = runtime_support.format_flip_sequence(["A", "B", "C"], "B")

        self.assertEqual(seq, "A -> **B** -> C")

    def test_format_missing_dependencies_lists_all_tools(self):
        message = runtime_support.format_missing_dependencies(
            [("audacious", "headless playback engine"), ("ffmpeg", "audio capture and transcoding")]
        )

        self.assertIn("audacious", message)
        self.assertIn("ffmpeg", message)
        self.assertIn("Install the missing packages", message)

    def test_prepare_playback_queue_restores_saved_queue(self):
        saved = {"queue": ["track-1", "track-2"], "collection_mode": "asma", "index": 1, "loop": False}

        queue_state = runtime_support.prepare_playback_queue(
            ["track-1", "track-3"],
            saved,
            "asma",
            True,
            shuffle_enabled=True,
        )

        self.assertEqual(queue_state["queue"], ["track-1", "track-2"])
        self.assertEqual(queue_state["index"], 1)
        self.assertFalse(queue_state["loop"])
        self.assertTrue(queue_state["restored"])

    def test_prepare_playback_queue_shuffles_new_queue(self):
        shuffled = []

        def fake_shuffle(items):
            shuffled.append(list(items))
            items.reverse()

        queue_state = runtime_support.prepare_playback_queue(
            ["track-1", "track-2", "track-3"],
            None,
            "asma",
            True,
            shuffle_enabled=True,
            shuffle_func=fake_shuffle,
        )

        self.assertEqual(shuffled, [["track-1", "track-2", "track-3"]])
        self.assertEqual(queue_state["queue"], ["track-3", "track-2", "track-1"])
        self.assertEqual(queue_state["index"], 0)
        self.assertTrue(queue_state["loop"])
        self.assertFalse(queue_state["restored"])

    def test_prepare_playback_queue_applies_track_filter(self):
        queue_state = runtime_support.prepare_playback_queue(
            ["allowed-1", "blocked", "allowed-2"],
            None,
            "asma",
            True,
            shuffle_enabled=False,
            track_filter=lambda tracks: [track for track in tracks if track != "blocked"],
        )

        self.assertEqual(queue_state["queue"], ["allowed-1", "allowed-2"])
        self.assertEqual(queue_state["index"], 0)
        self.assertFalse(queue_state["restored"])

    def test_build_collection_state_update_normalizes_switch_fields(self):
        update = runtime_support.build_collection_state_update("hvsc", ["track-1"])

        self.assertEqual(update["collection_mode"], "hvsc")
        self.assertEqual(update["loaded_collection"], "hvsc")
        self.assertEqual(update["tracks"], ["track-1"])
        self.assertEqual(update["queue"], [])
        self.assertEqual(update["index"], -1)

    def test_classify_track_route_covers_supported_collection_types(self):
        self.assertEqual(
            runtime_support.classify_track_route("https://www.hvsc.c64.org/download/C64Music/A.sid", "asma"),
            {"mode": "hvsc", "handler": "hvsc"},
        )
        self.assertEqual(
            runtime_support.classify_track_route("module.mod", "asma"),
            {"mode": "tiny", "handler": "tiny"},
        )
        self.assertEqual(
            runtime_support.classify_track_route("https://api.modarchive.org/downloads.php?moduleid=1", "asma"),
            {"mode": "modarchive", "handler": "modarchive"},
        )
        self.assertEqual(
            runtime_support.classify_track_route("track.ay", "asma"),
            {"mode": "ay", "handler": "ay"},
        )
        self.assertEqual(
            runtime_support.classify_track_route("track.ym", "asma"),
            {"mode": "ym", "handler": "ym"},
        )
        self.assertEqual(
            runtime_support.classify_track_route("game.rsn", "spc", snes_known=True),
            {"mode": "spc", "handler": "spc"},
        )
        self.assertEqual(
            runtime_support.classify_track_route("track.sap", "asma"),
            {"mode": "asma", "handler": "asma"},
        )

    def test_should_disconnect_for_empty_channel_tracks_timer_and_timeout(self):
        should_disconnect, empty_since = runtime_support.should_disconnect_for_empty_channel(1, None, 100.0, 60)
        self.assertFalse(should_disconnect)
        self.assertEqual(empty_since, 100.0)

        should_disconnect, empty_since = runtime_support.should_disconnect_for_empty_channel(1, 100.0, 161.0, 60)
        self.assertTrue(should_disconnect)
        self.assertEqual(empty_since, 100.0)

        should_disconnect, empty_since = runtime_support.should_disconnect_for_empty_channel(2, 100.0, 120.0, 60)
        self.assertFalse(should_disconnect)
        self.assertIsNone(empty_since)

    def test_should_confirm_output_drop_respects_grace_and_gme_formats(self):
        confirmed, drop_since = runtime_support.should_confirm_output_drop(
            20, 3, None, 100.0, 3, is_gme_format=False
        )
        self.assertFalse(confirmed)
        self.assertEqual(drop_since, 100.0)

        confirmed, drop_since = runtime_support.should_confirm_output_drop(
            20, 3, 100.0, 104.0, 3, is_gme_format=False
        )
        self.assertTrue(confirmed)
        self.assertIsNone(drop_since)

        confirmed, drop_since = runtime_support.should_confirm_output_drop(
            20, 3, 100.0, 104.0, 3, is_gme_format=True
        )
        self.assertFalse(confirmed)
        self.assertIsNone(drop_since)

    def test_timeout_and_predownload_helpers(self):
        self.assertEqual(runtime_support.compute_timeout_seconds(120, is_gme_format=False), 135)
        self.assertEqual(runtime_support.compute_timeout_seconds(120, is_gme_format=True), 600)
        self.assertTrue(runtime_support.should_force_timeout_stop(700, 600))
        self.assertFalse(runtime_support.should_force_timeout_stop(10001, 600))

        self.assertTrue(
            runtime_support.should_start_predownload(
                5,
                0,
                loop_enabled=True,
                predownload_ready=False,
                predownload_inflight=False,
                next_url="http://example.com/next.sap",
            )
        )
        self.assertFalse(
            runtime_support.should_start_predownload(
                5,
                0,
                loop_enabled=True,
                predownload_ready=True,
                predownload_inflight=False,
                next_url="http://example.com/next.sap",
            )
        )

    def test_should_advance_after_stop_waits_for_grace_and_loaded_state(self):
        should_advance, since = runtime_support.should_advance_after_stop(None, 100.0, 3, still_loaded=False)
        self.assertFalse(should_advance)
        self.assertEqual(since, 100.0)

        should_advance, since = runtime_support.should_advance_after_stop(100.0, 104.0, 3, still_loaded=False)
        self.assertTrue(should_advance)
        self.assertIsNone(since)

        should_advance, since = runtime_support.should_advance_after_stop(100.0, 104.0, 3, still_loaded=True)
        self.assertFalse(should_advance)
        self.assertEqual(since, 100.0)

    def test_toggle_and_remove_user_track(self):
        data = {}
        entry = {"url": "track-1", "name": "Track 1"}

        data, added = runtime_support.toggle_user_track(data, 123, entry)
        self.assertTrue(added)
        self.assertEqual(runtime_support.get_user_tracks(data, 123), [entry])

        data, added = runtime_support.toggle_user_track(data, 123, entry)
        self.assertFalse(added)
        self.assertEqual(runtime_support.get_user_tracks(data, 123), [])

        data, added = runtime_support.toggle_user_track(data, 123, entry)
        self.assertTrue(added)
        data, removed = runtime_support.remove_user_track(data, 123, "track-1")
        self.assertTrue(removed)
        self.assertEqual(runtime_support.get_user_tracks(data, 123), [])

    def test_blacklist_filters_for_urls_and_entries(self):
        blacklist = {"5": {"tracks": [{"url": "blocked"}]}}

        self.assertEqual(
            runtime_support.filter_blacklisted_urls(["allowed", "blocked"], blacklist, 5),
            ["allowed"],
        )
        self.assertEqual(
            runtime_support.filter_track_entries_by_blacklist(
                [{"url": "allowed"}, {"url": "blocked"}], blacklist, 5
            ),
            [{"url": "allowed"}],
        )

    def test_playlist_helpers_roundtrip_and_summary(self):
        temp_dir = ROOT / "tmp" / "runtime_support_tests"
        runtime_support.ensure_directory(str(temp_dir))
        playlist_name = "My / Playlist"
        safe_name = runtime_support.sanitize_playlist_name(playlist_name)
        record = runtime_support.build_playlist_record(
            playlist_name,
            [{"url": "track-1"}],
            7,
            "tester",
            created=123.0,
        )
        path = temp_dir / f"{safe_name}.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)

        loaded = runtime_support.load_playlist_record(str(temp_dir), playlist_name)
        summary = runtime_support.summarize_playlists(str(temp_dir))

        self.assertEqual(loaded["name"], playlist_name)
        self.assertEqual(summary[0]["name"], playlist_name)
        self.assertEqual(summary[0]["tracks"], 1)

        path.unlink()


class FetchMetadataBatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fixture = build_archive_runtime_fixture()
        self.metadata_index = self.fixture.archives.metadata_index

    async def test_skips_cached_urls_without_misalignment(self):
        self.metadata_index["cached"] = {"NAME": "Cached"}

        async def fake_fetch(_self, _session, url):
            return {"NAME": f"meta:{url}"}

        with patch.object(type(self.fixture.archive_runtime), "fetch_single_metadata", new=fake_fetch):
            results = await self.fixture.archive_runtime.fetch_metadata_batch(
                None,
                ["cached", "fresh-a", "fresh-b"],
                batch_size=3,
            )

        self.assertEqual(results["fresh-a"]["NAME"], "meta:fresh-a")
        self.assertEqual(results["fresh-b"]["NAME"], "meta:fresh-b")
        self.assertNotIn("cached", results)


class TempPathTests(unittest.TestCase):
    def test_build_temp_path_is_collision_resistant_for_same_filename(self):
        ctx = build_runtime_test_context(
            state=types.SimpleNamespace(
                stream_runtime=types.SimpleNamespace(active_streams={}),
                service_facade=object(),
                collection_service=types.SimpleNamespace(collections={}),
                collections={},
            ),
            runtime=types.SimpleNamespace(
                state=types.SimpleNamespace(
                    app_services=types.SimpleNamespace(
                        app_state=types.SimpleNamespace(guilds={}, message_track_map={})
                    ),
                    playback_handlers={},
                )
            ),
            app_config=types.SimpleNamespace(temp_dir="/tmp/runtime-test"),
            archive_runtime_config=types.SimpleNamespace(),
        )
        first = build_temp_path(ctx.app_config.temp_dir, "https://example.com/a/track.sap")
        second = build_temp_path(ctx.app_config.temp_dir, "https://example.com/b/track.sap")

        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith("_track.sap"))
        self.assertTrue(second.endswith("_track.sap"))


class QueuePlacementTests(unittest.TestCase):
    def test_place_track_in_queue_uses_existing_position(self):
        queue, index = place_track_in_queue(["a", "b", "c"], "b")

        self.assertEqual(queue, ["a", "b", "c"])
        self.assertEqual(index, 1)

    def test_place_track_in_queue_inserts_missing_track_at_front(self):
        queue, index = place_track_in_queue(["a", "c"], "b")

        self.assertEqual(queue, ["b", "a", "c"])
        self.assertEqual(index, 0)


class StreamCleanupTests(unittest.TestCase):
    def setUp(self):
        self.stream_runtime = StreamRuntime(
            sink_name="sink",
            audio_format="s16le",
            sample_rate=48000,
            channels=2,
            logger=types.SimpleNamespace(
                info=lambda *args, **kwargs: None,
                debug=lambda *args, **kwargs: None,
            ),
            clear_predownload_state=lambda _state: None,
        )

    def tearDown(self):
        self.stream_runtime.active_streams.clear()

    def test_after_stream_end_cleans_matching_source_id(self):
        cleaned = []

        class FakeSource:
            source_id = 42

            def cleanup(self):
                cleaned.append(True)

        self.stream_runtime.active_streams[123] = FakeSource()
        self.stream_runtime.after_stream_end(123, None, 42)

        self.assertNotIn(123, self.stream_runtime.active_streams)
        self.assertEqual(cleaned, [True])

    def test_after_stream_end_ignores_stale_source_id(self):
        cleaned = []

        class FakeSource:
            source_id = 99

            def cleanup(self):
                cleaned.append(True)

        self.stream_runtime.active_streams[123] = FakeSource()
        self.stream_runtime.after_stream_end(123, None, 42)

        self.assertIn(123, self.stream_runtime.active_streams)
        self.assertEqual(cleaned, [])


class SonglengthParsingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = build_archive_runtime_fixture()
        self.fixture.archives.sid_durations.clear()

    def test_parse_old_format(self):
        tracks = self.fixture.archive_runtime.parse_songlengths_to_tracks("; /MUSICIANS/A/Author/Track.sid = 3:02")

        self.assertEqual(len(tracks), 1)
        self.assertEqual(self.fixture.archives.sid_durations[tracks[0]], 182)

    def test_parse_md5_format(self):
        data = "; /MUSICIANS/A/Author/Track.sid\n6897307ef63533962667412848c92124=1:17"
        tracks = self.fixture.archive_runtime.parse_songlengths_to_tracks(data)

        self.assertEqual(len(tracks), 1)
        self.assertEqual(self.fixture.archives.sid_durations[tracks[0]], 77)

    def test_parse_md5_with_alt_duration(self):
        data = "; /MUSICIANS/A/Author/Track.sid\nabc123=3:02 (alt 4:15)"
        tracks = self.fixture.archive_runtime.parse_songlengths_to_tracks(data)

        self.assertEqual(len(tracks), 1)
        self.assertEqual(self.fixture.archives.sid_durations[tracks[0]], 182)

    def test_parse_md5_no_duration(self):
        data = "; /MUSICIANS/A/Author/Track.sid\nnoise"
        tracks = self.fixture.archive_runtime.parse_songlengths_to_tracks(data)

        self.assertEqual(len(tracks), 1)
        self.assertNotIn(tracks[0], self.fixture.archives.sid_durations)


class YmCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_cache = Path(self.temp_dir.name) / "ym_cache.json"
        self.fixture = build_archive_runtime_fixture(ym_cache=str(self.temp_cache))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_ym_cache_returns_none_when_missing(self):
        result = self.fixture.archive_runtime.load_ym_cache()
        self.assertIsNone(result)

    def test_load_ym_cache_returns_tracks(self):
        data = {
            "version": 1,
            "total": 3,
            "tracks": [
                {"path": "modland/Jochen Hippel/track1.ym", "size": 1234, "collection": "modland"},
                {"path": "bulba_v5/test.ym", "size": 567, "collection": "bulba_v5"},
            ]
        }
        with open(self.temp_cache, "w") as f:
            json.dump(data, f)
        result = self.fixture.archive_runtime.load_ym_cache()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIn("modland/Jochen Hippel/track1.ym", result)
