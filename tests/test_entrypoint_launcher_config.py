import sys
import types
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_support import install_discord_stubs


install_discord_stubs()

from entrypoint_launcher_config import build_entrypoint_launcher
from entrypoint_executable_assembly import build_entrypoint_legacy_resolver
from entrypoint_module_bindings import ENTRYPOINT_EXPORT_GRAPH
from entrypoint_module_bindings import ENTRYPOINT_DIRECT_COLLECTION_BINDINGS


class EntrypointLauncherConfigTests(unittest.TestCase):
    @staticmethod
    def _direct_collection_names() -> set[str]:
        return {
            spec.export_name
            for spec in ENTRYPOINT_DIRECT_COLLECTION_BINDINGS
            if spec.export_name != "_switch_collection"
        }

    def test_build_entrypoint_launcher_captures_module_builder(self):
        build_calls = []
        create_calls = []
        built_module = object()

        def fake_builder(**kwargs):
            build_calls.append(kwargs)
            return built_module

        fake_launcher = types.SimpleNamespace(
            loader=types.SimpleNamespace(),
            runtime=types.SimpleNamespace(),
        )

        with (
            patch("entrypoint_launcher_config.build_entrypoint_module", side_effect=fake_builder),
            patch(
                "entrypoint_launcher_config.LazyEntrypointLauncher.create",
                side_effect=lambda **kwargs: create_calls.append(kwargs) or fake_launcher,
            ),
        ):
            launcher = build_entrypoint_launcher(
                module_path="/tmp/robbo-obibok.py",
                logger_name="robbo-obibok",
                load_last_collection=lambda _path: None,
                save_last_collection=lambda _path, _mode: None,
                atomic_json_write=lambda _path, _data, _logger: None,
                command_prefix=lambda _bot, _message: "!",
                deps="deps",
                flip_order=["asma"],
                flip_seq=["ASMA"],
            )

        self.assertIs(launcher, fake_launcher)
        self.assertEqual(len(create_calls), 1)

        module_factory = create_calls[0]["module_factory"]
        self.assertIs(module_factory(), built_module)
        self.assertEqual(len(build_calls), 1)
        self.assertEqual(build_calls[0]["module_path"], "/tmp/robbo-obibok.py")
        self.assertEqual(build_calls[0]["logger_name"], "robbo-obibok")
        self.assertEqual(build_calls[0]["deps"], "deps")

    def test_build_entrypoint_legacy_resolver_smoke_covers_legacy_and_compat_paths(self):
        resolved = []
        legacy_values = {
            "bot": "bot",
            "get_guild_id_override": "get-guild",
            "set_guild_id_override": "set-guild",
            "_STATE": "state",
            "_app_cfg": "cfg",
            "_archive_runtime_config": "archive",
        }
        fake_loader = types.SimpleNamespace(
            resolve_legacy=lambda name: legacy_values[name],
            resolve=lambda name: resolved.append(name) or f"resolved:{name}",
        )

        resolve = build_entrypoint_legacy_resolver(loader=fake_loader)

        self.assertEqual(resolve("bot"), "bot")
        self.assertEqual(resolve("get_guild_id_override"), "get-guild")
        self.assertEqual(resolve("set_guild_id_override"), "set-guild")
        self.assertEqual(resolve("_STATE"), "state")
        self.assertEqual(resolve("_app_cfg"), "cfg")
        self.assertEqual(resolve("_archive_runtime_config"), "archive")
        self.assertEqual(resolve("LOCK_FILE"), "resolved:LOCK_FILE")
        self.assertEqual(resolve("_APP"), "resolved:_APP")
        self.assertEqual(set(resolved), {"LOCK_FILE", "_APP"})
        self.assertIn("LOCK_FILE", ENTRYPOINT_EXPORT_GRAPH.compat_names)
        self.assertIn("_APP", ENTRYPOINT_EXPORT_GRAPH.compat_names)
        for name in self._direct_collection_names() | {"single_guild_check", "_FLIP_ORDER", "_FLIP_SEQ"}:
            with self.assertRaises(AttributeError):
                resolve(name)
