from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def run_python(code: str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    runtime_env = dict(os.environ)
    runtime_env["PYTHONPATH"] = str(ROOT)
    if env:
        runtime_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=runtime_env,
        capture_output=True,
        text=True,
        timeout=30,
    )


class RealDependencyIntegrationTests(unittest.TestCase):
    def test_real_discord_sdk_constructs_and_closes_bot(self):
        result = run_python(
            """
import asyncio
import discord
from discord.ext import commands

async def main():
    assert hasattr(discord, "__version__")
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
    assert bot.command_prefix == "!"
    await bot.close()

asyncio.run(main())
"""
        )
        if result.returncode != 0 and "No module named 'discord'" in result.stderr:
            self.skipTest("discord.py is not installed in this interpreter")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_ffmpeg_generates_and_probes_pcm_audio(self):
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            self.skipTest("ffmpeg and ffprobe are required")

        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "tone.wav"
            generate = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=0.1",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    str(wav_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(generate.returncode, 0, msg=generate.stderr)
            self.assertGreater(wav_path.stat().st_size, 44)

            probe = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=codec_name,sample_rate,channels",
                    "-of",
                    "json",
                    str(wav_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(probe.returncode, 0, msg=probe.stderr)
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream["codec_name"], "pcm_s16le")
            self.assertEqual(stream["sample_rate"], "48000")
            self.assertEqual(stream["channels"], 2)

    @unittest.skipUnless(
        os.environ.get("DISCORD_INTEGRATION_TOKEN"),
        "DISCORD_INTEGRATION_TOKEN is not configured",
    )
    def test_discord_token_authenticates(self):
        result = run_python(
            """
import asyncio
import os
import discord
from discord.ext import commands

async def main():
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
    try:
        await bot.login(os.environ["DISCORD_INTEGRATION_TOKEN"])
        assert bot.user is not None
    finally:
        await bot.close()

asyncio.run(main())
""",
            env={"DISCORD_INTEGRATION_TOKEN": os.environ["DISCORD_INTEGRATION_TOKEN"]},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    @unittest.skipUnless(
        os.environ.get("RUN_LIVE_AUDIO_INTEGRATION") == "1",
        "RUN_LIVE_AUDIO_INTEGRATION=1 is required",
    )
    def test_live_audio_services_are_reachable(self):
        for command in (["pactl", "info"], ["audacious", "--version"]):
            if shutil.which(command[0]) is None:
                self.fail(f"required executable is missing: {command[0]}")
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
