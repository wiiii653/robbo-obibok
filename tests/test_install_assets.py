import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_LOCAL_INDEX_BUILDERS = (
    "build_asma_index.py",
    "build_hvsc_index.py",
    "build_ay_index.py",
    "build_ym_index.py",
    "build_tiny_index.py",
    "build_snes_index.py",
)


class InstallAssetsTests(unittest.TestCase):
    @staticmethod
    def _assert_ordered_substrings(text: str, substrings: tuple[str, ...]) -> None:
        position = -1
        for substring in substrings:
            next_position = text.find(substring, position + 1)
            if next_position == -1:
                raise AssertionError(f"missing substring: {substring}")
            if next_position < position:
                raise AssertionError(f"substring out of order: {substring}")
            position = next_position

    def test_launch_helper_declares_canonical_entry_scripts(self):
        launch_text = (ROOT / "robbo_obibok_launch.py").read_text(encoding="utf-8")

        self.assertIn('DEFAULT_ENTRY_SCRIPT = "robbo-obibok.py"', launch_text)
        self.assertIn('STRICT_ENTRY_SCRIPT = "robbo-obibok-strict.py"', launch_text)

    def test_strict_service_uses_explicit_strict_entrypoint(self):
        service_text = (ROOT / "robbo-obibok-strict.service").read_text(encoding="utf-8")

        self.assertIn("Description=Robbo Obibok", service_text)
        self.assertIn("strict compatibility mode", service_text)
        self.assertIn("robbo-obibok-strict.py", service_text)
        self.assertNotIn("ROBBO_STRICT_COMPAT=1", service_text)

    def test_install_script_installs_both_service_units(self):
        install_text = (ROOT / "install.sh").read_text(encoding="utf-8")

        self.assertIn('SERVICE_FILES=("robbo-obibok.service" "robbo-obibok-strict.service")', install_text)
        for script_name in EXPECTED_LOCAL_INDEX_BUILDERS:
            self.assertIn(script_name, install_text)
        self.assertIn("systemctl --user enable --now robbo-obibok.service", install_text)
        self.assertIn("systemctl --user enable --now robbo-obibok-strict.service", install_text)
        self.assertIn('SERVICE_DIR="$HOME/.config/systemd/user"', install_text)
        self.assertIn("make run-strict", install_text)

    def test_cli_entrypoints_delegate_to_shared_bootstrap(self):
        main_text = (ROOT / "robbo_obibok_main.py").read_text(encoding="utf-8")
        strict_main_text = (ROOT / "robbo_obibok_main_strict.py").read_text(encoding="utf-8")
        logged_entrypoint_text = (ROOT / "run_bot_logged.py").read_text(encoding="utf-8")
        logged_launcher_text = (ROOT / "robbo_obibok_logged_launcher.py").read_text(encoding="utf-8")
        runtime_text = (ROOT / "robbo_obibok_runtime.py").read_text(encoding="utf-8")
        entrypoint_text = (ROOT / "robbo-obibok.py").read_text(encoding="utf-8")
        strict_entrypoint_text = (ROOT / "robbo-obibok-strict.py").read_text(encoding="utf-8")

        self.assertIn("from robbo_obibok_runtime import run_runtime_entrypoint", main_text)
        self.assertIn("run_runtime_entrypoint()", main_text)
        self.assertIn("from robbo_obibok_runtime import run_runtime_entrypoint", strict_main_text)
        self.assertIn("run_runtime_entrypoint()", strict_main_text)
        self.assertIn("def run_runtime_entrypoint(", runtime_text)
        self.assertIn("from robbo_obibok_logged_launcher import", logged_entrypoint_text)
        self.assertIn("def run_logged_bot(", logged_launcher_text)
        self.assertIn("runtime facade", runtime_text)
        self.assertIn("launcher facade", entrypoint_text)
        self.assertIn("launcher facade", strict_entrypoint_text)

    def test_launch_assets_are_consistent_across_entrypoints_docs_and_services(self):
        agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        shell_text = (ROOT / "run_bot.sh").read_text(encoding="utf-8")
        launcher_script_text = (ROOT / "test_launchers.sh").read_text(encoding="utf-8")
        logged_text = (ROOT / "run_bot_logged.py").read_text(encoding="utf-8")
        logged_launcher_text = (ROOT / "robbo_obibok_logged_launcher.py").read_text(encoding="utf-8")
        launcher_text = (ROOT / "robbo_obibok_launcher.py").read_text(encoding="utf-8")
        make_text = (ROOT / "Makefile").read_text(encoding="utf-8")
        readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
        install_text = (ROOT / "install.sh").read_text(encoding="utf-8")
        strict_service_text = (ROOT / "robbo-obibok-strict.service").read_text(encoding="utf-8")
        default_service_text = (ROOT / "robbo-obibok.service").read_text(encoding="utf-8")
        workflow_text = (ROOT / ".github" / "workflows" / "test-launchers.yml").read_text(encoding="utf-8")
        runtime_workflow_text = (ROOT / ".github" / "workflows" / "test-entrypoint-runtime.yml").read_text(encoding="utf-8")

        self.assertIn("`robbo_obibok_launcher.py` is the canonical process launcher", agents_text)
        self.assertIn("local entrypoint scripts", agents_text)
        self.assertIn("./test_launchers.sh", agents_text)
        self.assertIn("`robbo_obibok_logged_launcher.py` remains separate on purpose", agents_text)
        self.assertIn("logging-oriented launcher module", agents_text)
        self.assertIn("launcher smoke CI surface is `.github/workflows/test-launchers.yml`", agents_text)
        self.assertIn("broader entrypoint/runtime CI surface is `.github/workflows/test-entrypoint-runtime.yml`", agents_text)
        self.assertIn("exec ./venv/bin/python3 -u robbo_obibok_launcher.py", shell_text)
        self.assertIn("tests.test_run_bot_logged", launcher_script_text)
        self.assertNotIn("ENTRY_SCRIPT=", shell_text)
        self.assertIn("robbo_obibok_logged_launcher", logged_text)
        self.assertIn("build_logged_launch_command", logged_launcher_text)
        self.assertIn("run_logged_bot", logged_launcher_text)
        self.assertIn("load_runtime_environment(root=root, env=os.environ if env is None else env)", logged_launcher_text)
        self.assertIn("selected_entry_command(root=root, env=runtime_env, entry_script=entry_script)", logged_launcher_text)
        self.assertIn("os.execvpe(command[0], command, runtime_env)", launcher_text)
        self.assertIn("./run_bot.sh", make_text)
        self.assertIn("./test_launchers.sh", make_text)
        self.assertIn("make test-launchers", make_text)
        for script_name in EXPECTED_LOCAL_INDEX_BUILDERS:
            self.assertIn(script_name, make_text)
        self.assertIn("./run_bot.sh", readme_text)
        self.assertIn("ROBBO_STRICT_COMPAT=1 ./run_bot.sh", readme_text)
        self.assertIn("git@github.com:wiiii653/robbo-obibok.git", readme_text)
        self.assertNotIn("robbo-obibok-ulimate-chiptune-bot", readme_text)
        self.assertIn("make build-indexes", readme_text)
        self.assertIn("# Canonical logged launcher module", readme_text)
        self.assertIn("run_bot_logged.py", readme_text)
        self.assertIn("./test_launchers.sh", readme_text)
        self.assertIn("make test-launchers", readme_text)
        for script_name in EXPECTED_LOCAL_INDEX_BUILDERS:
            self.assertIn(script_name, readme_text)
        self.assertIn("cp robbo-obibok-strict.service", readme_text)
        self.assertIn("make run-strict", install_text)
        self.assertIn("robbo-obibok-strict.py", strict_service_text)
        self.assertIn("robbo-obibok.py", default_service_text)
        self.assertIn("WorkingDirectory=%h/robbo-obibok", default_service_text)
        self.assertIn("WantedBy=default.target", default_service_text)
        self.assertNotIn("User=boruta", default_service_text)
        self.assertNotIn("ExecStartPre=", default_service_text)
        self.assertIn("Run launcher smoke suite", workflow_text)
        self.assertIn("./test_launchers.sh", workflow_text)
        self.assertIn("Run entrypoint/runtime regression suite", runtime_workflow_text)
        self.assertIn("tests.test_entrypoint_executable_assembly", runtime_workflow_text)

    def test_local_index_builder_order_stays_consistent_across_install_docs_and_make(self):
        install_text = (ROOT / "install.sh").read_text(encoding="utf-8")
        make_text = (ROOT / "Makefile").read_text(encoding="utf-8")
        readme_text = (ROOT / "README.md").read_text(encoding="utf-8")

        self._assert_ordered_substrings(install_text, EXPECTED_LOCAL_INDEX_BUILDERS)
        self._assert_ordered_substrings(make_text, EXPECTED_LOCAL_INDEX_BUILDERS)
        self._assert_ordered_substrings(readme_text, EXPECTED_LOCAL_INDEX_BUILDERS)
