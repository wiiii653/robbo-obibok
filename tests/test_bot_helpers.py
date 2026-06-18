import asyncio
import importlib.util
import os
import unittest
from pathlib import Path


def load_bot_module():
    os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
    module_path = Path(__file__).resolve().parents[1] / "asma-bot.py"
    spec = importlib.util.spec_from_file_location("asma_bot", module_path)
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
    def test_parse_songlengths_populates_duration_map(self):
        bot.sid_durations.clear()
        tracks = bot.parse_songlengths_to_tracks("; /MUSICIANS/A/Author/Track.sid = 3:02")

        self.assertEqual(len(tracks), 1)
        self.assertEqual(bot.sid_durations[tracks[0]], 182)


if __name__ == "__main__":
    unittest.main()
