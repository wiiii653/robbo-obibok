import sys
import types
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_app import EntrypointCompat
from entrypoint_module import build_entrypoint_exports
from tests.test_support import install_discord_stubs


install_discord_stubs()

from entrypoint_module import build_entrypoint_module
from tests.test_entrypoint_module_fixtures import (
    build_fake_module_bootstrap,
    build_fake_module_deps,
    build_fake_module_support,
)


class EntrypointModuleSurfaceTests(unittest.TestCase):
    def _module_deps(self):
        return build_fake_module_deps()

    def test_build_entrypoint_module_wires_support_bot_app_and_exports(self):
        support = build_fake_module_support()
        bootstrap = build_fake_module_bootstrap(support=support)
        fake_app = types.SimpleNamespace()
        exports = {"monitor_playback": object()}

        with (
            patch("entrypoint_module.build_entrypoint_module_bootstrap", return_value=bootstrap),
            patch("entrypoint_module.build_module_component_deps", return_value=lambda: object()),
            patch("entrypoint_module.build_module_raw_callbacks", return_value=object()),
            patch("entrypoint_module.build_entrypoint_app", return_value=fake_app),
            patch("entrypoint_module.build_entrypoint_exports", return_value=exports),
        ):
            module = build_entrypoint_module(
                module_path="/tmp/robbo-obibok.py",
                logger_name="robbo-obibok",
                load_last_collection=lambda _path: None,
                save_last_collection=lambda _path, _mode: None,
                atomic_json_write=lambda _path, _data, _logger: None,
                command_prefix=lambda _bot, _message: "!",
                deps=self._module_deps(),
            )

        self.assertIs(module.support, support)
        self.assertIs(module.bot, bootstrap.bot)
        self.assertIs(module.app, fake_app)
        self.assertIs(module.exports, exports)
        self.assertTrue(callable(module.single_guild_check))

    def test_entrypoint_compat_and_exports_expose_expected_hooks(self):
        calls = []
        app = types.SimpleNamespace(
            ensure_components=lambda: calls.append("ensure"),
            glue=types.SimpleNamespace(
                after_stream_end=lambda guild_id, error, source_id: (guild_id, error, source_id),
                apply_queue_state=lambda state, queue_state: ("applied", state, queue_state),
                place_track_in_queue=lambda queue, url: (queue, 0),
                queue_position=lambda state: (0, 1),
                cancel_monitor=lambda state: None,
                pre_download_next=lambda state: None,
                start_targeted_playback_session=lambda ctx, state, url: True,
                play_via_audacious=lambda state, path, current_path=None: None,
                send_now_playing_embed=lambda *args, **kwargs: None,
            ),
            runtime_tasks=types.SimpleNamespace(
                monitor_playback=lambda *_args, **_kwargs: None,
                fetch_metadata_background=lambda: None,
                health_watchdog=lambda: None,
            ),
        )
        exports = build_entrypoint_exports(app)
        self.assertIn("_after_stream_end", exports)
        self.assertIn("monitor_playback", exports)

        state = types.SimpleNamespace(
            stream_runtime="stream",
            now_playing_deps="np",
            legacy=types.SimpleNamespace(
                skip_to_next="skip",
                cleanup_orphan_players="cleanup",
                stop_all_players="stop",
                auto_play_after_switch="auto",
                play_subsong="subsong",
            ),
            app="app",
            runtime_registration="reg",
            lock_file="/tmp/lock",
            shutdown_flag="flag",
            service_facade=types.SimpleNamespace(
                switch_collection="switch",
                cleanup_subsong_temp_wavs="cleanup_wavs",
            ),
        )
        compat = EntrypointCompat(
            state=state,
            ensure_components=lambda: calls.append("compat"),
            guild_id_getter=lambda: 123,
        )
        self.assertEqual(compat.resolve("GUILD_ID"), 123)
        with self.assertRaises(AttributeError):
            compat.resolve("_switch_collection")
        self.assertEqual(calls, [])
