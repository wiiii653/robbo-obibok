"""ASMA Radio Bot - Shuffled chiptune radio from Atari SAP Music Archive

Commands:
  !play / !radio  - Start shuffled radio from all ASMA tracks
  !stop           - Stop playback and disconnect
  !skip / !next   - Skip to next track
  !np             - Show current track
  !refresh        - Re-crawl ASMA and rebuild playlist
"""

import discord
from discord.ext import commands
import requests
import subprocess
import os
import tempfile
import asyncio
import random
import json
import re
import time
import aiohttp
from urllib.parse import urljoin

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SINK_NAME = "asma_bot"
TEMP_DIR = tempfile.mkdtemp(prefix="asma_bot_")
ASMA_BASE = "https://asma.atari.org/asma/"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asma_cache.json")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_streams: dict[int, "MonitorAudioSource"] = {}

# ── Playlist state ──────────────────────────────────────────────
class PlaylistState:
    def __init__(self):
        self.tracks: list[str] = []      # all known SAP URLs
        self.queue: list[str] = []       # shuffled play queue
        self.index: int = -1             # current position in queue
        self.loop: bool = True
        self.guild_id: int | None = None
        self.ctx = None
        self.vc = None
        self.current_sap_path: str | None = None
        self.crawling: bool = False

playlist_state = PlaylistState()

