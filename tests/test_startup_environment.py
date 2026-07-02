import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robbo_obibok.runtime_bootstrap import (
    acquire_process_lock,
    initialize_startup_environment,
    release_process_lock,
)


class StartupEnvironmentTests(unittest.TestCase):
    def test_process_lock_rejects_matching_live_owner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_file = str(Path(temp_dir) / "bot.pid")
            acquire_process_lock(lock_file, "python")
            try:
                with self.assertRaises(SystemExit):
                    acquire_process_lock(lock_file, "python")
            finally:
                release_process_lock(lock_file)

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

    def test_initialize_startup_environment_accepts_explicit_lock_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_lock = os.path.join(temp_dir, "custom-test.pid")
            env = initialize_startup_environment(
                bot_token="token",
                root_dir="/some/project/root",
                lock_file=custom_lock,
                validate_runtime_dependencies=lambda: None,
                acquire_process_lock=acquire_process_lock,
                process_name="test-case",
            )
            self.assertEqual(env.lock_file, custom_lock)
            self.assertTrue(os.path.exists(custom_lock))
            release_process_lock(custom_lock)

    def test_initialize_startup_environment_default_lock_from_root_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = initialize_startup_environment(
                bot_token="token",
                root_dir=temp_dir,
                validate_runtime_dependencies=lambda: None,
                acquire_process_lock=acquire_process_lock,
                process_name="test-case",
            )
            self.assertEqual(env.lock_file, os.path.join(temp_dir, "obibok.pid"))
            self.assertTrue(os.path.exists(env.lock_file))
            release_process_lock(env.lock_file)

    def test_isolated_lock_does_not_conflict_with_held_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate a running bot: hold a lock on obibok.pid
            prod_lock = os.path.join(temp_dir, "obibok.pid")
            acquire_process_lock(prod_lock, "production-bot")
            try:
                # Isolated test should use a different lock path
                isolated_lock = os.path.join(temp_dir, "test-isolated.pid")
                env = initialize_startup_environment(
                    bot_token="token",
                    root_dir="/some/root",
                    lock_file=isolated_lock,
                    validate_runtime_dependencies=lambda: None,
                    acquire_process_lock=acquire_process_lock,
                    process_name="isolated-test",
                )
                self.assertNotEqual(env.lock_file, prod_lock)
                self.assertEqual(env.lock_file, isolated_lock)
                release_process_lock(isolated_lock)
            finally:
                release_process_lock(prod_lock)
