import sys
import types
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_launcher_loader import build_entrypoint_support


class EntrypointLauncherSupportTests(unittest.TestCase):
    def test_build_entrypoint_support_uses_injected_logger_builder(self):
        logger_calls = []
        boot_calls = []
        logger = types.SimpleNamespace(name="test-logger")

        with patch(
            "entrypoint_launcher_loader.build_entrypoint_bootstrap",
            side_effect=lambda *args, **kwargs: boot_calls.append((args, kwargs)) or types.SimpleNamespace(),
        ):
            support = build_entrypoint_support(
                module_path="/tmp/robbo-obibok.py",
                logger_name="robbo-obibok",
                load_last_collection=lambda _path: None,
                atomic_json_write=lambda _path, _data, _logger: None,
                configure_logger=lambda root_dir, logger_name: logger_calls.append((root_dir, logger_name)) or logger,
            )

        self.assertIs(support.logger, logger)
        self.assertEqual(logger_calls, [("/tmp", "robbo-obibok")])
        self.assertEqual(len(boot_calls), 1)
        self.assertEqual(boot_calls[0][0][0], "/tmp")
        self.assertIs(boot_calls[0][0][1], logger)
