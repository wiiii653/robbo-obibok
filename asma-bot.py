"""
ASMA Discord Bot - Plays Atari SAP music from https://asma.atari.org/ via Audacious.

Setup:
    sudo apt install audacious audacious-plugins ffmpeg
    pip install discord.py requests
    export DISCORD_BOT_TOKEN="your-token-here"

Architecture:
    1. Virtual PulseAudio/PipeWire sink isolates bot audio
    2. Audacious headless decodes SAP files via audtool IPC
    3. FFmpeg captures the sink monitor and pipes PCM to Discord
"""

import discord
from discord.ext import commands
import requests
import subprocess
import os
import tempfile
import asyncio

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SINK_NAME = "asma_bot"
TEMP_DIR = tempfile.mkdtemp(prefix="asma_bot_")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_streams: dict[int, "MonitorAudioSource"] = {}


class MonitorAudioSource(discord.AudioSource):
    """Captures audio from a PulseAudio/PipeWire monitor via FFmpeg."""

    FRAME_SIZE = 3840  # 20ms @ 48kHz stereo s16le

    def __init__(self, sink_name: str):
        self.buffer = b""
        self.process = subprocess.Popen(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "pulse", "-i", f"{sink_name}.monitor",
                "-f", "s16le", "-ar", "48000", "-ac", "2",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def read(self) -> bytes:
        while len(self.buffer) < self.FRAME_SIZE:
            chunk = self.process.stdout.read(4096)
            if not chunk:
                return b""
            self.buffer += chunk
        frame = self.buffer[: self.FRAME_SIZE]
        self.buffer = self.buffer[self.FRAME_SIZE :]
        return frame

    def cleanup(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


def setup_virtual_sink():
    result = subprocess.run(
        ["pactl", "list", "sinks", "short"], capture_output=True, text=True
    )
    if SINK_NAME not in result.stdout:
        subprocess.run(
            [
                "pactl", "load-module", "module-null-sink",
                f"sink_name={SINK_NAME}",
                f"sink_properties=device.description=ASMA_Bot",
            ],
            check=True,
        )


def ensure_audacious():
    result = subprocess.run(["pgrep", "-x", "audacious"], capture_output=True)
    if result.returncode != 0:
        subprocess.Popen(
            ["audacious", "--headless"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import time
        time.sleep(2)


def move_playback_to_sink():
    result = subprocess.run(
        ["pactl", "list", "sink-inputs", "short"], capture_output=True, text=True
    )
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            subprocess.run(
                ["pactl", "move-sink-input", parts[0], SINK_NAME],
                capture_output=True,
            )


def download_sap(url: str) -> str:
    filename = url.split("/")[-1]
    filepath = os.path.join(TEMP_DIR, filename)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    with open(filepath, "wb") as f:
        f.write(resp.content)
    return filepath


def audacious_play(filepath: str):
    subprocess.run(["audtool", "--playlist-clear"], capture_output=True)
    subprocess.run(["audtool", "--playlist-add", filepath], capture_output=True)
    subprocess.run(["audtool", "--play"], capture_output=True)
    import time
    time.sleep(0.5)
    move_playback_to_sink()


def audacious_stop():
    subprocess.run(["audtool", "--stop"], capture_output=True)


def audacious_song() -> str:
    r = subprocess.run(["audtool", "--current-song"], capture_output=True, text=True)
    return r.stdout.strip()


def is_playing() -> bool:
    r = subprocess.run(["audtool", "--is-playing"], capture_output=True)
    return r.returncode == 0


async def monitor_playback(ctx: commands.Context, vc: discord.VoiceClient, guild_id: int):
    while vc.is_connected():
        await asyncio.sleep(2)
        playing = await asyncio.get_event_loop().run_in_executor(None, is_playing)
        if not playing:
            if guild_id in active_streams:
                active_streams[guild_id].cleanup()
                del active_streams[guild_id]
            if vc.is_connected():
                await vc.disconnect()
            await ctx.send("Playback finished.")
            break


@bot.command()
async def play(ctx: commands.Context, url: str):
    if not ctx.author.voice:
        return await ctx.send("Join a voice channel first!")
    if not url.startswith("https://asma.atari.org/"):
        return await ctx.send("Provide a valid ASMA URL.")

    if ctx.voice_client:
        await ctx.voice_client.disconnect()

    vc = await ctx.author.voice.channel.connect()
    await ctx.send("Downloading SAP...")

    try:
        loop = asyncio.get_event_loop()
        filepath = await loop.run_in_executor(None, download_sap, url)
        await loop.run_in_executor(None, audacious_play, filepath)

        source = MonitorAudioSource(SINK_NAME)
        vc.play(source, after=lambda e: print(f"Stream ended: {e}"))
        active_streams[ctx.guild.id] = source

        track = await loop.run_in_executor(None, audacious_song)
        await ctx.send(f"Now playing: **{track or url.split('/')[-1]}**")

        bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))

    except Exception as e:
        await ctx.send(f"Error: {e}")
        if vc.is_connected():
            await vc.disconnect()


@bot.command()
async def stop(ctx: commands.Context):
    if ctx.guild.id in active_streams:
        active_streams[ctx.guild.id].cleanup()
        del active_streams[ctx.guild.id]
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    await ctx.send("Stopped.")


@bot.event
async def on_ready():
    print(f"Ready: {bot.user}")
    await asyncio.get_event_loop().run_in_executor(None, setup_virtual_sink)
    await asyncio.get_event_loop().run_in_executor(None, ensure_audacious)


if not BOT_TOKEN:
    raise SystemExit("Set DISCORD_BOT_TOKEN environment variable.")

bot.run(BOT_TOKEN)
