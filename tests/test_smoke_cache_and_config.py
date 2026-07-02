"""Smoke tests: verify cache files, archive paths, and config resolution."""

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robbo_obibok.domain_config import AppConfig, derive_app_config
from robbo_obibok.domain_archive_config import ArchiveRuntimeConfig


class CacheFilesSmokeTests(unittest.TestCase):
    """All cache JSON files must exist, be readable, and parse as valid JSON."""

    CACHE_FILES = [
        "asma_cache.json",
        "asma_cache_local.json",
        "ay_cache.json",
        "hvsc_cache.json",
        "hvsc_cache_local.json",
        "kgen_cache.json",
        "metadata_cache.json",
        "modarchive_cache.json",
        "snes_cache.json",
        "tiny_cache.json",
        "ym_cache.json",
    ]

    def test_all_cache_files_exist(self):
        root = str(ROOT)
        for name in self.CACHE_FILES:
            path = os.path.join(root, name)
            with self.subTest(file=name):
                self.assertTrue(os.path.isfile(path), f"Missing cache file: {path}")
                # Ensure it's NOT a symlink anymore
                self.assertFalse(os.path.islink(path), f"Cache file is still a symlink: {path}")

    def test_cache_files_parse_as_json(self):
        root = str(ROOT)
        for name in self.CACHE_FILES:
            path = os.path.join(root, name)
            with self.subTest(file=name):
                try:
                    with open(path, "rb") as fh:
                        data = json.load(fh)
                    self.assertIsInstance(data, (dict, list))
                except (json.JSONDecodeError, OSError) as exc:
                    self.fail(f"{name}: {exc}")

    def test_kgen_cache_has_tracks(self):
        path = os.path.join(str(ROOT), "kgen_cache.json")
        with open(path) as fh:
            data = json.load(fh)
        self.assertIn("tracks", data)
        self.assertGreater(len(data["tracks"]), 4000)


class ArchivePathsSmokeTests(unittest.TestCase):
    """Archive directories referenced in config must be reachable."""

    ARCHIVE_DIRS = [
        "asma",
        "ay",
        "hvsc/C64Music",
        "kgen",
        "spc",
        "tiny",
        "ym",
    ]

    def test_archive_base_path_resolves(self):
        app_config = derive_app_config(
            root_dir=str(ROOT),
            config={},
        )
        # Default: archive_base = <root_dir>/archiwum
        expected = os.path.join(str(ROOT), "archiwum")
        self.assertEqual(app_config.archive_base, expected)
        self.assertTrue(os.path.isdir(expected) or os.path.islink(expected))

    def test_archive_subdirs_exist(self):
        root = str(ROOT)
        base = os.path.join(root, "archiwum")
        for sub in self.ARCHIVE_DIRS:
            path = os.path.join(base, sub)
            with self.subTest(dir=sub):
                self.assertTrue(
                    os.path.isdir(path),
                    f"Archive directory missing: {path}",
                )

    def test_custom_archive_path_from_config(self):
        app_config = derive_app_config(
            root_dir=str(ROOT),
            config={"archive": {"path": "/tmp/test-archiwum"}},
        )
        self.assertEqual(app_config.archive_base, "/tmp/test-archiwum")
        self.assertEqual(app_config.ay_dir, "/tmp/test-archiwum/ay")


class ConfigSmokeTests(unittest.TestCase):
    """Config building must not crash and must produce sensible defaults."""

    def test_derive_app_config_defaults(self):
        app_config = derive_app_config(
            root_dir=str(ROOT),
            config={},
        )
        self.assertIsInstance(app_config, AppConfig)
        self.assertEqual(app_config.root_dir, str(ROOT))
        self.assertIsInstance(app_config.archive_runtime_config, ArchiveRuntimeConfig)
        # bot_token may be set by other tests via os.environ
        self.assertIsInstance(app_config.bot_token, str)

    def test_archive_runtime_config_has_cache_dir(self):
        app_config = derive_app_config(
            root_dir=str(ROOT),
            config={},
        )
        arc = app_config.archive_runtime_config
        expected = os.path.join(str(ROOT), "archiwum", "modarchive", "cache")
        self.assertEqual(arc.modarchive_cache_dir, expected)

    def test_archive_runtime_config_custom_cache_dir(self):
        app_config = derive_app_config(
            root_dir=str(ROOT),
            config={"archive": {"path": "/custom/path"}},
        )
        arc = app_config.archive_runtime_config
        self.assertEqual(arc.modarchive_cache_dir, "/custom/path/modarchive/cache")


if __name__ == "__main__":
    unittest.main()
