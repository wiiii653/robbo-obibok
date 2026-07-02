import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robbo_obibok.app_services import AppServicesProtocol
from robbo_obibok.bot_dependencies import LibraryCommandDependencies


class BotDependenciesTests(unittest.TestCase):
    def test_app_services_protocol_does_not_advertise_raw_runtime_maps(self):
        self.assertFalse(hasattr(AppServicesProtocol, "guilds"))
        self.assertFalse(hasattr(AppServicesProtocol, "message_track_map"))
        self.assertTrue(hasattr(AppServicesProtocol, "iter_guild_states"))
        self.assertTrue(hasattr(AppServicesProtocol, "get_message_track"))

    def test_library_command_dependencies_use_accessor_not_raw_message_track_map(self):
        annotations = LibraryCommandDependencies.__annotations__

        self.assertIn("get_message_track", annotations)
        self.assertNotIn("message_track_map", annotations)
        self.assertEqual(
            annotations["get_message_track"],
            "Callable[[int], dict[str, object] | None]",
        )

    def test_playback_command_dependencies_use_accessors_for_metadata_and_snes_maps(self):
        from robbo_obibok.bot_dependencies import PlaybackCommandDependencies

        annotations = PlaybackCommandDependencies.__annotations__

        self.assertIn("get_metadata_entry", annotations)
        self.assertIn("metadata_index_size", annotations)
        self.assertIn("get_modarchive_track_name", annotations)
        self.assertIn("has_snes_metadata", annotations)
        self.assertIn("iter_snes_metadata", annotations)
        self.assertNotIn("metadata_index", annotations)
        self.assertNotIn("modarchive_name_map", annotations)
        self.assertNotIn("snes_metadata", annotations)

    def test_session_runtime_dependencies_use_callbacks_not_raw_maps(self):
        from robbo_obibok.session_runtime import (
            MetadataSessionDependencies,
            PlaybackSessionDependencies,
        )

        playback_annotations = PlaybackSessionDependencies.__annotations__
        metadata_annotations = MetadataSessionDependencies.__annotations__

        self.assertIn("get_snes_game", playback_annotations)
        self.assertIn("has_snes_game", playback_annotations)
        self.assertNotIn("snes_metadata", playback_annotations)
        self.assertIn("has_metadata_entry", metadata_annotations)
        self.assertIn("metadata_index_size", metadata_annotations)
        self.assertIn("snapshot_metadata_index", metadata_annotations)
        self.assertIn("store_metadata_entry", metadata_annotations)
        self.assertNotIn("metadata_index", metadata_annotations)
