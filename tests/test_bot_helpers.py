import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


def load_bot_module():
    os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
    module_path = Path(__file__).resolve().parents[1] / "robbo-obibok.py"
    spec = importlib.util.spec_from_file_location("robbo_obibok", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


bot = load_bot_module()


class FetchMetadataBatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_index = dict(bot.metadata_index)
        self.original_fetch = bot.fetch_single_metadata
        bot.metadata_index.clear()

    async def asyncTearDown(self):
        bot.metadata_index.clear()
        bot.metadata_index.update(self.original_index)
        bot.fetch_single_metadata = self.original_fetch

    async def test_skips_cached_urls_without_misalignment(self):
        bot.metadata_index["cached"] = {"NAME": "Cached"}

        async def fake_fetch(_session, url):
            return {"NAME": f"meta:{url}"}

        bot.fetch_single_metadata = fake_fetch

        results = await bot.fetch_metadata_batch(None, ["cached", "fresh-a", "fresh-b"], batch_size=3)

        self.assertEqual(results["fresh-a"]["NAME"], "meta:fresh-a")
        self.assertEqual(results["fresh-b"]["NAME"], "meta:fresh-b")
        self.assertNotIn("cached", results)


class TempPathTests(unittest.TestCase):
    def test_build_temp_path_is_collision_resistant_for_same_filename(self):
        first = bot.build_temp_path("https://example.com/a/track.sap")
        second = bot.build_temp_path("https://example.com/b/track.sap")

        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith("_track.sap"))
        self.assertTrue(second.endswith("_track.sap"))


class SonglengthParsingTests(unittest.TestCase):
    def setUp(self):
        bot.sid_durations.clear()

    def test_parse_old_format(self):
        """Old single-line format: ; /path = M:SS"""
        tracks = bot.parse_songlengths_to_tracks("; /MUSICIANS/A/Author/Track.sid = 3:02")

        self.assertEqual(len(tracks), 1)
        self.assertEqual(bot.sid_durations[tracks[0]], 182)

    def test_parse_md5_format(self):
        """MD5 format: ; /path then hash=M:SS on next line"""
        data = "; /MUSICIANS/A/Author/Track.sid\n6897307ef63533962667412848c92124=1:17"
        tracks = bot.parse_songlengths_to_tracks(data)

        self.assertEqual(len(tracks), 1)
        self.assertEqual(bot.sid_durations[tracks[0]], 77)

    def test_parse_md5_with_alt_duration(self):
        """MD5 format with alternate duration: hash=M:SS (alt X:XX)"""
        data = "; /MUSICIANS/A/Author/Track.sid\nabc123=3:02 (alt 4:15)"
        tracks = bot.parse_songlengths_to_tracks(data)

        self.assertEqual(len(tracks), 1)
        self.assertEqual(bot.sid_durations[tracks[0]], 182)  # first dur wins

    def test_parse_md5_no_duration(self):
        """MD5 format without duration (should still extract track)."""
        data = "; /MUSICIANS/A/Author/Track.sid\nnoise"
        tracks = bot.parse_songlengths_to_tracks(data)

        self.assertEqual(len(tracks), 1)  # path still extracted
        self.assertNotIn(tracks[0], bot.sid_durations)


class YmCacheTests(unittest.TestCase):
    """Tests for YM cache loading."""

    def setUp(self):
        self.temp_cache = Path(bot.YM_CACHE + ".test")
        self.real_cache = bot.YM_CACHE
        bot.YM_CACHE = str(self.temp_cache)

    def tearDown(self):
        bot.YM_CACHE = self.real_cache
        if self.temp_cache.exists():
            self.temp_cache.unlink()

    def test_load_ym_cache_returns_none_when_missing(self):
        """load_ym_cache returns None when cache file doesn't exist."""
        result = bot.load_ym_cache()
        self.assertIsNone(result)

    def test_load_ym_cache_returns_tracks(self):
        """load_ym_cache returns list of paths from valid cache."""
        import json
        data = {
            "version": 1,
            "total": 3,
            "tracks": [
                {"path": "modland/Jochen Hippel/track1.ym", "size": 1234, "collection": "modland"},
                {"path": "bulba_v5/test.ym", "size": 567, "collection": "bulba_v5"},
            ]
        }
        with open(self.temp_cache, "w") as f:
            json.dump(data, f)
        result = bot.load_ym_cache()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIn("modland/Jochen Hippel/track1.ym", result)


class SingleGuildCheckTests(unittest.TestCase):
    """Tests for single-server lock."""

    def test_rejects_wrong_guild(self):
        """single_guild_check returns False for non-matching guild."""
        orig = bot.GUILD_ID
        bot.GUILD_ID = 12345
        ctx = MagicMock()
        ctx.guild.id = 99999
        self.assertFalse(bot.single_guild_check(ctx))
        bot.GUILD_ID = orig

    def test_allows_correct_guild(self):
        """single_guild_check returns True for matching guild."""
        orig = bot.GUILD_ID
        bot.GUILD_ID = 12345
        ctx = MagicMock()
        ctx.guild.id = 12345
        self.assertTrue(bot.single_guild_check(ctx))
        bot.GUILD_ID = orig

    def test_allows_when_unset(self):
        """single_guild_check returns True when GUILD_ID is not configured."""
        orig = bot.GUILD_ID
        bot.GUILD_ID = None
        ctx = MagicMock()
        ctx.guild.id = 99999
        self.assertTrue(bot.single_guild_check(ctx))
        bot.GUILD_ID = orig


if __name__ == "__main__":
    unittest.main()