# ── Audio Capture ───────────────────────────────────────────────
class MonitorAudioSource(discord.AudioSource):
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
        self.buffer = self.buffer[self.FRAME_SIZE:]
        return frame

    def cleanup(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

# ── Audio Infrastructure ──────────────────────────────────────
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
    subprocess.run(["audtool", "playlist-clear"], capture_output=True)
    subprocess.run(["audtool", "playlist-addurl", filepath], capture_output=True)
    subprocess.run(["audtool", "playback-play"], capture_output=True)
    time.sleep(0.5)
    move_playback_to_sink()

def audacious_stop():
    subprocess.run(["audtool", "playback-stop"], capture_output=True)

def audacious_song() -> str:
    r = subprocess.run(["audtool", "current-song"], capture_output=True, text=True)
    return r.stdout.strip()

def is_playing() -> bool:
    r = subprocess.run(["audtool", "playback-playing"], capture_output=True)
    return r.returncode == 0

# ── ASMA Crawler ────────────────────────────────────────────────
SAP_RE = re.compile(r'href="([^"]+\.sap)"', re.IGNORECASE)
DIR_RE = re.compile(r'href="([^"]+)/"')

TOP_LEVEL_DIRS = ["Composers/", "Games/", "Groups/", "Misc/", "Unknown/"]

async def crawl_directory(session: aiohttp.ClientSession, url: str, depth: int = 0) -> list[str]:
    """Recursively crawl an ASMA directory and return .sap file URLs."""
    if depth > 10:
        return []
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()
    except Exception:
        return []
    
    tracks = []
    
    # Find .sap files
    for match in SAP_RE.finditer(html):
        sap_rel = match.group(1)
        sap_url = urljoin(url, sap_rel)
        tracks.append(sap_url)
    
    # Find subdirectories and recurse
    seen_dirs = set()
    for match in DIR_RE.finditer(html):
        subdir = match.group(1)
        # Skip parent and special dirs
        if subdir in ("..", "."):
            continue
        if subdir not in seen_dirs:
            seen_dirs.add(subdir)
            sub_url = urljoin(url, subdir + "/")
            try:
                sub_tracks = await crawl_directory(session, sub_url, depth + 1)
                tracks.extend(sub_tracks)
            except Exception:
                continue
    
    return tracks

async def refresh_tracklist() -> list[str]:
    """Crawl all top-level ASMA directories and return every .sap URL."""
    all_tracks = []
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        for top_dir in TOP_LEVEL_DIRS:
            url = urljoin(ASMA_BASE, top_dir)
            tracks = await crawl_directory(session, url)
            all_tracks.extend(tracks)
    
    # Save cache
    cache_data = {"tracks": all_tracks, "count": len(all_tracks)}
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception:
        pass
    
    return all_tracks

def load_cached_tracklist() -> list[str] | None:
    """Load cached tracklist if available and recent (< 24h)."""
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        age = time.time() - os.path.getmtime(CACHE_FILE)
        if age > 86400:  # 24h cache
            return None
        with open(CACHE_FILE) as f:
            data = json.load(f)
        return data.get("tracks", [])
    except Exception:
        return None

# ── Playback control ────────────────────────────────────────────
async def play_current_track(ctx):
    """Download and play the current track from the queue."""
    if playlist_state.index < 0 or playlist_state.index >= len(playlist_state.queue):
        await ctx.send("Queue empty. Use !play to rebuild.")
        return False
    
    url = playlist_state.queue[playlist_state.index]
    await ctx.send(f"Loading... `{url.split('/')[-1]}`")
    
    try:
        filepath = await asyncio.get_event_loop().run_in_executor(None, download_sap, url)
        await asyncio.get_event_loop().run_in_executor(None, audacious_play, filepath)
        
        playlist_state.current_sap_path = filepath
        
        # Re-create voice source if needed
        if playlist_state.vc and playlist_state.vc.is_connected():
            if playlist_state.guild_id in active_streams:
                active_streams[playlist_state.guild_id].cleanup()
                del active_streams[playlist_state.guild_id]
            
            source = MonitorAudioSource(SINK_NAME)
            playlist_state.vc.play(
                source,
                after=lambda e: print(f"Stream ended: {e}")
            )
            active_streams[playlist_state.guild_id] = source
        
        track = await asyncio.get_event_loop().run_in_executor(None, audacious_song)
        total = len(playlist_state.queue)
        pos = playlist_state.index + 1
        await ctx.send(f"🎵 **{track or url.split('/')[-1]}** ({pos}/{total})")
        return True
    
    except Exception as e:
        await ctx.send(f"Error playing `{url}`: {e}")
        return False

async def skip_to_next(ctx):
    """Skip to next track and play it."""
    if not playlist_state.queue:
        await ctx.send("No tracks in queue. Use !play.")
        return
    
    playlist_state.index += 1
    
    if playlist_state.index >= len(playlist_state.queue):
        if playlist_state.loop:
            random.shuffle(playlist_state.queue)
            playlist_state.index = 0
            await ctx.send("🔁 Loop: reshuffling playlist...")
        else:
            await ctx.send("Playlist ended.")
            if playlist_state.vc and playlist_state.vc.is_connected():
                await playlist_state.vc.disconnect()
            return
    
    await play_current_track(playlist_state.ctx or ctx)

# ── Bot Events ──────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Ready: {bot.user}")
    await asyncio.get_event_loop().run_in_executor(None, setup_virtual_sink)
    await asyncio.get_event_loop().run_in_executor(None, ensure_audacious)
    
    # Preload cached tracklist
    cached = load_cached_tracklist()
    if cached:
        playlist_state.tracks = cached
        print(f"Loaded {len(cached)} tracks from cache")

# ── Commands ────────────────────────────────────────────────────
@bot.command(aliases=["radio"])
async def play(ctx: commands.Context):
    """Start shuffled ASMA radio. Joins your voice channel and plays all ASMA tracks shuffled."""
    if not ctx.author.voice:
        return await ctx.send("Join a voice channel first!")
    
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    
    vc = await ctx.author.voice.channel.connect()
    playlist_state.vc = vc
    playlist_state.guild_id = ctx.guild.id
    playlist_state.ctx = ctx
    playlist_state.loop = True
    
    await ctx.send("🎛️ **ASMA Radio starting...**")
    
    # Ensure we have tracks
    if not playlist_state.tracks:
        await ctx.send("🔍 Crawling ASMA archive (6400+ tracks)... this may take a minute.")
        playlist_state.crawling = True
        tracks = await refresh_tracklist()
        playlist_state.tracks = tracks
        playlist_state.crawling = False
        await ctx.send(f"📀 Found **{len(tracks)}** tracks!")
    else:
        tracks = playlist_state.tracks
        await ctx.send(f"📀 Using cached playlist: **{len(tracks)}** tracks")
    
    # Shuffle and start
    playlist_state.queue = list(tracks)
    random.shuffle(playlist_state.queue)
    playlist_state.index = 0
    
    if await play_current_track(ctx):
        bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))


