import asyncio
import sys
import types
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_launcher_state import EntrypointRuntimeController, EntrypointRuntimeStateAccess


class EntrypointLauncherStateTests(unittest.TestCase):
    def test_state_access_initializes_once_and_caches_startup_env(self):
        startup_env = types.SimpleNamespace(bot_token="runtime-token")
        app_instance = types.SimpleNamespace(startup_env=startup_env)
        init_calls = []
        state = types.SimpleNamespace(app=None, startup_env=None)
        app = types.SimpleNamespace(
            runtime_initializer=types.SimpleNamespace(
                initialize_runtime=lambda: init_calls.append("init") or app_instance
            )
        )

        access = EntrypointRuntimeStateAccess(state=state, app=app)

        self.assertIs(access.ensure_initialized(), app_instance)
        self.assertIs(access.ensure_initialized(), app_instance)
        self.assertEqual(init_calls, ["init"])
        self.assertIs(state.startup_env, startup_env)

    def test_runtime_controller_uses_loader_state_and_app_config(self):
        calls = []
        runtime_state = types.SimpleNamespace(
            app=None,
            startup_env=None,
            runtime=types.SimpleNamespace(
                graceful_shutdown=self._shutdown_marker(calls),
                handle_signal=lambda signum, frame: calls.append(("signal", signum, frame)),
            ),
            lock_file="/tmp/lock",
        )
        app_instance = types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token"))
        bindings = types.SimpleNamespace(
            state=types.SimpleNamespace(
                _STATE=runtime_state,
                _APP=types.SimpleNamespace(
                    runtime_initializer=types.SimpleNamespace(
                        initialize_runtime=lambda: calls.append("init") or app_instance
                    )
                ),
            )
        )
        loader = types.SimpleNamespace(
            bootstrap_app=lambda: bindings.state._APP,
            runtime_state_surface=lambda: types.SimpleNamespace(
                state=lambda: runtime_state,
                app_config=lambda: types.SimpleNamespace(bot_token="cfg-token"),
                archive_runtime_config=lambda: types.SimpleNamespace(name="archive"),
            ),
            lock_file=lambda: "/tmp/lock",
        )
        controller = EntrypointRuntimeController(loader=loader)

        self.assertIs(controller.initialize_runtime(), app_instance)
        self.assertEqual(controller.bot_token(), "runtime-token")
        self.assertEqual(controller.lock_file(), "/tmp/lock")
        asyncio.run(controller.graceful_shutdown())
        controller.handle_signal(15, "frame")

        self.assertEqual(calls, ["init", ("shutdown",), ("signal", 15, "frame")])

    def test_runtime_controller_bot_token_falls_back_to_config_before_init(self):
        runtime_state = types.SimpleNamespace(
            app=None,
            startup_env=None,
            runtime=types.SimpleNamespace(
                graceful_shutdown=self._shutdown_marker([]),
                handle_signal=lambda *_args: None,
            ),
            lock_file="/tmp/lock",
        )
        app_instance = types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token"))
        init_calls = []
        bindings = types.SimpleNamespace(
            state=types.SimpleNamespace(
                _STATE=runtime_state,
                _APP=types.SimpleNamespace(
                    runtime_initializer=types.SimpleNamespace(
                        initialize_runtime=lambda: init_calls.append("init") or app_instance
                    )
                ),
            )
        )
        loader = types.SimpleNamespace(
            bootstrap_app=lambda: bindings.state._APP,
            runtime_state_surface=lambda: types.SimpleNamespace(
                state=lambda: runtime_state,
                app_config=lambda: types.SimpleNamespace(bot_token="cfg-token"),
                archive_runtime_config=lambda: types.SimpleNamespace(name="archive"),
            ),
            lock_file=lambda: "/tmp/lock",
        )
        controller = EntrypointRuntimeController(loader=loader)

        self.assertEqual(controller.bot_token(), "cfg-token")
        self.assertIs(controller.initialize_runtime(), app_instance)
        self.assertEqual(controller.bot_token(), "runtime-token")
        self.assertEqual(init_calls, ["init"])

    def _shutdown_marker(self, calls):
        async def _shutdown():
            calls.append(("shutdown",))

        return _shutdown
