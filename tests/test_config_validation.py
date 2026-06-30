import tempfile
import unittest
from pathlib import Path

from entrypoint_startup import load_config


class Logger:
    def error(self, *_args):
        pass


class ConfigValidationTests(unittest.TestCase):
    def test_partial_config_is_merged_with_valid_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "config.yaml").write_text('command_prefix: "?"\n', encoding="utf-8")

            config = load_config(tmpdir, Logger())

        self.assertEqual(config["command_prefix"], "?")
        self.assertEqual(config["audio"]["sink_name"], "asma_bot")

    def test_top_level_sequence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "config.yaml").write_text("- invalid\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "top level"):
                load_config(tmpdir, Logger())

    def test_invalid_sink_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "config.yaml").write_text(
                'audio:\n  sink_name: "bad; command"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "sink_name"):
                load_config(tmpdir, Logger())
