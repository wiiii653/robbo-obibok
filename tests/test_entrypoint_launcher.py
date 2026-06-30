import importlib.util
import sys
import types
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_module_bindings import (
    ENTRYPOINT_EXPORT_GRAPH,
    ENTRYPOINT_EXECUTABLE_DICT_ATTR_NAMES,
    is_supported_executable_attr,
    supported_executable_dict_attrs,
)
from tests.test_support import install_discord_stubs
from tests.test_entrypoint_launcher_fixtures import build_fake_launcher_module


install_discord_stubs()


class EntrypointLauncherTests(unittest.TestCase):
    @staticmethod
    def _load_entrypoint_module(module_name: str):
        sys.modules.pop("robbo_obibok_runtime", None)
        module_path = ROOT / "robbo-obibok.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_launcher_import_defers_executable_assembly_until_first_use(self):
        runtime_app = types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token"))
        fake_module = build_fake_launcher_module(
            runtime_app=runtime_app,
            init_calls=[],
            compat_calls=[],
            bot_calls=[],
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module) as build_module:
            module = self._load_entrypoint_module("robbo_obibok_test_lazy_import")
            self.assertIsNone(module._ASSEMBLY)
            self.assertNotIn("_LAUNCHER", module.__dict__)
            self.assertNotIn("_BINDINGS", module.__dict__)
            build_module.assert_not_called()
            self.assertEqual(module.monitor_playback(), "monitor")
            build_module.assert_called_once()

    def test_launcher_initialize_runtime_caches_app_and_getattr_uses_compat(self):
        runtime_app = types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token"))
        init_calls = []
        compat_calls = []
        bot_calls = []

        fake_module = build_fake_launcher_module(
            runtime_app=runtime_app,
            init_calls=init_calls,
            compat_calls=compat_calls,
            bot_calls=bot_calls,
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            module = self._load_entrypoint_module("robbo_obibok_test_module")
            first_app = module.initialize_runtime()
            second_app = module.initialize_runtime()
            bindings = module._BINDINGS

            self.assertIs(first_app, runtime_app)
            self.assertIs(second_app, runtime_app)
            self.assertEqual(init_calls, ["init"])
            self.assertEqual(module.BOT_TOKEN, "runtime-token")
            self.assertNotIn("bot", module.__dict__)
            self.assertIs(module.bot, bindings["bot"])
            self.assertEqual(bindings["bot"].ping(), "pong")
            self.assertEqual(bot_calls, ["ping"])
            self.assertEqual(module.LOCK_FILE, "resolved:LOCK_FILE")
            self.assertEqual(compat_calls, ["LOCK_FILE"])

    def test_launcher_unknown_attr_fails_closed(self):
        fake_module = build_fake_launcher_module(
            runtime_app=types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            init_calls=[],
            compat_calls=[],
            bot_calls=[],
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            module = self._load_entrypoint_module("robbo_obibok_test_unknown_attr")

        with self.assertRaises(AttributeError):
            _ = module.some_missing_attr

    def test_launcher_binds_common_legacy_names_without_compat_fallback(self):
        runtime_app = types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token"))
        init_calls = []
        compat_calls = []
        bot_calls = []

        fake_module = build_fake_launcher_module(
            runtime_app=runtime_app,
            init_calls=init_calls,
            compat_calls=compat_calls,
            bot_calls=bot_calls,
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            module = self._load_entrypoint_module("robbo_obibok_test_bound_names")
            bindings = module._BINDINGS
            for name in ENTRYPOINT_EXPORT_GRAPH.dynamic_names():
                self.assertNotIn(name, module.__dict__)
                self.assertIs(getattr(module, name), bindings[name])
            self.assertIsNone(bindings["get_guild_id_override"]())
            bindings["set_guild_id_override"](123)
            self.assertIsNotNone(module.state)
            self.assertIsInstance(module.flip_order, list)
            self.assertIsInstance(module.flip_seq, list)
            self.assertIsNot(module.flip_order, module.COLLECTION_FLIP_ORDER)
            self.assertIsNot(module.flip_seq, module.COLLECTION_FLIP_SEQ)
            self.assertEqual(module.app_config().bot_token, "cfg-token")
            self.assertIsInstance(module.archive_runtime_config(), types.SimpleNamespace)
            self.assertEqual(bindings["_skip_to_next"](), "skip")
            self.assertEqual(bindings["_cleanup_orphan_players"](), "cleanup")
            self.assertEqual(bindings["_stop_all_players"](), "stop")
            self.assertEqual(bindings["_auto_play_after_switch"](), "auto")
            self.assertEqual(bindings["_play_subsong"](), "subsong")
            self.assertEqual(bindings["_cleanup_subsong_temp_wavs"](), "cleanup_wavs")
            self.assertEqual(bindings["_after_stream_end"](1, None, 2), (1, None, 2))
            self.assertEqual(bindings["_switch_collection"]("ctx", "hvsc", flip_seq=["HVSC"]), ("ctx", "hvsc", ["HVSC"]))
            self.assertEqual(compat_calls, [])

    def test_launcher_binding_map_matches_module_exports(self):
        compat_calls = []
        fake_module = build_fake_launcher_module(
            runtime_app=types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            init_calls=[],
            compat_calls=compat_calls,
            bot_calls=[],
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            module = self._load_entrypoint_module("robbo_obibok_test_binding_map")
            self.assertEqual(
                set(module._BINDINGS),
                ENTRYPOINT_EXPORT_GRAPH.bound_names(),
            )
            self.assertIs(module.bot, module._BINDINGS["bot"])
            self.assertIs(module._skip_to_next, module._BINDINGS["_skip_to_next"])
            self.assertIs(module.monitor_playback, module._BINDINGS["monitor_playback"])
            self.assertTrue(is_supported_executable_attr("LOCK_FILE"))
            self.assertNotIn("LOCK_FILE", module._BINDINGS)
            self.assertEqual(module.LOCK_FILE, "resolved:LOCK_FILE")
            self.assertEqual(compat_calls, ["LOCK_FILE"])

    def test_launcher_exports_managed_runtime_helpers_and_internal_wiring(self):
        fake_module = build_fake_launcher_module(
            runtime_app=types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            init_calls=[],
            compat_calls=[],
            bot_calls=[],
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            module = self._load_entrypoint_module("robbo_obibok_test_export_surface")

            managed_attrs = supported_executable_dict_attrs(module.__dict__)

            self.assertTrue(managed_attrs.issubset(ENTRYPOINT_EXECUTABLE_DICT_ATTR_NAMES))
            self.assertTrue(
                {
                    "initialize_runtime",
                    "graceful_shutdown",
                    "handle_signal",
                    "main",
                    "__getattr__",
                }.issubset(managed_attrs)
            )
            self.assertNotIn("_ASSEMBLY", module.__dict__)
            self.assertNotIn("_BINDINGS", module.__dict__)

            module.initialize_runtime()
            managed_attrs = supported_executable_dict_attrs(module.__dict__)
            self.assertEqual(
                managed_attrs,
                {"initialize_runtime", "graceful_shutdown", "handle_signal", "main", "__getattr__"},
            )

    def test_launcher_startup_smoke_covers_runtime_bound_exports_and_compat_resolution(self):
        runtime_app = types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token"))
        init_calls = []
        compat_calls = []
        bot_calls = []

        fake_module = build_fake_launcher_module(
            runtime_app=runtime_app,
            init_calls=init_calls,
            compat_calls=compat_calls,
            bot_calls=bot_calls,
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            module = self._load_entrypoint_module("robbo_obibok_test_startup_smoke")
            app = module.initialize_runtime()

            self.assertIs(app, runtime_app)
            self.assertEqual(init_calls, ["init"])
            self.assertEqual(module.BOT_TOKEN, "runtime-token")
            self.assertTrue(ENTRYPOINT_EXPORT_GRAPH.bound_names().issubset(set(module._BINDINGS)))
            self.assertEqual(module.bot.ping(), "pong")
            self.assertIsNotNone(module.state)
            self.assertEqual(module.app_config().bot_token, "cfg-token")
            self.assertIsInstance(module.archive_runtime_config(), types.SimpleNamespace)
            self.assertIn("asma", module.flip_order)
            self.assertTrue(any("ASMA" in item for item in module.flip_seq))
            self.assertEqual(module._skip_to_next(), "skip")
            self.assertEqual(module.monitor_playback(), "monitor")
            self.assertEqual(module.fetch_metadata_background(), "metadata")
            self.assertEqual(module.health_watchdog(), "watchdog")
            self.assertEqual(module.LOCK_FILE, "resolved:LOCK_FILE")
            self.assertEqual(bot_calls, ["ping"])
            self.assertEqual(compat_calls, ["LOCK_FILE"])

    def test_launcher_exposes_only_stable_state_config_names(self):
        fake_module = build_fake_launcher_module(
            runtime_app=types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            init_calls=[],
            compat_calls=[],
            bot_calls=[],
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            module = self._load_entrypoint_module("robbo_obibok_test_legacy_compat_exports")

        for name in ("_STATE", "_app_cfg", "_archive_runtime_config", "_FLIP_ORDER", "_FLIP_SEQ"):
            with self.assertRaises(AttributeError):
                getattr(module, name)
        self.assertIsNotNone(module.state)
        self.assertIsNotNone(module.app_config())
        self.assertIsNotNone(module.archive_runtime_config())
        self.assertIn("asma", module.flip_order)
        self.assertTrue(any("ASMA" in item for item in module.flip_seq))

    def test_launcher_does_not_introduce_unmanaged_bound_globals(self):
        fake_module = build_fake_launcher_module(
            runtime_app=types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            init_calls=[],
            compat_calls=[],
            bot_calls=[],
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            module = self._load_entrypoint_module("robbo_obibok_test_unmanaged_globals")

        binding_value_ids = {id(value) for value in module._BINDINGS.values()}
        mirrored_binding_names = {
            name
            for name, value in module.__dict__.items()
            if name != "_BINDINGS" and id(value) in binding_value_ids
        }
        self.assertEqual(
            mirrored_binding_names,
            set(),
        )

    def test_entrypoint_script_stays_thin_and_delegates_public_helpers_to_runtime_module(self):
        runtime_module = types.SimpleNamespace(
            initialize_runtime=object(),
            graceful_shutdown=object(),
            handle_signal=object(),
            main=object(),
            main_strict=object(),
            selected_main=object(),
        )
        module_path = ROOT / "robbo-obibok.py"
        spec = importlib.util.spec_from_file_location("robbo_obibok_test_entrypoint_thin", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None

        with patch.dict(sys.modules, {"robbo_obibok_runtime": runtime_module}):
            spec.loader.exec_module(module)

        self.assertIs(module.initialize_runtime, runtime_module.initialize_runtime)
        self.assertIs(module.graceful_shutdown, runtime_module.graceful_shutdown)
        self.assertIs(module.handle_signal, runtime_module.handle_signal)
        self.assertIs(module.main, runtime_module.main)
        self.assertIs(module.main_strict, runtime_module.main_strict)
        self.assertIs(module.selected_main, runtime_module.selected_main)
        self.assertNotIn("BOT_TOKEN", module.__dict__)
