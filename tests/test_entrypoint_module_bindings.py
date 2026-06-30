import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_module_bindings import (
    ENTRYPOINT_DIRECT_COLLECTION_BINDINGS,
    ENTRYPOINT_DIRECT_RUNTIME_BINDINGS,
    ENTRYPOINT_PRIVATE_DIRECT_EXPORT_BINDINGS,
    ENTRYPOINT_PUBLIC_DIRECT_EXPORT_BINDINGS,
)
from entrypoint_module_bindings import (
    EntrypointSurfaceAliasSpec,
    ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS,
    ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_PRIVATE_DIRECT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_ATTR_NAMES,
    ENTRYPOINT_EXPORT_GRAPH,
    ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES,
    ENTRYPOINT_MODULE_STABLE_NAMES,
    build_entrypoint_compat_module_bindings,
    ENTRYPOINT_EXECUTABLE_DICT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_HELPER_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_PRIVATE_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_STABLE_INTERNAL_ATTR_NAMES,
    build_entrypoint_stable_module_bindings,
    resolve_compat_binding_attr,
    resolve_bound_entrypoint_module_attr,
    resolve_compat_entrypoint_module_attr,
    is_deprecated_executable_attr,
    is_supported_executable_attr,
    is_stable_executable_attr,
    supported_executable_dict_attrs,
)


