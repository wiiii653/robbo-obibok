import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_support import install_discord_stubs

install_discord_stubs()

from entrypoint_module_bindings import (
    ALLOW_DEPRECATED,
    ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES,
)


class RobboObibokRuntimeTests(unittest.TestCase):
    @staticmethod
    def _load_runtime_module():
        sys.modules.pop("robbo_obibok_runtime", None)
        return importlib.import_module("robbo_obibok_runtime")

    @staticmethod
    def _build_fake_assembly(*, init_calls=None, compat_calls=None, signal_calls=None):
        init_calls = [] if init_calls is None else init_calls
        compat_calls = [] if compat_calls is None else compat_calls
        signal_calls = [] if signal_calls is None else signal_calls
        runtime = types.SimpleNamespace(
            initialize_runtime=lambda: init_calls.append("init")
            or types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            bot_token=lambda: "runtime-token",
            graceful_shutdown=lambda: None,
            handle_signal=lambda signum, frame: signal_calls.append((signum, frame)),
            lock_file=lambda: "/tmp/lock",
        )
        return types.SimpleNamespace(
            providers=types.SimpleNamespace(),
            deps=object(),
            launcher=types.SimpleNamespace(
                loader=types.SimpleNamespace(
                    ensure_module=lambda: None,
                    resolve=lambda name: compat_calls.append(name) or f"resolved:{name}",
                ),
                runtime=runtime,
            ),
            legacy_resolve=lambda name: compat_calls.append(name) or f"resolved:{name}",
            surface=types.SimpleNamespace(resolve=lambda name: compat_calls.append(name) or f"resolved:{name}"),
            bindings={
                "bot": types.SimpleNamespace(ping=lambda: "pong"),
                "single_guild_check": lambda _ctx: True,
                "get_guild_id_override": lambda: None,
                "set_guild_id_override": lambda _guild_id: None,
                "_skip_to_next": lambda: "skip",
                "monitor_playback": lambda: "monitor",
            },
            compat_bindings={
                "_STATE": object(),
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(),
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            },
            compat_policy=ALLOW_DEPRECATED,
        )

    def test_import_keeps_runtime_wiring_lazy(self):
        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
        ) as build_assembly:
            module = self._load_runtime_module()

        self.assertEqual(module.BOT_TOKEN, "")
        self.assertIsNone(module._ASSEMBLY)
        self.assertNotIn("_BINDINGS", module.__dict__)
        self.assertNotIn("_LAUNCHER", module.__dict__)
        build_assembly.assert_not_called()

    def test_initialize_runtime_caches_assembly_and_updates_token(self):
        init_calls = []
        compat_calls = []
        assembly = self._build_fake_assembly(init_calls=init_calls, compat_calls=compat_calls)

        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
            return_value=assembly,
        ):
            module = self._load_runtime_module()
            first_app = module.initialize_runtime()
            second_app = module.initialize_runtime()

        self.assertEqual(init_calls, ["init"])
        self.assertIs(first_app, second_app)
        self.assertIs(module._ASSEMBLY, assembly)
        self.assertEqual(module.BOT_TOKEN, "runtime-token")
        self.assertEqual(module.monitor_playback(), "monitor")
        self.assertEqual(module.LOCK_FILE, "resolved:LOCK_FILE")
        self.assertEqual(compat_calls, ["LOCK_FILE"])

    def test_runtime_stable_attr_contract_is_explicit(self):
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES,
            {
                "BOT_TOKEN",
                "_ASSEMBLY",
                "_BINDINGS",
                "_COMPAT_BINDINGS",
                "__getattr__",
                "app_config",
                "archive_runtime_config",
                "bot",
                "flip_order",
                "flip_seq",
                "get_guild_id_override",
                "graceful_shutdown",
                "handle_signal",
                "initialize_runtime",
                "main",
                "set_guild_id_override",
                "single_guild_check",
                "state",
            },
        )

    def test_runtime_exposes_internal_views_without_mirroring_globals(self):
        compat_calls = []
        assembly = self._build_fake_assembly(compat_calls=compat_calls)

        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
            return_value=assembly,
        ):
            module = self._load_runtime_module()
            self.assertIs(module._BINDINGS, assembly.bindings)
            self.assertIs(module._COMPAT_BINDINGS, assembly.compat_bindings)
            for name in ("_LAUNCHER", "_MODULE_DEPS", "_SURFACE", "_LEGACY_RESOLVE"):
                with self.assertRaises(AttributeError):
                    getattr(module, name)

        self.assertNotIn("_BINDINGS", module.__dict__)
        self.assertNotIn("_COMPAT_BINDINGS", module.__dict__)
        self.assertNotIn("_LAUNCHER", module.__dict__)
        self.assertNotIn("_MODULE_DEPS", module.__dict__)
        self.assertNotIn("_SURFACE", module.__dict__)
        self.assertNotIn("_LEGACY_RESOLVE", module.__dict__)
        self.assertEqual(module.bot.ping(), "pong")
        self.assertEqual(module._skip_to_next(), "skip")
        self.assertEqual(module.LOCK_FILE, "resolved:LOCK_FILE")
        self.assertEqual(compat_calls, ["LOCK_FILE"])
        with self.assertRaises(AttributeError):
            _ = module._FLIP_ORDER
        with self.assertRaises(AttributeError):
            _ = module._FLIP_SEQ

    def test_runtime_rejects_private_direct_helper_attrs_from_module_surface(self):
        assembly = self._build_fake_assembly()
        assembly.bindings["_ensure_entrypoint_components"] = "hidden-helper"

        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
            return_value=assembly,
        ):
            module = self._load_runtime_module()
            self.assertEqual(module._BINDINGS["_ensure_entrypoint_components"], "hidden-helper")
            with self.assertRaises(AttributeError):
                _ = module._ensure_entrypoint_components

    def test_runtime_can_disable_deprecated_internal_attr_shims(self):
        assembly = self._build_fake_assembly()

        with (
            patch(
                "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
                return_value=assembly,
            ),
        ):
            assembly.compat_policy = ALLOW_DEPRECATED
            module = self._load_runtime_module()
            for name in ("_LAUNCHER", "_SURFACE", "_MODULE_DEPS", "_LEGACY_RESOLVE"):
                with self.assertRaises(AttributeError):
                    getattr(module, name)

    def test_runtime_does_not_expose_removed_legacy_compat_attrs(self):
        assembly = self._build_fake_assembly()

        with (
            patch(
                "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
                return_value=assembly,
            ),
        ):
            module = self._load_runtime_module()
            self.assertIs(module.state, assembly.compat_bindings["_STATE"])
            self.assertEqual(module.app_config().bot_token, "cfg-token")
            self.assertEqual(module.flip_order, ["asma"])
            self.assertEqual(module.flip_seq, ["ASMA"])
            for name in ("_STATE", "_app_cfg", "_archive_runtime_config", "_FLIP_ORDER", "_FLIP_SEQ"):
                with self.assertRaises(AttributeError):
                    getattr(module, name)

    def test_runtime_strict_policy_keeps_stable_aliases_while_removing_legacy_names(self):
        assembly = self._build_fake_assembly()
        assembly.compat_policy = ALLOW_DEPRECATED

        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
            return_value=assembly,
        ):
            module = self._load_runtime_module()
            self.assertIs(module.state, assembly.compat_bindings["_STATE"])
            self.assertEqual(module.app_config().bot_token, "cfg-token")
            self.assertEqual(module.archive_runtime_config(), assembly.compat_bindings["_archive_runtime_config"]())
            self.assertEqual(module.flip_order, ["asma"])
            self.assertEqual(module.flip_seq, ["ASMA"])
            for name in ("_STATE", "_app_cfg", "_archive_runtime_config", "_FLIP_ORDER", "_FLIP_SEQ"):
                with self.assertRaises(AttributeError):
                    getattr(module, name)

    def test_runtime_public_surface_smoke_survives_with_deprecated_internal_shims_disabled(self):
        compat_calls = []
        assembly = self._build_fake_assembly(compat_calls=compat_calls)
        assembly.bindings["fetch_metadata_background"] = lambda: "metadata"
        assembly.bindings["health_watchdog"] = lambda: "watchdog"
        assembly.bindings["_after_stream_end"] = lambda *args: args

        with (
            patch(
                "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
                return_value=assembly,
            ),
        ):
            assembly.compat_policy = ALLOW_DEPRECATED
            module = self._load_runtime_module()
            self.assertEqual(module.initialize_runtime().startup_env.bot_token, "runtime-token")
            self.assertEqual(module.bot.ping(), "pong")
            self.assertTrue(module.single_guild_check(None))
            self.assertIsNone(module.get_guild_id_override())
            module.set_guild_id_override(5)
            self.assertEqual(module.app_config().bot_token, "cfg-token")
            self.assertIs(module.state, assembly.compat_bindings["_STATE"])
            self.assertEqual(module.flip_order, ["asma"])
            self.assertEqual(module.flip_seq, ["ASMA"])
            self.assertEqual(module.fetch_metadata_background(), "metadata")
            self.assertEqual(module.health_watchdog(), "watchdog")
            self.assertEqual(module._skip_to_next(), "skip")
            self.assertEqual(module.LOCK_FILE, "resolved:LOCK_FILE")

    def test_runtime_exposes_stable_non_legacy_aliases(self):
        assembly = self._build_fake_assembly()

        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
            return_value=assembly,
        ):
            module = self._load_runtime_module()
            self.assertIs(module.state, assembly.compat_bindings["_STATE"])
            self.assertEqual(module.app_config().bot_token, "cfg-token")
            self.assertEqual(module.archive_runtime_config(), assembly.compat_bindings["_archive_runtime_config"]())
            self.assertEqual(module.flip_order, ["asma"])
            self.assertEqual(module.flip_seq, ["ASMA"])

    def test_runtime_legacy_compat_attrs_are_removed(self):
        assembly = self._build_fake_assembly()

        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
            return_value=assembly,
        ):
            module = self._load_runtime_module()
            for name in ("_STATE", "_app_cfg", "_archive_runtime_config", "_FLIP_ORDER", "_FLIP_SEQ"):
                with self.assertRaises(AttributeError):
                    getattr(module, name)

    def test_main_delegates_to_run_bot_entrypoint(self):
        signal_calls = []
        assembly = self._build_fake_assembly(signal_calls=signal_calls)
        captured = {}

        def fake_run_bot_entrypoint(**kwargs):
            captured.update(kwargs)
            kwargs["handle_signal"](9, "frame")

        with (
            patch(
                "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
                return_value=assembly,
            ),
            patch("entrypoint_app.run_bot_entrypoint", side_effect=fake_run_bot_entrypoint),
        ):
            module = self._load_runtime_module()
            module.main()

        self.assertIs(captured["bot"], assembly.bindings["bot"])
        self.assertEqual(captured["token_getter"](), "runtime-token")
        self.assertEqual(captured["lock_file_getter"](), "/tmp/lock")
        self.assertEqual(signal_calls, [(9, "frame")])

    def test_main_strict_uses_strict_assembly_builder(self):
        signal_calls = []
        assembly = self._build_fake_assembly(signal_calls=signal_calls)
        assembly.compat_policy = ALLOW_DEPRECATED
        captured = {}

        def fake_run_bot_entrypoint(**kwargs):
            captured.update(kwargs)
            kwargs["initialize_runtime"]()

        with (
            patch(
                "entrypoint_executable_assembly.build_strict_entrypoint_executable_assembly",
                return_value=assembly,
            ),
            patch("entrypoint_app.run_bot_entrypoint", side_effect=fake_run_bot_entrypoint),
        ):
            module = self._load_runtime_module()
            module.main_strict()

        self.assertIs(captured["bot"], assembly.bindings["bot"])
        self.assertEqual(captured["token_getter"](), "runtime-token")
