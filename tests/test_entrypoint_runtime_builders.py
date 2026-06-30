import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_app import (
    build_entrypoint_runtime_callbacks,
    build_entrypoint_runtime_initializer,
)
from entrypoint_runtime_surface import (
    EntrypointRuntimeSurface,
    EntrypointRuntimeStateSurface,
    build_runtime_surface,
    build_runtime_state_surface,
    ENTRYPOINT_STABLE_RUNTIME_SURFACE_ALIAS_BINDINGS,
    ENTRYPOINT_STABLE_RUNTIME_SURFACE_BINDINGS,
)
from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_STABLE_ALIAS_SPECS,
    ENTRYPOINT_MODULE_LEGACY_COMPAT_BINDINGS,
    ENTRYPOINT_MODULE_STABLE_BINDINGS,
)
from entrypoint_runtime_tasks import build_entrypoint_runtime_tasks
from tests.test_entrypoint_runtime_fixtures import (
    build_runtime_callback_inputs,
    build_runtime_task_inputs,
)


class EntrypointRuntimeBuilderTests(unittest.TestCase):
    def test_build_entrypoint_runtime_tasks_wires_expected_dependencies(self):
        inputs = build_runtime_task_inputs()

        runtime_tasks = build_entrypoint_runtime_tasks(
            bot="bot",
            support=inputs.support,
            app_cfg_getter=inputs.app_cfg_getter,
            component_access=inputs.component_access,
            raw_callbacks=inputs.raw_callbacks,
            compute_timeout_seconds="timeout",
            is_gme_format_path="gme",
            should_advance_after_stop="advance",
            should_confirm_output_drop="drop",
            should_disconnect_for_empty_channel="disconnect",
            should_force_timeout_stop="force",
            should_start_predownload="start_predownload",
            facade=inputs.facade,
            glue=inputs.glue,
        )

        self.assertEqual(runtime_tasks.bot, "bot")
        self.assertIs(runtime_tasks.app_cfg_getter, inputs.app_cfg_getter)
        self.assertIs(runtime_tasks.components, inputs.component_access)
        self.assertEqual(runtime_tasks.state, "state")
        self.assertEqual(runtime_tasks.logger, "logger")
        self.assertEqual(runtime_tasks.pre_download_next, "predownload")
        self.assertEqual(runtime_tasks.skip_to_next, "skip")
        self.assertEqual(runtime_tasks.stop_all_players, "stop_all")
        self.assertEqual(runtime_tasks.ensure_audacious, "ensure")
        self.assertEqual(runtime_tasks.setup_virtual_sink, "sink")

    def test_build_entrypoint_runtime_callbacks_and_initializer_wire_split_builders(self):
        inputs = build_runtime_callback_inputs()

        runtime_callbacks = build_entrypoint_runtime_callbacks(
            raw_callbacks=inputs.raw_callbacks,
            clear_predownload_state="clear_predownload",
            facade=inputs.facade,
            glue=inputs.glue,
            runtime_tasks=inputs.runtime_tasks,
        )

        self.assertEqual(runtime_callbacks.playback.monitor_playback, "monitor")
        self.assertEqual(runtime_callbacks.playback.clear_predownload_state, "clear_predownload")
        self.assertEqual(runtime_callbacks.collection.switch_collection, "switch_collection")
        self.assertEqual(runtime_callbacks.bootstrap.cleanup_orphan_players, "cleanup_orphans")
        self.assertEqual(runtime_callbacks.library.load_user_tracks, "load_tracks")
        self.assertEqual(runtime_callbacks.library.remove_user_track, "remove_track")

        initializer = build_entrypoint_runtime_initializer(
            bot="bot",
            support=inputs.initializer_support,
            status_count_cache={"status": (1.0, 2)},
            flip_order=["asma"],
            flip_seq=["ASMA"],
            validate_runtime_dependencies="validate",
            component_access="components",
            build_playback_handlers="build_handlers",
            register_core_events="register_events",
            register_playback_commands="register_playback",
            register_library_commands="register_library",
            runtime_tasks=inputs.runtime_tasks,
            runtime_callbacks=runtime_callbacks,
        )

        self.assertEqual(initializer.root_dir, "/tmp/root")
        self.assertEqual(initializer.logger, "logger")
        self.assertEqual(initializer.bot, "bot")
        self.assertEqual(initializer.registration_hooks.health_watchdog, "watchdog")
        self.assertEqual(initializer.registration_hooks.fetch_metadata_background, "fetch_metadata")
        self.assertIs(initializer.callbacks, runtime_callbacks)


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
        surface = EntrypointRuntimeSurface(bindings=bindings, alias_bindings=alias_bindings)

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

        surface = build_runtime_surface(
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

    def test_stable_runtime_surface_rejects_non_stable_names(self):
        surface = EntrypointRuntimeSurface(
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
