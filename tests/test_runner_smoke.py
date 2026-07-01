import importlib.util
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_support import install_discord_stubs

install_discord_stubs()


class RunnerSmokeTests(unittest.TestCase):
    @staticmethod
    def _purge_new_project_modules(before_modules: set[str]) -> None:
        root_prefix = str(ROOT)
        for name, module in list(sys.modules.items()):
            if name in before_modules:
                continue
            module_file = getattr(module, "__file__", None)
            if module_file and module_file.startswith(root_prefix):
                sys.modules.pop(name, None)

    @staticmethod
    def _reset_runtime_modules() -> None:
        sys.modules.pop("robbo_obibok_runtime", None)
        sys.modules.pop("robbo_obibok_main", None)
        sys.modules.pop("robbo_obibok_main_strict", None)

    def test_entrypoint_import_smoke_exposes_assembled_runtime_surface(self):
        module_path = ROOT / "robbo-obibok.py"
        before_modules = set(sys.modules)
        self._reset_runtime_modules()
        compat_calls = []
        runtime = types.SimpleNamespace(
            initialize_runtime=lambda: types.SimpleNamespace(
                startup_env=types.SimpleNamespace(bot_token="runtime-token")
            ),
            bot_token=lambda: "runtime-token",
            graceful_shutdown=lambda: None,
            handle_signal=lambda _signum, _frame: None,
            lock_file=lambda: "/tmp/lock",
        )
        assembly = types.SimpleNamespace(
            providers=types.SimpleNamespace(),
            deps=object(),
            launcher=types.SimpleNamespace(loader=types.SimpleNamespace(ensure_module=lambda: None, resolve=lambda name: compat_calls.append(name) or f"resolved:{name}"), runtime=runtime),
            legacy_resolve=lambda name: compat_calls.append(name) or f"resolved:{name}",
            surface=types.SimpleNamespace(resolve=lambda name: compat_calls.append(name) or f"resolved:{name}"),
            bindings={
                "bot": types.SimpleNamespace(ping=lambda: "pong"),
                "single_guild_check": lambda _ctx: True,
                "get_guild_id_override": lambda: None,
                "set_guild_id_override": lambda _guild_id: None,
                "_skip_to_next": lambda: "skip",
                "monitor_playback": lambda: "monitor",
            },
            compat_bindings={
                "_STATE": object(),
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(),
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            },
            compat_policy=False,
        )

        spec = importlib.util.spec_from_file_location("robbo_obibok_entrypoint_smoke", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None

        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
            return_value=assembly,
        ):
            try:
                spec.loader.exec_module(module)
                self.assertEqual(module.initialize_runtime().startup_env.bot_token, "runtime-token")
                self.assertEqual(module.BOT_TOKEN, "runtime-token")
                self.assertEqual(module.bot.ping(), "pong")
                self.assertEqual(module.app_config().bot_token, "cfg-token")
                self.assertEqual(module.flip_order, ["asma"])
                self.assertEqual(module.flip_seq, ["ASMA"])
                self.assertEqual(module._skip_to_next(), "skip")
                self.assertEqual(module.monitor_playback(), "monitor")
                self.assertEqual(module.LOCK_FILE, "resolved:LOCK_FILE")
            finally:
                self._purge_new_project_modules(before_modules)
        self.assertEqual(compat_calls, ["LOCK_FILE"])

    def test_entrypoint_import_smoke_keeps_stable_state_config_exports_without_legacy_flip_names(self):
        module_path = ROOT / "robbo-obibok.py"
        before_modules = set(sys.modules)
        self._reset_runtime_modules()
        runtime = types.SimpleNamespace(
            initialize_runtime=lambda: types.SimpleNamespace(
                startup_env=types.SimpleNamespace(bot_token="runtime-token")
            ),
            bot_token=lambda: "runtime-token",
            graceful_shutdown=lambda: None,
            handle_signal=lambda _signum, _frame: None,
            lock_file=lambda: "/tmp/lock",
        )
        assembly = types.SimpleNamespace(
            providers=types.SimpleNamespace(),
            deps=object(),
            launcher=types.SimpleNamespace(loader=types.SimpleNamespace(ensure_module=lambda: None, resolve=lambda name: f"resolved:{name}"), runtime=runtime),
            legacy_resolve=lambda name: f"resolved:{name}",
            surface=types.SimpleNamespace(resolve=lambda name: f"resolved:{name}"),
            bindings={
                "bot": types.SimpleNamespace(ping=lambda: "pong"),
                "single_guild_check": lambda _ctx: True,
                "get_guild_id_override": lambda: None,
                "set_guild_id_override": lambda _guild_id: None,
                "_skip_to_next": lambda: "skip",
                "monitor_playback": lambda: "monitor",
            },
            compat_bindings={
                "_STATE": object(),
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(name="archive"),
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            },
            compat_policy=False,
        )

        spec = importlib.util.spec_from_file_location("robbo_obibok_entrypoint_legacy_compat", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None

        with patch(
            "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
            return_value=assembly,
        ):
            try:
                spec.loader.exec_module(module)
                self.assertIs(module.state, assembly.compat_bindings["_STATE"])
                self.assertEqual(module.app_config().bot_token, "cfg-token")
                self.assertEqual(module.archive_runtime_config().name, "archive")
                self.assertEqual(module.flip_order, ["asma"])
                self.assertEqual(module.flip_seq, ["ASMA"])
                with self.assertRaises(AttributeError):
                    _ = module._FLIP_ORDER
                with self.assertRaises(AttributeError):
                    _ = module._FLIP_SEQ
            finally:
                self._purge_new_project_modules(before_modules)

    def test_entrypoint_import_smoke_with_deprecated_internal_shims_disabled(self):
        module_path = ROOT / "robbo-obibok.py"
        before_modules = set(sys.modules)
        self._reset_runtime_modules()
        compat_calls = []
        runtime = types.SimpleNamespace(
            initialize_runtime=lambda: types.SimpleNamespace(
                startup_env=types.SimpleNamespace(bot_token="runtime-token")
            ),
            bot_token=lambda: "runtime-token",
            graceful_shutdown=lambda: None,
            handle_signal=lambda _signum, _frame: None,
            lock_file=lambda: "/tmp/lock",
        )
        assembly = types.SimpleNamespace(
            providers=types.SimpleNamespace(),
            deps=object(),
            launcher=types.SimpleNamespace(loader=types.SimpleNamespace(ensure_module=lambda: None, resolve=lambda name: compat_calls.append(name) or f"resolved:{name}"), runtime=runtime),
            legacy_resolve=lambda name: compat_calls.append(name) or f"resolved:{name}",
            surface=types.SimpleNamespace(resolve=lambda name: compat_calls.append(name) or f"resolved:{name}"),
            bindings={
                "bot": types.SimpleNamespace(ping=lambda: "pong"),
                "single_guild_check": lambda _ctx: True,
                "get_guild_id_override": lambda: None,
                "set_guild_id_override": lambda _guild_id: None,
                "_skip_to_next": lambda: "skip",
                "monitor_playback": lambda: "monitor",
                "fetch_metadata_background": lambda: "metadata",
                "health_watchdog": lambda: "watchdog",
                "_after_stream_end": lambda *args: args,
            },
            compat_bindings={
                "_STATE": object(),
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(),
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            },
            compat_policy=False,
        )

        spec = importlib.util.spec_from_file_location("robbo_obibok_entrypoint_smoke_disabled_shims", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None

        with (
            patch(
                "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
                return_value=assembly,
            ),
        ):
            assembly.compat_policy = False
            try:
                spec.loader.exec_module(module)
                self.assertEqual(module.initialize_runtime().startup_env.bot_token, "runtime-token")
                self.assertEqual(module.bot.ping(), "pong")
                self.assertEqual(module.app_config().bot_token, "cfg-token")
                self.assertEqual(module.monitor_playback(), "monitor")
                self.assertEqual(module.fetch_metadata_background(), "metadata")
                self.assertEqual(module.health_watchdog(), "watchdog")
                self.assertEqual(module._skip_to_next(), "skip")
                self.assertEqual(module.LOCK_FILE, "resolved:LOCK_FILE")
                for name in ("_LAUNCHER", "_SURFACE", "_MODULE_DEPS", "_LEGACY_RESOLVE"):
                    with self.assertRaises(AttributeError):
                        getattr(module, name)
            finally:
                self._purge_new_project_modules(before_modules)

    def test_entrypoint_import_smoke_with_legacy_compat_attrs_disabled(self):
        module_path = ROOT / "robbo-obibok.py"
        before_modules = set(sys.modules)
        self._reset_runtime_modules()
        assembly = types.SimpleNamespace(
            providers=types.SimpleNamespace(),
            deps=object(),
            launcher=types.SimpleNamespace(
                loader=types.SimpleNamespace(ensure_module=lambda: None, resolve=lambda name: f"resolved:{name}"),
                runtime=types.SimpleNamespace(
                    initialize_runtime=lambda: types.SimpleNamespace(
                        startup_env=types.SimpleNamespace(bot_token="runtime-token")
                    ),
                    bot_token=lambda: "runtime-token",
                    graceful_shutdown=lambda: None,
                    handle_signal=lambda _signum, _frame: None,
                    lock_file=lambda: "/tmp/lock",
                ),
            ),
            legacy_resolve=lambda name: f"resolved:{name}",
            surface=types.SimpleNamespace(resolve=lambda name: f"resolved:{name}"),
            bindings={
                "bot": types.SimpleNamespace(ping=lambda: "pong"),
                "single_guild_check": lambda _ctx: True,
                "get_guild_id_override": lambda: None,
                "set_guild_id_override": lambda _guild_id: None,
                "_skip_to_next": lambda: "skip",
                "monitor_playback": lambda: "monitor",
            },
            compat_bindings={
                "_STATE": object(),
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(name="archive"),
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            },
            compat_policy=False,
        )

        spec = importlib.util.spec_from_file_location("robbo_obibok_entrypoint_legacy_attrs_disabled", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None

        with (
            patch(
                "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
                return_value=assembly,
            ),
        ):
            try:
                spec.loader.exec_module(module)
                self.assertIs(module.state, assembly.compat_bindings["_STATE"])
                self.assertEqual(module.app_config().bot_token, "cfg-token")
                self.assertEqual(module._skip_to_next(), "skip")
                for name in ("_STATE", "_app_cfg", "_archive_runtime_config", "_FLIP_ORDER", "_FLIP_SEQ"):
                    with self.assertRaises(AttributeError):
                        getattr(module, name)
            finally:
                self._purge_new_project_modules(before_modules)

    def test_entrypoint_main_smoke_hands_runtime_into_run_bot_entrypoint(self):
        module_path = ROOT / "robbo-obibok.py"
        before_modules = set(sys.modules)
        self._reset_runtime_modules()
        runtime_calls = []
        runtime = types.SimpleNamespace(
            initialize_runtime=lambda: types.SimpleNamespace(
                startup_env=types.SimpleNamespace(bot_token="runtime-token")
            ),
            bot_token=lambda: "runtime-token",
            graceful_shutdown=lambda: None,
            handle_signal=lambda signum, frame: runtime_calls.append((signum, frame)),
            lock_file=lambda: "/tmp/lock",
        )
        assembly = types.SimpleNamespace(
            providers=types.SimpleNamespace(),
            deps=object(),
            launcher=types.SimpleNamespace(loader=types.SimpleNamespace(ensure_module=lambda: None, resolve=lambda name: f"resolved:{name}"), runtime=runtime),
            legacy_resolve=lambda name: f"resolved:{name}",
            surface=types.SimpleNamespace(resolve=lambda name: f"resolved:{name}"),
            bindings={
                "bot": types.SimpleNamespace(run=lambda _token: None),
                "single_guild_check": lambda _ctx: True,
                "get_guild_id_override": lambda: None,
                "set_guild_id_override": lambda _guild_id: None,
                "_skip_to_next": lambda: "skip",
                "monitor_playback": lambda: "monitor",
            },
            compat_bindings={
                "_STATE": object(),
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(),
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            },
            compat_policy=False,
        )
        captured = {}

        def fake_run_bot_entrypoint(**kwargs):
            captured.update(kwargs)
            app = kwargs["initialize_runtime"]()
            captured["initialized_token"] = app.startup_env.bot_token
            captured["runtime_token"] = kwargs["token_getter"]()
            captured["lock_file"] = kwargs["lock_file_getter"]()

        with (
            patch(
                "entrypoint_executable_assembly.build_entrypoint_executable_assembly",
                return_value=assembly,
            ),
            patch("robbo_obibok_runtime.run_bot_entrypoint", side_effect=fake_run_bot_entrypoint),
        ):
            try:
                runpy.run_path(str(module_path), run_name="__main__")
            finally:
                self._purge_new_project_modules(before_modules)

        self.assertEqual(captured["initialized_token"], "runtime-token")
        self.assertEqual(captured["runtime_token"], "runtime-token")
        self.assertEqual(captured["lock_file"], "/tmp/lock")
        self.assertIs(captured["bot"], assembly.bindings["bot"])
        captured["handle_signal"](15, "frame")
        self.assertEqual(runtime_calls, [(15, "frame")])

    def test_cli_main_process_smoke_runs_in_isolated_python_process(self):
        harness = """
import json
import types
from unittest.mock import patch
from tests.test_support import install_discord_stubs

install_discord_stubs()
import robbo_obibok_runtime
runtime_calls = []
assembly = types.SimpleNamespace(
    providers=types.SimpleNamespace(),
    deps=object(),
    launcher=types.SimpleNamespace(
        loader=types.SimpleNamespace(ensure_module=lambda: None, resolve=lambda name: f"resolved:{name}"),
        runtime=types.SimpleNamespace(
            initialize_runtime=lambda: types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            bot_token=lambda: "runtime-token",
            graceful_shutdown=lambda: None,
            handle_signal=lambda signum, frame: runtime_calls.append([signum, frame]),
            lock_file=lambda: "/tmp/lock",
        ),
    ),
    legacy_resolve=lambda name: f"resolved:{name}",
    surface=types.SimpleNamespace(resolve=lambda name: f"resolved:{name}"),
    bindings={
        "bot": types.SimpleNamespace(run=lambda _token: None),
        "single_guild_check": lambda _ctx: True,
        "get_guild_id_override": lambda: None,
        "set_guild_id_override": lambda _guild_id: None,
        "_skip_to_next": lambda: "skip",
        "monitor_playback": lambda: "monitor",
    },
    compat_bindings={
        "_STATE": object(),
        "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
        "_archive_runtime_config": lambda: types.SimpleNamespace(),
        "_FLIP_ORDER": ["asma"],
        "_FLIP_SEQ": ["ASMA"],
    },
    compat_policy=False,
)
captured = {}

def fake_run_bot_entrypoint(**kwargs):
    captured["token"] = kwargs["token_getter"]()
    captured["lock_file"] = kwargs["lock_file_getter"]()
    captured["bot_type"] = type(kwargs["bot"]).__name__
    kwargs["handle_signal"](2, "frame")

with (
    patch("entrypoint_executable_assembly.build_entrypoint_executable_assembly", return_value=assembly),
    patch("robbo_obibok_runtime.run_bot_entrypoint", side_effect=fake_run_bot_entrypoint),
    patch("runtime_support.validate_runtime_dependencies", lambda required_tools=None: None),
    patch("entrypoint_executable_assembly.validate_runtime_dependencies", lambda required_tools=None: None),
):
    robbo_obibok_runtime.main()

print(json.dumps({"captured": captured, "runtime_calls": runtime_calls}))
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{ROOT}/src/robbo_obibok:{ROOT}"
        env["DISCORD_BOT_TOKEN"] = "runtime-token"

        result = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["captured"]["token"], "runtime-token")
        self.assertEqual(payload["captured"]["lock_file"], "/tmp/lock")
        self.assertEqual(payload["runtime_calls"], [[2, "frame"]])

    def test_cli_main_process_smoke_with_deprecated_internal_shims_disabled(self):
        harness = """
import json
import types
from unittest.mock import patch
from tests.test_support import install_discord_stubs

install_discord_stubs()
import robbo_obibok_runtime
runtime_calls = []
assembly = types.SimpleNamespace(
    providers=types.SimpleNamespace(),
    deps=object(),
    launcher=types.SimpleNamespace(
        loader=types.SimpleNamespace(ensure_module=lambda: None, resolve=lambda name: f"resolved:{name}"),
        runtime=types.SimpleNamespace(
            initialize_runtime=lambda: types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            bot_token=lambda: "runtime-token",
            graceful_shutdown=lambda: None,
            handle_signal=lambda signum, frame: runtime_calls.append([signum, frame]),
            lock_file=lambda: "/tmp/lock",
        ),
    ),
    legacy_resolve=lambda name: f"resolved:{name}",
    surface=types.SimpleNamespace(resolve=lambda name: f"resolved:{name}"),
    bindings={
        "bot": types.SimpleNamespace(run=lambda _token: None),
        "single_guild_check": lambda _ctx: True,
        "get_guild_id_override": lambda: None,
        "set_guild_id_override": lambda _guild_id: None,
        "_skip_to_next": lambda: "skip",
        "monitor_playback": lambda: "monitor",
        "fetch_metadata_background": lambda: "metadata",
        "health_watchdog": lambda: "watchdog",
        "_after_stream_end": lambda *args: args,
    },
    compat_bindings={
        "_STATE": object(),
        "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
        "_archive_runtime_config": lambda: types.SimpleNamespace(),
        "_FLIP_ORDER": ["asma"],
        "_FLIP_SEQ": ["ASMA"],
    },
    compat_policy=False,
)
captured = {}

def fake_run_bot_entrypoint(**kwargs):
    import robbo_obibok_runtime
    captured["token"] = kwargs["token_getter"]()
    captured["lock_file"] = kwargs["lock_file_getter"]()
    captured["bot_type"] = type(kwargs["bot"]).__name__
    kwargs["handle_signal"](2, "frame")
    captured["deprecated_internal_visibility"] = {}
    for name in ("_LAUNCHER", "_SURFACE", "_MODULE_DEPS", "_LEGACY_RESOLVE"):
        try:
            getattr(robbo_obibok_runtime, name)
            captured["deprecated_internal_visibility"][name] = True
        except AttributeError:
            captured["deprecated_internal_visibility"][name] = False

with (
    patch("entrypoint_executable_assembly.build_entrypoint_executable_assembly", return_value=assembly),
    patch("robbo_obibok_runtime.run_bot_entrypoint", side_effect=fake_run_bot_entrypoint),
    patch("runtime_support.validate_runtime_dependencies", lambda required_tools=None: None),
    patch("entrypoint_executable_assembly.validate_runtime_dependencies", lambda required_tools=None: None),
):
    robbo_obibok_runtime.main()

print(json.dumps({"captured": captured, "runtime_calls": runtime_calls}))
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{ROOT}/src/robbo_obibok:{ROOT}"
        env["DISCORD_BOT_TOKEN"] = "runtime-token"

        result = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["captured"]["token"], "runtime-token")
        self.assertEqual(payload["captured"]["lock_file"], "/tmp/lock")
        self.assertEqual(
            payload["captured"]["deprecated_internal_visibility"],
            {
                "_LAUNCHER": False,
                "_SURFACE": False,
                "_MODULE_DEPS": False,
                "_LEGACY_RESOLVE": False,
            },
        )
        self.assertEqual(payload["runtime_calls"], [[2, "frame"]])

    def test_cli_strict_main_process_smoke_uses_strict_entrypoint(self):
        harness = """
import json
import types
from unittest.mock import patch
from tests.test_support import install_discord_stubs

install_discord_stubs()
import robbo_obibok_runtime

runtime_calls = []
assembly = types.SimpleNamespace(
    providers=types.SimpleNamespace(),
    deps=object(),
    launcher=types.SimpleNamespace(
        loader=types.SimpleNamespace(ensure_module=lambda: None, resolve=lambda name: f"resolved:{name}"),
        runtime=types.SimpleNamespace(
            initialize_runtime=lambda: types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token")),
            bot_token=lambda: "runtime-token",
            graceful_shutdown=lambda: None,
            handle_signal=lambda signum, frame: runtime_calls.append([signum, frame]),
            lock_file=lambda: "/tmp/lock",
        ),
    ),
    legacy_resolve=lambda name: f"resolved:{name}",
    surface=types.SimpleNamespace(resolve=lambda name: f"resolved:{name}"),
    bindings={
        "bot": types.SimpleNamespace(run=lambda _token: None),
        "single_guild_check": lambda _ctx: True,
        "get_guild_id_override": lambda: None,
        "set_guild_id_override": lambda _guild_id: None,
        "_skip_to_next": lambda: "skip",
        "monitor_playback": lambda: "monitor",
    },
    compat_bindings={
        "_STATE": object(),
        "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
        "_archive_runtime_config": lambda: types.SimpleNamespace(),
        "_FLIP_ORDER": ["asma"],
        "_FLIP_SEQ": ["ASMA"],
    },
    compat_policy=False,
)
captured = {}

def fake_run_bot_entrypoint(**kwargs):
    captured["token"] = kwargs["token_getter"]()
    captured["lock_file"] = kwargs["lock_file_getter"]()
    kwargs["handle_signal"](3, "frame")

with (
    patch("entrypoint_executable_assembly.build_entrypoint_executable_assembly", return_value=assembly),
    patch("robbo_obibok_runtime.run_bot_entrypoint", side_effect=fake_run_bot_entrypoint),
):
    robbo_obibok_runtime.main()

print(json.dumps({"captured": captured, "runtime_calls": runtime_calls}))
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{ROOT}/src/robbo_obibok:{ROOT}"
        env["DISCORD_BOT_TOKEN"] = "runtime-token"

        result = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["captured"]["token"], "runtime-token")
        self.assertEqual(payload["captured"]["lock_file"], "/tmp/lock")
        self.assertEqual(payload["runtime_calls"], [[3, "frame"]])

    def test_run_bot_shell_shim_fails_fast_without_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shutil.copy(ROOT / "run_bot.sh", temp_root / "run_bot.sh")
            (temp_root / "src" / "robbo_obibok").mkdir(parents=True)
            shutil.copy(ROOT / "src" / "robbo_obibok" / "robbo_obibok_launcher.py", temp_root / "src" / "robbo_obibok" / "robbo_obibok_launcher.py")
            os.chmod(temp_root / "run_bot.sh", 0o755)
            (temp_root / "venv" / "bin").mkdir(parents=True)
            launcher = temp_root / "venv" / "bin" / "python3"
            launcher.write_text(
                "#!/usr/bin/env bash\n"
                f'exec "{sys.executable}" "$@"\n',
                encoding="utf-8",
            )
            os.chmod(launcher, 0o755)

            env = self._clean_env()
            env["PYTHONPATH"] = f"{ROOT}/src/robbo_obibok:{ROOT}"

            result = subprocess.run(
                ["bash", "run_bot.sh"],
                cwd=temp_root,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("DISCORD_BOT_TOKEN", result.stderr)

    def test_run_bot_shell_shim_uses_strict_entry_script_when_env_requests_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            shutil.copy(ROOT / "run_bot.sh", temp_root / "run_bot.sh")
            (temp_root / "src" / "robbo_obibok").mkdir(parents=True)
            shutil.copy(ROOT / "src" / "robbo_obibok" / "robbo_obibok_launcher.py", temp_root / "src" / "robbo_obibok" / "robbo_obibok_launcher.py")
            os.chmod(temp_root / "run_bot.sh", 0o755)
            capture_path = temp_root / "launcher_args.txt"
            (temp_root / "venv" / "bin").mkdir(parents=True)
            fake_python = temp_root / "venv" / "bin" / "python3"
            fake_python.write_text(
                "#!/usr/bin/env bash\n"
                f'printf "%s\\n" "$@" > "{capture_path}"\n',
                encoding="utf-8",
            )
            os.chmod(fake_python, 0o755)

            env = self._clean_env()
            env["ROBBO_STRICT_COMPAT"] = "1"

            result = subprocess.run(
                ["bash", "run_bot.sh"],
                cwd=temp_root,
                capture_output=True,
                text=True,
                env=env,
            )

            captured_args = capture_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            captured_args,
            ["-u", "src/robbo_obibok/robbo_obibok_launcher.py"],
        )


    @staticmethod
    def _clean_env() -> dict[str, str]:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"DISCORD_BOT_TOKEN", "PYTHONPATH"}
        }
        env.setdefault("PATH", os.environ.get("PATH", ""))
        return env
