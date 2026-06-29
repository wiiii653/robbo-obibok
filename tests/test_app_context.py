import sys
import tempfile
from pathlib import Path
from types import MappingProxyType
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_context import build_app_context
from app_bootstrap import bootstrap_app
from archive_catalog import ArchivePaths


class AppContextTests(unittest.TestCase):
    def test_build_app_context_wires_state_stores_and_archive_views(self):
        writes = []
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = ArchivePaths(
                asma_base="https://asma.example/",
                asma_dir=f"{temp_dir}/asma",
                asma_local_cache=f"{temp_dir}/asma_cache.json",
                ay_cache=f"{temp_dir}/ay_cache.json",
                hvsc_base="https://hvsc.example/",
                hvsc_cache_file=f"{temp_dir}/hvsc_cache.json",
                hvsc_cache_ttl_hours=24,
                hvsc_local_cache=f"{temp_dir}/hvsc_local_cache.json",
                hvsc_songlengths_url="https://hvsc.example/songlengths.txt",
                metadata_cache=f"{temp_dir}/metadata_cache.json",
                modarchive_cache_file=f"{temp_dir}/modarchive_cache.json",
                snes_cache_file=f"{temp_dir}/snes_cache.json",
                tiny_cache=f"{temp_dir}/tiny_cache.json",
                ym_cache=f"{temp_dir}/ym_cache.json",
            )
            context = build_app_context(
                queue_dir=f"{temp_dir}/queue",
                default_collection_mode="asma",
                favorites_file=f"{temp_dir}/favorites.json",
                blacklist_file=f"{temp_dir}/blacklist.json",
                playlist_dir=f"{temp_dir}/playlists",
                archive_paths=paths,
                json_writer=lambda path, data: writes.append((path, data)),
                logger=type("Logger", (), {"error": lambda *a, **k: None})(),
            )

            state = context.app_state.get_state(1)
            state.set_guild_id(1)
            state.set_queue_state(["track-1"], -1)
            context.app_state.save_queue(state)

        self.assertEqual(state.collection_mode, "asma")
        self.assertIsInstance(context.metadata_index, MappingProxyType)
        self.assertIsInstance(context.modarchive_name_map, MappingProxyType)
        self.assertIsInstance(context.snes_metadata, MappingProxyType)
        self.assertEqual(dict(context.metadata_index), context.archives.metadata_index)
        self.assertEqual(dict(context.modarchive_name_map), context.archives.modarchive_name_map)
        self.assertEqual(dict(context.snes_metadata), context.archives.snes_metadata)
        self.assertTrue(writes)

    def test_bootstrap_app_exposes_archive_owner_and_read_only_views(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = ArchivePaths(
                asma_base="https://asma.example/",
                asma_dir=f"{temp_dir}/asma",
                asma_local_cache=f"{temp_dir}/asma_cache.json",
                ay_cache=f"{temp_dir}/ay_cache.json",
                hvsc_base="https://hvsc.example/",
                hvsc_cache_file=f"{temp_dir}/hvsc_cache.json",
                hvsc_cache_ttl_hours=24,
                hvsc_local_cache=f"{temp_dir}/hvsc_local_cache.json",
                hvsc_songlengths_url="https://hvsc.example/songlengths.txt",
                metadata_cache=f"{temp_dir}/metadata_cache.json",
                modarchive_cache_file=f"{temp_dir}/modarchive_cache.json",
                snes_cache_file=f"{temp_dir}/snes_cache.json",
                tiny_cache=f"{temp_dir}/tiny_cache.json",
                ym_cache=f"{temp_dir}/ym_cache.json",
            )
            boot = bootstrap_app(
                queue_dir=f"{temp_dir}/queue",
                default_collection_mode="asma",
                favorites_file=f"{temp_dir}/favorites.json",
                blacklist_file=f"{temp_dir}/blacklist.json",
                playlist_dir=f"{temp_dir}/playlists",
                archive_paths=paths,
                json_writer=lambda *_args, **_kwargs: None,
                logger=type("Logger", (), {"error": lambda *a, **k: None})(),
            )

        self.assertFalse(hasattr(boot, "metadata_index"))
        self.assertIsInstance(boot.archive_views.metadata_index, MappingProxyType)
        self.assertEqual(dict(boot.archive_views.metadata_index), boot.context.archives.metadata_index)
