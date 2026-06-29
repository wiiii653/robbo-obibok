import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime_service_facade import RuntimeServiceFacade


class RuntimeServiceFacadeTests(unittest.TestCase):
    def test_stop_all_players_uses_app_service_iterator(self):
        first = object()
        second = object()
        recorded = {}

        def stop_all_players_impl(states, cleanup):
            recorded["states"] = list(states)
            recorded["cleanup"] = cleanup

        facade = RuntimeServiceFacade(
            app_services=types.SimpleNamespace(iter_guild_states=lambda: iter([first, second])),
            blacklist_loader=lambda: {},
            blacklist_filter=lambda tracks, _blacklist, _user_id: tracks,
            logger=types.SimpleNamespace(info=lambda *_args, **_kwargs: None),
            stop_all_players_impl=stop_all_players_impl,
            subsongs=types.SimpleNamespace(
                get_subsongs=lambda _filepath: [],
                has_subsongs=lambda _filepath: False,
                convert_subsong=lambda _filepath, _subsong, _output_path: False,
                subsong_temp_path=lambda _filepath, _subsong: "",
                play_subsong=lambda *_args, **_kwargs: None,
                cleanup_subsong_temp_wavs=lambda _state: None,
            ),
        )

        def cleanup(state):
            return state

        facade.stop_all_players(cleanup)

        self.assertEqual(recorded["states"], [first, second])
        self.assertIs(recorded["cleanup"], cleanup)
