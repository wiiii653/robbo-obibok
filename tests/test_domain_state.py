import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import domain_state
from bot_persistence import load_queue_from_disk, save_queue_to_disk


class AppRuntimeStateTests(unittest.TestCase):
    def test_registry_helpers_and_views_route_state_changes(self):
        runtime_state = domain_state.AppRuntimeState(
            queue_dir="/tmp/unused",
            default_collection_mode="asma",
            json_writer=self._write_json,
        )
        playlist = domain_state.PlaylistState()

        runtime_state.register_guild_state(7, playlist)
        runtime_state.replace_message_track_map({11: {"url": "track.sap"}})

        self.assertEqual(list(runtime_state.iter_guild_states()), [playlist])
        self.assertEqual(runtime_state.get_message_track(11), {"url": "track.sap"})
        self.assertEqual(dict(runtime_state.guilds_view), {7: playlist})
        self.assertEqual(dict(runtime_state.message_track_map_view), {11: {"url": "track.sap"}})

    def test_playlist_state_helpers_update_related_fields(self):
        state = domain_state.PlaylistState()

        state.bind_voice_context(guild_id=5, ctx="ctx", vc="vc")
        state.set_collection_mode("hvsc")
        state.set_loaded_collection("hvsc", ["a.sid"])
        state.set_queue_state(["a.sid", "b.sid"], 1, loop=False)
        state.set_search_results(["a.sid"])
        state.set_predownload("/tmp/a.sid", "https://example.com/a.sid")
        state.set_subsong_state(path="/tmp/a.sid", total=3, current=1)
        state.reset_subsong_state()
        state.clear_predownload()
        state.clear_queue_state()

        self.assertEqual((state.guild_id, state.ctx, state.vc), (5, "ctx", "vc"))
        self.assertEqual(state.collection_mode, "hvsc")
        self.assertEqual(state.tracks, ["a.sid"])
        self.assertEqual(state.queue, [])
        self.assertEqual(state.index, -1)
        self.assertFalse(state.loop)
        self.assertEqual(state.search_results, ["a.sid"])
        self.assertIsNone(state.pre_downloaded)
        self.assertIsNone(state.pre_downloaded_url)
        self.assertIsNone(state.pre_download_task)
        self.assertEqual(state.subsong_wavs, [])
        self.assertEqual(state.subsong_total, 0)
        self.assertEqual(state.subsong_current, -1)
        self.assertIsNone(state.subsong_path)

    def test_playlist_queue_position_history_and_upcoming_helpers(self):
        state = domain_state.PlaylistState()
        state.set_queue_state(["a.sid", "b.sid", "c.sid", "d.sid"], 2, loop=True)

        self.assertEqual(state.queue_length(), 4)
        self.assertTrue(state.has_current_queue_item())
        self.assertTrue(state.contains_queue_index(2))
        self.assertFalse(state.contains_queue_index(4))
        self.assertEqual(state.current_queue_url(), "c.sid")
        self.assertEqual(state.current_queue_position(), (3, 4))
        self.assertEqual(state.remaining_queue_count(), 1)
        self.assertEqual(state.next_queue_url(), "d.sid")
        self.assertEqual(state.upcoming_queue(2), ["d.sid"])
        self.assertEqual(state.played_queue(2), ["a.sid", "b.sid"])

        state.set_queue_state(["a.sid", "b.sid"], 1, loop=True)
        self.assertEqual(state.next_queue_url(), "a.sid")

        state.set_loop_enabled(False)
        self.assertIsNone(state.next_queue_url())

        state.clear_queue_state()

        self.assertEqual(state.queue_length(), 0)
        self.assertFalse(state.has_current_queue_item())
        self.assertIsNone(state.current_queue_position())
        self.assertEqual(state.remaining_queue_count(), 0)
        self.assertEqual(state.upcoming_queue(), [])
        self.assertEqual(state.played_queue(), [])

    def test_save_and_load_queue_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_state = domain_state.AppRuntimeState(
                queue_dir=tmpdir,
                default_collection_mode="hvsc",
                json_writer=self._write_json,
                save_queue_fn=save_queue_to_disk,
                load_queue_fn=load_queue_from_disk,
            )
            state = runtime_state.get_state(42)
            state.set_guild_id(42)
            state.set_queue_state(["a.sid", "b.sid"], 1, loop=False)
            state.set_collection_mode("hvsc")

            runtime_state.save_queue(state)

            self.assertEqual(
                runtime_state.load_queue(42),
                {
                    "queue": ["a.sid", "b.sid"],
                    "index": 1,
                    "loop": False,
                    "collection_mode": "hvsc",
                },
            )

    def test_load_queue_rejects_invalid_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_state = domain_state.AppRuntimeState(
                queue_dir=tmpdir,
                default_collection_mode="hvsc",
                json_writer=self._write_json,
                save_queue_fn=save_queue_to_disk,
                load_queue_fn=load_queue_from_disk,
            )
            Path(tmpdir, "42.json").write_text(
                '{"queue": ["a.sid"], "index": "bad", "loop": true, "collection_mode": "hvsc"}',
                encoding="utf-8",
            )

            self.assertIsNone(runtime_state.load_queue(42))

    def test_register_now_playing_message_prunes_old_entries(self):
        runtime_state = domain_state.AppRuntimeState(
            queue_dir="/tmp/unused",
            default_collection_mode="asma",
            json_writer=self._write_json,
            message_track_map_max=2,
        )

        with patch.object(domain_state.time, "time", side_effect=[1.0, 2.0, 3.0]):
            runtime_state.register_now_playing_message(1, "a.sap", "A", "Auth A")
            runtime_state.register_now_playing_message(2, "b.sap", "B", "Auth B")
            runtime_state.register_now_playing_message(3, "c.sap", "C", "Auth C")

        self.assertEqual(sorted(runtime_state.message_track_map), [2, 3])
        self.assertEqual(runtime_state.message_track_map[3]["url"], "c.sap")

    def _write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
