import sys
import types
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_module_bindings import ENTRYPOINT_COMPAT_RUNTIME_BINDINGS
from entrypoint_module_bindings import ENTRYPOINT_DIRECT_EXPORT_BINDINGS
from entrypoint_surface_assembly import (
    EntrypointSurfaceExportAdapter,
    build_entrypoint_compat_registry_attrs,
    build_entrypoint_direct_export_map,
    build_entrypoint_surface_exports,
)
from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES,
    ENTRYPOINT_EXPORT_GRAPH,
)
from entrypoint_surface_assembly import EntrypointModuleSurface


class EntrypointLauncherSurfaceTests(unittest.TestCase):
    def test_surface_resolve_uses_direct_exports_then_whitelisted_fallback(self):
        fallback_calls = []
        surface = EntrypointModuleSurface(
            exports={
                "bot": "bot",
                "single_guild_check": "check",
                "get_guild_id_override": lambda: None,
                "set_guild_id_override": lambda _guild_id: None,
                "_after_stream_end": "after",
                "_switch_collection": "switch",
                "_skip_to_next": "skip",
                "monitor_playback": "monitor",
            },
            resolve_fallback=lambda name: fallback_calls.append(name) or f"fallback:{name}",
        )

        self.assertEqual(surface.resolve("bot"), "bot")
        self.assertEqual(surface.resolve("_skip_to_next"), "skip")
        self.assertEqual(surface.resolve("monitor_playback"), "monitor")
        self.assertEqual(surface.resolve("LOCK_FILE"), "fallback:LOCK_FILE")
        self.assertNotIn("_FLIP_ORDER", ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES)
        self.assertNotIn("_FLIP_SEQ", ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES)
        self.assertNotIn("_LAUNCHER", ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES)
        with self.assertRaises(AttributeError):
            surface.resolve("_FLIP_ORDER")
        with self.assertRaises(AttributeError):
            surface.resolve("_FLIP_SEQ")
        with self.assertRaises(AttributeError):
            surface.resolve("_LAUNCHER")
        with self.assertRaises(AttributeError):
            surface.resolve("some_missing_attr")
        self.assertEqual(fallback_calls, ["LOCK_FILE"])

    def test_surface_builds_compat_registry_attrs_from_binding_specs(self):
        state = types.SimpleNamespace(
            stream_runtime="stream",
            now_playing_deps="np",
            legacy="legacy",
            app="app",
            runtime_registration="registration",
            lock_file="/tmp/lock",
            shutdown_flag="flag",
        )

        registry_attrs = build_entrypoint_compat_registry_attrs(
            state=state,
            guild_id_getter=lambda: 321,
        )

        self.assertEqual(set(registry_attrs), ENTRYPOINT_EXPORT_GRAPH.compat_names)
        self.assertEqual(ENTRYPOINT_COMPAT_RUNTIME_BINDINGS[0].export_name, "GUILD_ID")
        self.assertEqual(registry_attrs["GUILD_ID"](), 321)
        self.assertEqual(registry_attrs["_STREAM_RUNTIME"](), "stream")
        self.assertEqual(registry_attrs["_NOW_PLAYING_DEPS"](), "np")
        self.assertEqual(registry_attrs["_LEGACY"](), "legacy")
        self.assertEqual(registry_attrs["_APP"](), "app")
        self.assertEqual(registry_attrs["_RUNTIME_REGISTRATION"](), "registration")
        self.assertEqual(registry_attrs["LOCK_FILE"](), "/tmp/lock")
        self.assertEqual(registry_attrs["_shutdown_flag"](), "flag")
        self.assertFalse(set(registry_attrs) & ENTRYPOINT_EXPORT_GRAPH.direct_names)

    def test_surface_builds_direct_export_map_from_binding_specs(self):
        direct_exports = build_entrypoint_direct_export_map(
            resolve_collection=lambda spec: f"collection:{spec.export_name}:{'.'.join(spec.attr_path)}",
            resolve_runtime=lambda spec: f"runtime:{spec.export_name}",
        )

        self.assertEqual(set(direct_exports), ENTRYPOINT_EXPORT_GRAPH.direct_names)
        self.assertEqual(
            ENTRYPOINT_EXPORT_GRAPH.direct_names,
            frozenset(spec.export_name for spec in ENTRYPOINT_DIRECT_EXPORT_BINDINGS),
        )
        self.assertEqual(
            direct_exports["_skip_to_next"],
            "collection:_skip_to_next:legacy.skip_to_next",
        )
        self.assertEqual(
            direct_exports["_switch_collection"],
            "collection:_switch_collection:service_facade.switch_collection",
        )
        self.assertEqual(
            direct_exports["_after_stream_end"],
            "runtime:_after_stream_end",
        )
        self.assertEqual(
            direct_exports["monitor_playback"],
            "runtime:monitor_playback",
        )
        self.assertFalse(set(direct_exports) & ENTRYPOINT_EXPORT_GRAPH.compat_names)

    def test_surface_builds_cached_exports_from_launcher_contract(self):
        compat_calls = []
        loader = types.SimpleNamespace(
            resolve_legacy=lambda name: {
                "bot": "bot",
                "single_guild_check": "check",
                "get_guild_id_override": "getter",
                "set_guild_id_override": "setter",
                "_STATE": "state",
                "_app_cfg": "cfg",
                "_archive_runtime_config": "archive-cfg",
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            }[name],
            collection_export=lambda spec: (lambda: f"collection:{spec.export_name}"),
            runtime_export=lambda spec: (lambda: f"runtime:{spec.export_name}"),
        )

        exports = build_entrypoint_surface_exports(
            resolver=EntrypointSurfaceExportAdapter(
                loader=loader,
            ),
        )

        self.assertEqual(exports["bot"], "bot")
        self.assertNotIn("_STATE", exports)
        self.assertNotIn("_app_cfg", exports)
        self.assertNotIn("_archive_runtime_config", exports)
        self.assertNotIn("_FLIP_ORDER", exports)
        self.assertNotIn("_FLIP_SEQ", exports)
        self.assertEqual(exports["_skip_to_next"](), "collection:_skip_to_next")
        self.assertEqual(exports["_after_stream_end"](), "runtime:_after_stream_end")
        surface = EntrypointModuleSurface(
            exports=exports,
            resolve_fallback=lambda name: compat_calls.append(name) or f"fallback:{name}",
        )
        self.assertEqual(surface.resolve("bot"), "bot")
        self.assertEqual(surface.resolve("_skip_to_next")(), "collection:_skip_to_next")
        self.assertEqual(surface.resolve("_STATE"), "fallback:_STATE")
        self.assertEqual(surface.resolve("LOCK_FILE"), "fallback:LOCK_FILE")
        with self.assertRaises(AttributeError):
            surface.resolve("_FLIP_ORDER")
        with self.assertRaises(AttributeError):
            surface.resolve("_FLIP_SEQ")
        self.assertEqual(compat_calls, ["_STATE", "LOCK_FILE"])