class EntrypointModuleBindingsTests(unittest.TestCase):
    @staticmethod
    def _direct_export_names() -> set[str]:
        return {
            spec.export_name
            for spec in ENTRYPOINT_DIRECT_COLLECTION_BINDINGS + ENTRYPOINT_DIRECT_RUNTIME_BINDINGS
            if spec.export_name not in {"_switch_collection", "_after_stream_end"}
        }

    def test_supported_name_sets_cover_runtime_and_module_contract(self):
        all_binding_names = ENTRYPOINT_MODULE_STABLE_NAMES | ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES
        self.assertIn("bot", all_binding_names)
        self.assertIn("_STATE", all_binding_names)
        self.assertIn("_FLIP_ORDER", all_binding_names)
        self.assertEqual(
            ENTRYPOINT_MODULE_STABLE_NAMES,
            frozenset(
                {
                    "bot",
                    "single_guild_check",
                    "get_guild_id_override",
                    "set_guild_id_override",
                }
            ),
        )
        self.assertEqual(
            ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES,
            ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES,
        )
        self.assertIn("_switch_collection", ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES)
        self.assertIn("monitor_playback", ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES)
        self.assertIn("LOCK_FILE", ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES)
        self.assertIn("initialize_runtime", ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES)
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES,
            frozenset({"_STATE", "_app_cfg", "_archive_runtime_config", "_FLIP_ORDER", "_FLIP_SEQ"}),
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES,
            frozenset({"_STATE", "_app_cfg", "_archive_runtime_config"}),
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES,
            frozenset({"_FLIP_ORDER", "_FLIP_SEQ"}),
        )
        self.assertTrue(
            ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES
            <= ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES
        )
        self.assertFalse(
            self._direct_export_names()
            <= ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES
        )
        self.assertTrue(ENTRYPOINT_EXPORT_GRAPH.compat_names <= ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES)
        self.assertIn("_ASSEMBLY", ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES)
        self.assertIn("bot", ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES)
        self.assertTrue(ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_ATTR_NAMES <= ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES)
        self.assertIn("app_config", ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES)
        self.assertIn("state", ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES)
        self.assertFalse(
            ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES
            & ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES
        )
        self.assertIn("_skip_to_next", ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES)
        self.assertIn("LOCK_FILE", ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES)
        self.assertIn("_LAUNCHER", ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES)
        self.assertIn("_skip_to_next", ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES)
        self.assertIn("LOCK_FILE", ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES)
        self.assertIn("_LAUNCHER", ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES)
        self.assertFalse("_STATE" in ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES)
        self.assertFalse("_LAUNCHER" in ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES)

    def test_stable_public_alias_budget_is_explicit(self):
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS,
            (
                EntrypointSurfaceAliasSpec("state", "_STATE"),
                EntrypointSurfaceAliasSpec("app_config", "_app_cfg"),
                EntrypointSurfaceAliasSpec("archive_runtime_config", "_archive_runtime_config"),
                EntrypointSurfaceAliasSpec("flip_order", "_FLIP_ORDER"),
                EntrypointSurfaceAliasSpec("flip_seq", "_FLIP_SEQ"),
            ),
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_ATTR_NAMES,
            frozenset(
                {
                    "state",
                    "app_config",
                    "archive_runtime_config",
                    "flip_order",
                    "flip_seq",
                }
            ),
        )
        self.assertTrue(
            ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_ATTR_NAMES
            <= ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES
        )

    def test_deprecation_budget_sets_are_explicit_and_partitioned(self):
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES,
            frozenset({"_LAUNCHER", "_LEGACY_RESOLVE", "_SURFACE", "_MODULE_DEPS"}),
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES,
            frozenset({"_STATE", "_app_cfg", "_archive_runtime_config"}),
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES,
            frozenset({"_FLIP_ORDER", "_FLIP_SEQ"}),
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES,
            ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES
            | ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES,
        )
        self.assertFalse(
            ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES
            & ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES,
            ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES,
        )
        self.assertFalse(
            ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES
            & ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES
        )
        self.assertTrue(
            ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES
            <= ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES
        )
        self.assertTrue(
            ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES
            <= ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES,
            ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES
            | ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES,
        )
        self.assertIn("monitor_playback", ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES)
        self.assertIn("_ensure_entrypoint_components", ENTRYPOINT_EXECUTABLE_PRIVATE_DIRECT_ATTR_NAMES)
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES,
            frozenset(spec.export_name for spec in ENTRYPOINT_PUBLIC_DIRECT_EXPORT_BINDINGS),
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_PRIVATE_DIRECT_ATTR_NAMES,
            frozenset(spec.export_name for spec in ENTRYPOINT_PRIVATE_DIRECT_EXPORT_BINDINGS),
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_DICT_ATTR_NAMES,
            ENTRYPOINT_EXECUTABLE_HELPER_ATTR_NAMES
            | ENTRYPOINT_EXECUTABLE_STABLE_INTERNAL_ATTR_NAMES
            | ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES
            | ENTRYPOINT_EXECUTABLE_PRIVATE_ATTR_NAMES,
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES,
            ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES | ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES,
        )
        self.assertEqual(
            ENTRYPOINT_EXPORT_GRAPH.dynamic_names(),
            ENTRYPOINT_MODULE_STABLE_NAMES | ENTRYPOINT_EXECUTABLE_PUBLIC_DIRECT_COMPAT_ATTR_NAMES,
        )
        self.assertEqual(
            ENTRYPOINT_EXPORT_GRAPH.bound_names(),
            ENTRYPOINT_MODULE_STABLE_NAMES | ENTRYPOINT_EXPORT_GRAPH.direct_names,
        )
        self.assertEqual(ENTRYPOINT_EXPORT_GRAPH.stable_binding_names, ENTRYPOINT_MODULE_STABLE_NAMES)
        self.assertEqual(
            ENTRYPOINT_EXPORT_GRAPH.legacy_compat_binding_names,
            ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES,
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS,
            (
                EntrypointSurfaceAliasSpec("state", "_STATE"),
                EntrypointSurfaceAliasSpec("app_config", "_app_cfg"),
                EntrypointSurfaceAliasSpec("archive_runtime_config", "_archive_runtime_config"),
                EntrypointSurfaceAliasSpec("flip_order", "_FLIP_ORDER"),
                EntrypointSurfaceAliasSpec("flip_seq", "_FLIP_SEQ"),
            ),
        )

    def test_binding_builders_expose_split_direct_exports(self):
        flip_order = ["asma"]
        flip_seq = ["ASMA"]
        exports = {
            "bot": "bot",
            "single_guild_check": "check",
            "get_guild_id_override": "getter",
            "set_guild_id_override": "setter",
            "_STATE": "state",
            "_app_cfg": "cfg",
            "_archive_runtime_config": "archive-cfg",
            "_FLIP_ORDER": flip_order,
            "_FLIP_SEQ": flip_seq,
            "_after_stream_end": "after",
            "_switch_collection": "switch",
        }
        exports.update({name: f"value:{name}" for name in self._direct_export_names()})
        surface = type(
            "Surface",
            (),
            {
                "export_map": lambda self: {
                    key: value for key, value in exports.items() if key not in ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES
                },
                "resolve": lambda self, name: exports[name],
            },
        )()

        stable_bindings = build_entrypoint_stable_module_bindings(surface)
        compat_bindings = build_entrypoint_compat_module_bindings(surface)

        self.assertEqual(stable_bindings["bot"], "bot")
        self.assertEqual(stable_bindings["_after_stream_end"], "after")
        self.assertEqual(stable_bindings["_switch_collection"], "switch")
        self.assertEqual(compat_bindings["_STATE"], "state")
        self.assertEqual(compat_bindings["_FLIP_ORDER"], ["asma"])
        self.assertEqual(compat_bindings["_FLIP_SEQ"], ["ASMA"])
        self.assertEqual(
            set(stable_bindings),
            ENTRYPOINT_EXPORT_GRAPH.bound_names(),
        )
        for name in self._direct_export_names():
            self.assertEqual(stable_bindings[name], f"value:{name}")
        self.assertEqual(set(compat_bindings), ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES)
        self.assertIsNot(compat_bindings["_FLIP_ORDER"], flip_order)
        self.assertIsNot(compat_bindings["_FLIP_SEQ"], flip_seq)

    def test_stable_and_compat_binding_builders_split_export_classes(self):
        flip_order = ["asma"]
        flip_seq = ["ASMA"]
        exports = {
            "bot": "bot",
            "single_guild_check": "check",
            "get_guild_id_override": "getter",
            "set_guild_id_override": "setter",
            "_STATE": "state",
            "_app_cfg": "cfg",
            "_archive_runtime_config": "archive-cfg",
            "_FLIP_ORDER": flip_order,
            "_FLIP_SEQ": flip_seq,
            "_after_stream_end": "after",
            "_switch_collection": "switch",
        }
        exports.update({name: f"value:{name}" for name in self._direct_export_names()})
        surface = type(
            "Surface",
            (),
            {
                "export_map": lambda self: {
                    key: value for key, value in exports.items() if key not in ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES
                },
                "resolve": lambda self, name: exports[name],
            },
        )()

        stable_bindings = build_entrypoint_stable_module_bindings(surface)
        compat_bindings = build_entrypoint_compat_module_bindings(surface)

        self.assertEqual(set(stable_bindings), ENTRYPOINT_EXPORT_GRAPH.bound_names())
        self.assertEqual(set(compat_bindings), ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES)
        self.assertFalse(ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES & set(stable_bindings))
        self.assertEqual(
            stable_bindings | compat_bindings,
            {
                **stable_bindings,
                **compat_bindings,
            },
        )

    def test_supported_attr_helpers_cover_binding_and_runtime_names(self):
        self.assertTrue(is_supported_executable_attr("bot"))
        self.assertTrue(is_supported_executable_attr("_switch_collection"))
        self.assertTrue(is_supported_executable_attr("initialize_runtime"))
        self.assertTrue(is_supported_executable_attr("LOCK_FILE"))
        self.assertTrue(is_stable_executable_attr("_ASSEMBLY"))
        self.assertTrue(is_stable_executable_attr("_BINDINGS"))
        self.assertTrue(is_stable_executable_attr("_COMPAT_BINDINGS"))
        self.assertTrue(is_stable_executable_attr("bot"))
        self.assertFalse(is_stable_executable_attr("_skip_to_next"))
        self.assertFalse(is_stable_executable_attr("_LAUNCHER"))
        self.assertFalse(is_supported_executable_attr("_ensure_entrypoint_components"))
        self.assertFalse(is_deprecated_executable_attr("_skip_to_next"))
        self.assertTrue(is_deprecated_executable_attr("_LAUNCHER"))
        self.assertFalse(is_deprecated_executable_attr("LOCK_FILE"))
        self.assertFalse(is_deprecated_executable_attr("_STATE"))
        self.assertFalse(is_deprecated_executable_attr("_ASSEMBLY"))
        self.assertFalse(is_supported_executable_attr("some_missing_attr"))

        bindings = {"bot": "bound-bot"}
        self.assertEqual(
            resolve_bound_entrypoint_module_attr(
                "bot",
                bindings=bindings,
            ),
            "bound-bot",
        )
        with self.assertRaises(AttributeError):
            resolve_bound_entrypoint_module_attr(
                "LOCK_FILE",
                bindings=bindings,
            )
        self.assertEqual(
            resolve_compat_entrypoint_module_attr(
                "LOCK_FILE",
                fallback_resolver=lambda name: f"fallback:{name}",
            ),
            "fallback:LOCK_FILE",
        )
        with self.assertRaises(AttributeError):
            resolve_compat_entrypoint_module_attr(
                "bot",
                fallback_resolver=lambda name: f"fallback:{name}",
            )
        with self.assertRaises(AttributeError):
            resolve_bound_entrypoint_module_attr(
                "_ensure_entrypoint_components",
                bindings={"_ensure_entrypoint_components": "hidden"},
            )
        self.assertEqual(
            resolve_compat_binding_attr(
                "_STATE",
                compat_bindings={"_STATE": "legacy-state"},
            ),
            "legacy-state",
        )
        with self.assertRaises(AttributeError):
            resolve_compat_binding_attr(
                "bot",
                compat_bindings={"bot": "bot"},
            )
        with self.assertRaises(AttributeError):
            resolve_compat_entrypoint_module_attr(
                "_STATE",
                fallback_resolver=lambda name: f"fallback:{name}",
            )

        self.assertEqual(
            supported_executable_dict_attrs(
                {
                    "BOT_TOKEN": "",
                    "_BINDINGS": {},
                    "_COMPAT_BINDINGS": {},
                    "_LAUNCHER": object(),
                    "some_impl_name": object(),
                }
            ),
            {"BOT_TOKEN", "_BINDINGS", "_COMPAT_BINDINGS", "_LAUNCHER"},
        )

    def test_supported_executable_attr_contract_is_total_union(self):
        supported_names = ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES | ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES

        self.assertEqual(ENTRYPOINT_EXECUTABLE_SUPPORTED_ATTR_NAMES, supported_names)
        for name in supported_names:
            self.assertTrue(is_supported_executable_attr(name))
        self.assertFalse(is_supported_executable_attr("definitely_not_supported"))

    def test_stable_runtime_surface_is_intentionally_classified(self):
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

    def test_stable_runtime_surface_does_not_admit_new_legacy_prefixed_state_exports(self):
        allowed_prefixed_stable_names = frozenset(
            {
                "__getattr__",
                "_ASSEMBLY",
                "_BINDINGS",
                "_COMPAT_BINDINGS",
            }
        )

        self.assertEqual(
            {name for name in ENTRYPOINT_EXECUTABLE_STABLE_ATTR_NAMES if name.startswith("_")},
            allowed_prefixed_stable_names,
        )

    def test_compat_runtime_surface_is_intentionally_classified(self):
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES,
            {
                "GUILD_ID",
                "LOCK_FILE",
                "_APP",
                "_LEGACY",
                "_NOW_PLAYING_DEPS",
                "_RUNTIME_REGISTRATION",
                "_STREAM_RUNTIME",
                "_after_stream_end",
                "_auto_play_after_switch",
                "_cleanup_orphan_players",
                "_cleanup_subsong_temp_wavs",
                "_play_subsong",
                "_shutdown_flag",
                "_skip_to_next",
                "_stop_all_players",
                "_switch_collection",
                "fetch_metadata_background",
                "health_watchdog",
                "monitor_playback",
            },
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES,
            {
                "_LAUNCHER",
                "_LEGACY_RESOLVE",
                "_MODULE_DEPS",
                "_SURFACE",
            },
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES,
            {
                "GUILD_ID",
                "LOCK_FILE",
                "_APP",
                "_LEGACY",
                "_LAUNCHER",
                "_LEGACY_RESOLVE",
                "_MODULE_DEPS",
                "_NOW_PLAYING_DEPS",
                "_RUNTIME_REGISTRATION",
                "_STREAM_RUNTIME",
                "_SURFACE",
                "_after_stream_end",
                "_auto_play_after_switch",
                "_cleanup_orphan_players",
                "_cleanup_subsong_temp_wavs",
                "_play_subsong",
                "_shutdown_flag",
                "_skip_to_next",
                "_stop_all_players",
                "_switch_collection",
                "fetch_metadata_background",
                "health_watchdog",
                "monitor_playback",
            },
        )

    def test_compat_contract_audit_is_partitioned_and_total(self):
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES,
            ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES
            | ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES,
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES,
            ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES
            | ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES,
        )
        self.assertEqual(
            ENTRYPOINT_EXECUTABLE_COMPAT_ATTR_NAMES - ENTRYPOINT_EXECUTABLE_FALLBACK_ATTR_NAMES,
            ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES,
        )
        self.assertFalse(
            ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES
            & ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES
        )
        self.assertFalse(
            ENTRYPOINT_EXECUTABLE_LEGACY_STABLE_COMPAT_ATTR_NAMES
            & ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES
        )
        self.assertFalse(
            ENTRYPOINT_EXECUTABLE_RUNTIME_COMPAT_ATTR_NAMES
            & ENTRYPOINT_EXECUTABLE_INTERNAL_COMPAT_ATTR_NAMES
        )

    def test_compat_binding_builder_can_use_explicit_legacy_resolver(self):
        flip_order = ["asma"]
        flip_seq = ["ASMA"]
        source = {
            "_STATE": "state",
            "_app_cfg": "cfg",
            "_archive_runtime_config": "archive",
        }
        resolved = []

        compat_bindings = build_entrypoint_compat_module_bindings(
            source,
            resolver=lambda name: resolved.append(name) or {
                "_FLIP_ORDER": flip_order,
                "_FLIP_SEQ": flip_seq,
            }[name],
        )

        self.assertEqual(compat_bindings["_STATE"], "state")
        self.assertEqual(compat_bindings["_app_cfg"], "cfg")
        self.assertEqual(compat_bindings["_archive_runtime_config"], "archive")
        self.assertEqual(compat_bindings["_FLIP_ORDER"], ["asma"])
        self.assertEqual(compat_bindings["_FLIP_SEQ"], ["ASMA"])
        self.assertEqual(resolved, ["_FLIP_ORDER", "_FLIP_SEQ"])
        self.assertIsNot(compat_bindings["_FLIP_ORDER"], flip_order)
        self.assertIsNot(compat_bindings["_FLIP_SEQ"], flip_seq)
