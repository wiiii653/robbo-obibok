import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robbo_obibok_launch import (
    DEFAULT_ENTRY_SCRIPT,
    STRICT_ENTRY_SCRIPT,
    selected_entry_script,
    selected_entry_script_from_env,
)
from robbo_obibok_launcher import (
    exec_runtime_entrypoint,
    load_runtime_environment,
    selected_entry_command,
)


class RobboObibokLaunchTests(unittest.TestCase):
    def test_selected_entry_script_defaults_to_standard_entrypoint(self):
        self.assertEqual(selected_entry_script(), DEFAULT_ENTRY_SCRIPT)
        self.assertEqual(selected_entry_script(strict=False), DEFAULT_ENTRY_SCRIPT)

    def test_selected_entry_script_can_switch_to_strict_entrypoint(self):
        self.assertEqual(selected_entry_script(strict=True), STRICT_ENTRY_SCRIPT)

    def test_selected_entry_script_from_env_uses_strict_flag(self):
        self.assertEqual(selected_entry_script_from_env({}), DEFAULT_ENTRY_SCRIPT)
        self.assertEqual(
            selected_entry_script_from_env({"ROBBO_STRICT_COMPAT": "1"}),
            STRICT_ENTRY_SCRIPT,
        )
        self.assertEqual(
            selected_entry_script_from_env({"ROBBO_STRICT_COMPAT": "0"}),
            DEFAULT_ENTRY_SCRIPT,
        )

    def test_selected_entry_command_uses_root_venv_python_and_entry_script(self):
        root = Path("/tmp/robbo")
        self.assertEqual(
            selected_entry_command(root=root, env={"ROBBO_STRICT_COMPAT": "1"}),
            ["/tmp/robbo/venv/bin/python3", "-u", STRICT_ENTRY_SCRIPT],
        )
        self.assertEqual(
            selected_entry_command(
                root=root,
                env={"ROBBO_STRICT_COMPAT": "1"},
                entry_script=DEFAULT_ENTRY_SCRIPT,
            ),
            ["/tmp/robbo/venv/bin/python3", "-u", DEFAULT_ENTRY_SCRIPT],
        )

    def test_load_runtime_environment_accepts_explicit_env_with_token(self):
        env = {"DISCORD_BOT_TOKEN": "token"}

        with patch("robbo_obibok_launcher.load_dotenv_file", lambda _path: None):
            resolved = load_runtime_environment(root=Path("/tmp/robbo"), env=env)

        self.assertIs(resolved, env)

    def test_load_runtime_environment_rejects_missing_token(self):
        with patch("robbo_obibok_launcher.load_dotenv_file", lambda _path: None):
            with self.assertRaises(SystemExit) as ctx:
                load_runtime_environment(root=Path("/tmp/robbo"), env={})

        self.assertIn("DISCORD_BOT_TOKEN", str(ctx.exception))

    def test_exec_runtime_entrypoint_execs_selected_command(self):
        env = {"DISCORD_BOT_TOKEN": "token", "ROBBO_STRICT_COMPAT": "1"}
        captured = {}

        with (
            patch("robbo_obibok_launcher.load_dotenv_file", lambda _path: None),
            patch(
                "robbo_obibok_launcher.os.execvpe",
                side_effect=lambda exe, argv, runtime_env: captured.update(
                    exe=exe,
                    argv=argv,
                    runtime_env=runtime_env,
                ),
            ),
        ):
            exec_runtime_entrypoint(root=Path("/tmp/robbo"), env=env)

        self.assertEqual(captured["exe"], "/tmp/robbo/venv/bin/python3")
        self.assertEqual(
            captured["argv"],
            ["/tmp/robbo/venv/bin/python3", "-u", STRICT_ENTRY_SCRIPT],
        )
        self.assertIs(captured["runtime_env"], env)
