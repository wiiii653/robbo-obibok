import sys
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from domain_services import AppServices
from domain_state import AppRuntimeState


class AppServicesTests(unittest.TestCase):
    def test_iter_guild_states_returns_runtime_state_values(self):
        first = object()
        second = object()
        app_state = AppRuntimeState(
            queue_dir="/tmp/unused",
            default_collection_mode="asma",
            json_writer=lambda *_args, **_kwargs: None,
        )
        app_state.register_guild_state(1, first)
        app_state.register_guild_state(2, second)
        services = AppServices(
            app_state=app_state,
            favorites_store=types.SimpleNamespace(load=lambda: {}, save=lambda _data: None),
            blacklist_store=types.SimpleNamespace(load=lambda: {}, save=lambda _data: None),
            playlist_store=types.SimpleNamespace(
                ensure_playlist_dir=lambda: None,
                save_playlist=lambda *_args, **_kwargs: "playlist",
                load_playlist=lambda _name: None,
                list_playlists=lambda: [],
            ),
        )

        self.assertEqual(list(services.iter_guild_states()), [first, second])

    def test_get_message_track_delegates_to_app_state_map(self):
        app_state = AppRuntimeState(
            queue_dir="/tmp/unused",
            default_collection_mode="asma",
            json_writer=lambda *_args, **_kwargs: None,
        )
        app_state.message_track_map[12] = {"url": "track.sap"}
        services = AppServices(
            app_state=app_state,
            favorites_store=types.SimpleNamespace(load=lambda: {}, save=lambda _data: None),
            blacklist_store=types.SimpleNamespace(load=lambda: {}, save=lambda _data: None),
            playlist_store=types.SimpleNamespace(
                ensure_playlist_dir=lambda: None,
                save_playlist=lambda *_args, **_kwargs: "playlist",
                load_playlist=lambda _name: None,
                list_playlists=lambda: [],
            ),
        )

        self.assertEqual(services.get_message_track(12), {"url": "track.sap"})
        self.assertIsNone(services.get_message_track(99))
