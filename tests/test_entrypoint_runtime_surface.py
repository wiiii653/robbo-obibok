import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_runtime_surface import EntrypointStableRuntimeSurface
from entrypoint_runtime_surface import EntrypointCompatRuntimeSurface
from entrypoint_runtime_surface import EntrypointRuntimeStateSurface
from entrypoint_runtime_surface import build_compat_runtime_surface
from entrypoint_runtime_surface import build_runtime_state_surface
from entrypoint_runtime_surface import build_stable_runtime_surface
from entrypoint_runtime_surface import ENTRYPOINT_COMPAT_RUNTIME_SURFACE_BINDINGS
from entrypoint_runtime_surface import ENTRYPOINT_STABLE_RUNTIME_SURFACE_ALIAS_BINDINGS
from entrypoint_runtime_surface import ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS
from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS,
    ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS,
    ENTRYPOINT_MODULE_STABLE_BINDINGS,
)


class EntrypointRuntimeSurfaceTests(unittest.TestCase):
    def test_stable_runtime_surface_bindings_are_declared_once(self):
        self.assertEqual(
            [spec.export_name for spec in ENTRYPOINT_MODULE_STABLE_BINDINGS],
            [spec.binding_name for spec in ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS],
        )
        self.assertEqual(
            [spec.binding_name for spec in ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS],
            [
                "bot",
                "single_guild_check",
                "get_guild_id_override",
                "set_guild_id_override",
            ],
        )
        self.assertEqual(
            [spec.export_name for spec in ENTRYPOINT_MODULE_STABLE_BINDINGS],
            [
                "bot",
                "single_guild_check",
                "get_guild_id_override",
                "set_guild_id_override",
            ],
        )
        self.assertEqual(
            [spec.export_name for spec in ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS],
            [spec.binding_name for spec in ENTRYPOINT_STABLE_RUNTIME_SURFACE_ALIAS_BINDINGS],
        )
        self.assertEqual(
            [spec.export_name for spec in ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS],
            [spec.binding_name for spec in ENTRYPOINT_COMPAT_RUNTIME_SURFACE_BINDINGS],
        )
        self.assertEqual(
            [(spec.alias_name, spec.binding_name) for spec in ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS],
            [(spec.method_name, spec.binding_name) for spec in ENTRYPOINT_STABLE_RUNTIME_SURFACE_ALIAS_BINDINGS],
        )
        self.assertEqual(
            [(spec.alias_name, spec.binding_name) for spec in ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS],
            [
                ("state", "_STATE"),
                ("app_config", "_app_cfg"),
                ("archive_runtime_config", "_archive_runtime_config"),
                ("flip_order", "_FLIP_ORDER"),
                ("flip_seq", "_FLIP_SEQ"),
            ],
        )

    def test_stable_runtime_surface_exposes_typed_binding_accessors(self):
        bindings = {
            "bot": "bot",
            "single_guild_check": "check",
            "get_guild_id_override": "getter",
            "set_guild_id_override": "setter",
        }
        alias_bindings = {
            "_STATE": "state",
            "_app_cfg": "cfg",
            "_archive_runtime_config": "archive",
            "_FLIP_ORDER": ["asma"],
            "_FLIP_SEQ": ["ASMA"],
        }
        surface = EntrypointStableRuntimeSurface(bindings=bindings, alias_bindings=alias_bindings)

        self.assertEqual(surface.bot(), "bot")
        self.assertEqual(surface.single_guild_check(), "check")
        self.assertEqual(surface.get_guild_id_override(), "getter")
        self.assertEqual(surface.set_guild_id_override(), "setter")
        self.assertEqual(surface.state(), "state")
        self.assertEqual(surface.app_config(), "cfg")
        self.assertEqual(surface.archive_runtime_config(), "archive")
        self.assertEqual(surface.flip_order(), ["asma"])
        self.assertEqual(surface.flip_seq(), ["ASMA"])
        self.assertEqual(surface.resolve("bot"), "bot")
        self.assertEqual(surface.resolve_alias("state"), "state")
        self.assertEqual(surface.resolve_alias("app_config"), "cfg")
        with self.assertRaises(AttributeError):
            surface.resolve("_STATE")

    def test_build_stable_runtime_surface_supports_binding_subset(self):
        source = {
            "bot": "bot",
        }
        alias_source = {
            "_STATE": "state",
            "_app_cfg": "cfg",
            "_archive_runtime_config": "archive",
        }

        surface = build_stable_runtime_surface(
            source,
            resolver=source.__getitem__,
            binding_names={"bot"},
            alias_source=alias_source,
            alias_resolver=alias_source.__getitem__,
        )

        self.assertEqual(surface.bot(), "bot")
        self.assertEqual(surface.state(), "state")
        self.assertEqual(surface.app_config(), "cfg")
        self.assertEqual(surface.archive_runtime_config(), "archive")

    def test_runtime_state_surface_dereferences_config_cells(self):
        state = object()
        app_config = object()
        archive_runtime_config = object()

        surface = EntrypointRuntimeStateSurface(
            bindings={
                "_STATE": state,
                "_app_cfg": lambda: app_config,
                "_archive_runtime_config": lambda: archive_runtime_config,
            }
        )

        self.assertIs(surface.state(), state)
        self.assertIs(surface.app_config(), app_config)
        self.assertIs(surface.archive_runtime_config(), archive_runtime_config)

    def test_compat_runtime_surface_exposes_legacy_binding_names(self):
        surface = EntrypointCompatRuntimeSurface(
            bindings={
                "_STATE": "state",
                "_app_cfg": "cfg",
                "_archive_runtime_config": "archive",
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            }
        )

        self.assertEqual(surface.resolve("_STATE"), "state")
        self.assertEqual(surface.resolve("_app_cfg"), "cfg")
        self.assertEqual(surface.resolve("_FLIP_ORDER"), ["asma"])
        with self.assertRaises(AttributeError):
            surface.resolve("bot")

    def test_build_compat_runtime_surface_uses_legacy_binding_contract(self):
        source = {
            "_STATE": "state",
            "_app_cfg": "cfg",
            "_archive_runtime_config": "archive",
            "_FLIP_ORDER": ["asma"],
            "_FLIP_SEQ": ["ASMA"],
        }

        surface = build_compat_runtime_surface(
            source,
            resolver=source.__getitem__,
        )

        self.assertEqual(surface.resolve("_STATE"), "state")
        self.assertEqual(surface.resolve("_archive_runtime_config"), "archive")

    def test_build_runtime_state_surface_uses_narrow_typed_contract(self):
        state = object()
        app_config = object()
        archive_runtime_config = object()
        source = {
            "_STATE": state,
            "_app_cfg": lambda: app_config,
            "_archive_runtime_config": lambda: archive_runtime_config,
        }

        surface = build_runtime_state_surface(
            source,
            resolver=source.__getitem__,
        )

        self.assertIs(surface.state(), state)
        self.assertIs(surface.app_config(), app_config)
        self.assertIs(surface.archive_runtime_config(), archive_runtime_config)

    def test_stable_runtime_surface_rejects_non_stable_names(self):
        surface = EntrypointStableRuntimeSurface(
            bindings={
                "bot": "bot",
                "single_guild_check": "check",
                "get_guild_id_override": "getter",
                "set_guild_id_override": "setter",
                "monitor_playback": "monitor",
            },
            alias_bindings={
                "_STATE": "state",
                "_app_cfg": "cfg",
                "_archive_runtime_config": "archive",
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            },
        )

        with self.assertRaises(AttributeError):
            surface.resolve("monitor_playback")
        with self.assertRaises(AttributeError):
            surface.resolve_alias("monitor_playback")