@bot.command()
async def stop(ctx: commands.Context):
    """Stop playback and disconnect."""
    if playlist_state.guild_id and playlist_state.guild_id in active_streams:
        active_streams[playlist_state.guild_id].cleanup()
        del active_streams[playlist_state.guild_id]
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    playlist_state.queue = []
    playlist_state.index = -1
    await ctx.send("⏹️ Stopped.")


@bot.command(aliases=["next"])
async def skip(ctx: commands.Context):
    """Skip to next track."""
    if not playlist_state.queue:
        return await ctx.send("Nothing playing.")
    await skip_to_next(ctx)


@bot.command()
async def np(ctx: commands.Context):
    """Show current track info."""
    if not is_playing():
        return await ctx.send("Nothing playing right now.")
    track = await asyncio.get_event_loop().run_in_executor(None, audacious_song)
    total = len(playlist_state.queue)
    pos = playlist_state.index + 1
    await ctx.send(f"🎵 Now playing: **{track}** ({pos}/{total})")


@bot.command()
async def refresh(ctx: commands.Context):
    """Re-crawl ASMA and rebuild the playlist."""
    await ctx.send("🔍 Re-crawling ASMA archive... this may take a minute.")
    tracks = await refresh_tracklist()
    playlist_state.tracks = tracks
    await ctx.send(f"✅ Refreshed! Found **{len(tracks)}** tracks.")


@bot.command()
async def stats(ctx: commands.Context):
    """Show radio stats."""
    total = len(playlist_state.tracks)
    queue_len = len(playlist_state.queue)
    pos = playlist_state.index + 1 if playlist_state.index >= 0 else 0
    playing = "🎵 Yes" if is_playing() else "⏸️ No"
    loop = "🔁 On" if playlist_state.loop else "➡️ Off"
    await ctx.send(
        f"📊 **ASMA Radio Stats**\n"
        f"• Total tracks in archive: **{total}**\n"
        f"• Queue remaining: **{queue_len - pos}/{queue_len}**\n"
        f"• Playing: {playing}\n"
        f"• Loop: {loop}"
    )

# ── Playback Monitor ────────────────────────────────────────────
async def monitor_playback(ctx: commands.Context, vc: discord.VoiceClient, guild_id: int):
    """Monitor playback and auto-advance when track ends."""
    while vc.is_connected():
        await asyncio.sleep(1)
        playing = await asyncio.get_event_loop().run_in_executor(None, is_playing)
        if not playing:
            # Track finished - advance to next
            if playlist_state.loop or playlist_state.index < len(playlist_state.queue) - 1:
                await skip_to_next(ctx)
                # Continue monitoring
                continue
            else:
                # Last track, no loop
                if guild_id in active_streams:
                    active_streams[guild_id].cleanup()
                    del active_streams[guild_id]
                if vc.is_connected():
                    await vc.disconnect()
                await ctx.send("Playlist ended. Use !play to restart.")
                break
    
    # Cleanup on disconnect
    if guild_id in active_streams:
        active_streams[guild_id].cleanup()
        del active_streams[guild_id]

# ── Main ────────────────────────────────────────────────────────
if not BOT_TOKEN:
    raise SystemExit("Set DISCORD_BOT_TOKEN environment variable.")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
