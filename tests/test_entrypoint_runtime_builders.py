import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_runtime_callback_builders import (
    build_entrypoint_runtime_callbacks,
    build_entrypoint_runtime_initializer,
)
from entrypoint_runtime_task_builders import build_entrypoint_runtime_tasks
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
        self.assertEqual(runtime_callbacks.library, "library_callbacks")

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
