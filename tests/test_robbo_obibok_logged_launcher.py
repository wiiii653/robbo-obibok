import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import robbo_obibok_logged_launcher as logged_launcher


class RunBotLoggedTests(unittest.TestCase):
    def test_build_logged_launch_command_uses_runtime_env_and_strict_selection(self):
        env = {"DISCORD_BOT_TOKEN": "token", "ROBBO_STRICT_COMPAT": "1"}

        with patch("robbo_obibok_logged_launcher.load_runtime_environment", return_value=env):
            runtime_env, command = logged_launcher.build_logged_launch_command(
                root=Path("/tmp/robbo"),
                env=env,
            )

        self.assertIs(runtime_env, env)
        self.assertEqual(
            command,
            ["/tmp/robbo/venv/bin/python3", "-u", "robbo-obibok-strict.py"],
        )

    def test_run_logged_bot_launches_process_and_returns_exit_code(self):
        popen_calls = []
        Path("/tmp/robbo/bot_output.log")

        class FakeLog:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeProcess:
            pid = 321

            def wait(self):
                return 7

            def terminate(self):
                return None

        with (
            patch(
                "robbo_obibok_logged_launcher.build_logged_launch_command",
                return_value=(
                    {"DISCORD_BOT_TOKEN": "token"},
                    ["/tmp/robbo/venv/bin/python3", "-u", "robbo-obibok.py"],
                ),
            ),
            patch("pathlib.Path.open", return_value=FakeLog()) as open_log,
            patch(
                "robbo_obibok_logged_launcher.subprocess.Popen",
                side_effect=lambda *args, **kwargs: popen_calls.append((args, kwargs)) or FakeProcess(),
            ),
            patch("sys.stdout.flush", lambda: None),
        ):
            exit_code = logged_launcher.run_logged_bot(root=Path("/tmp/robbo"))

        self.assertEqual(exit_code, 7)
        open_log.assert_called_once_with("a", encoding="utf-8")
        self.assertEqual(
            popen_calls[0][0][0],
            ["/tmp/robbo/venv/bin/python3", "-u", "robbo-obibok.py"],
        )
        self.assertEqual(popen_calls[0][1]["cwd"], Path("/tmp/robbo"))
        self.assertEqual(popen_calls[0][1]["env"], {"DISCORD_BOT_TOKEN": "token"})

    def test_run_logged_bot_terminates_on_keyboard_interrupt(self):
        proc = types.SimpleNamespace(pid=11, terminate_called=False)

        def terminate():
            proc.terminate_called = True

        proc.terminate = terminate

        def wait():
            raise KeyboardInterrupt

        proc.wait = wait

        class FakeLog:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with (
            patch(
                "robbo_obibok_logged_launcher.build_logged_launch_command",
                return_value=(
                    {"DISCORD_BOT_TOKEN": "token"},
                    ["/tmp/robbo/venv/bin/python3", "-u", "robbo-obibok.py"],
                ),
            ),
            patch("pathlib.Path.open", return_value=FakeLog()),
            patch("robbo_obibok_logged_launcher.subprocess.Popen", return_value=proc),
            patch("sys.stdout.flush", lambda: None),
        ):
            exit_code = logged_launcher.run_logged_bot(root=Path("/tmp/robbo"))

        self.assertEqual(exit_code, 130)
        self.assertTrue(proc.terminate_called)
