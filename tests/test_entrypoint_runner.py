import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_support import install_discord_stubs


install_discord_stubs()

from entrypoint_runner import build_default_intents, run_bot_entrypoint


class EntrypointRunnerTests(unittest.TestCase):
    def test_build_default_intents_enables_message_content(self):
        intents = build_default_intents()

        self.assertTrue(intents.message_content)

    def test_run_bot_entrypoint_initializes_hooks_runs_bot_and_releases_lock(self):
        calls = []

        class FakeBot:
            def run(self, token):
                calls.append(("run", token))

        run_bot_entrypoint(
            initialize_runtime=lambda: calls.append("init"),
            install_runtime_hooks=lambda **kwargs: calls.append(("hooks", sorted(kwargs))) or kwargs["release_lock"](),
            handle_signal=lambda signum, frame: calls.append(("signal", signum, frame)),
            release_process_lock=lambda path: calls.append(("release", path)),
            bot=FakeBot(),
            lock_file_getter=lambda: "/tmp/lock",
            token_getter=lambda: "runtime-token",
        )

        self.assertEqual(
            calls,
            [
                "init",
                ("hooks", ["handle_signal", "release_lock"]),
                ("release", "/tmp/lock"),
                ("run", "runtime-token"),
                ("release", "/tmp/lock"),
            ],
        )

    def test_run_bot_entrypoint_releases_lock_when_bot_run_fails(self):
        calls = []

        class FakeBot:
            def run(self, _token):
                calls.append("run")
                raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            run_bot_entrypoint(
                initialize_runtime=lambda: calls.append("init"),
                install_runtime_hooks=lambda **kwargs: calls.append(("hooks", sorted(kwargs))),
                handle_signal=lambda signum, frame: calls.append(("signal", signum, frame)),
                release_process_lock=lambda path: calls.append(("release", path)),
                bot=FakeBot(),
                lock_file_getter=lambda: "/tmp/lock",
                token_getter=lambda: "runtime-token",
            )

        self.assertEqual(
            calls,
            [
                "init",
                ("hooks", ["handle_signal", "release_lock"]),
                "run",
                ("release", "/tmp/lock"),
            ],
        )
