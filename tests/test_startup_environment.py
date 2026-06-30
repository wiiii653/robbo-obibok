import sys
import asyncio
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime_bootstrap import initialize_startup_environment


class StartupEnvironmentTests(unittest.TestCase):
    def test_initialize_startup_environment_builds_lock_and_shutdown_flag(self):
        calls = []
        with tempfile.TemporaryDirectory() as temp_dir:
            env = initialize_startup_environment(
                bot_token="token",
                root_dir=temp_dir,
                validate_runtime_dependencies=lambda: calls.append("validate"),
                acquire_process_lock=lambda path, process: calls.append((path, process)) or 123,
                process_name="robbo-obibok.py",
            )

        self.assertEqual(env.bot_token, "token")
        self.assertTrue(env.lock_file.endswith("obibok.pid"))
        self.assertIsInstance(env.shutdown_flag, asyncio.Event)
        self.assertEqual(calls[0], "validate")
        self.assertEqual(calls[1][1], "robbo-obibok.py")

    def test_initialize_startup_environment_rejects_missing_token(self):
        with self.assertRaises(SystemExit) as ctx:
            initialize_startup_environment(
                bot_token="",
                root_dir="/tmp",
                validate_runtime_dependencies=lambda: None,
                acquire_process_lock=lambda *_args: 1,
                process_name="robbo-obibok.py",
            )

        self.assertIn("DISCORD_BOT_TOKEN", str(ctx.exception))
