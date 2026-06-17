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
import subprocess
import os
import tempfile
import asyncio
import random
import json
import re
import time
import logging
import shutil
import signal
import sys
import aiohttp
import yaml
from urllib.parse import urljoin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("asma-bot")

# ── Config Loader ────────────────────────────────────────────────
def load_config() -> dict:
    """Load config.yaml from the same directory as this script.
    Returns a dict with all keys present (missing keys get defaults)."""
    defaults = {
        "command_prefix": "!",
        "asma": {
            "base_url": "https://asma.atari.org/asma/",
            "top_dirs": ["Composers/", "Games/", "Groups/", "Misc/", "Unknown/"],
            "crawl_timeout": 15,
            "cache_ttl": 24,
            "crawl_concurrency": 5,
        },
        "audio": {
            "sink_name": "asma_bot",
            "sample_rate": 48000,
            "channels": 2,
            "format": "s16le",
        },
        "playback": {
            "loop": True,
            "shuffle": True,
            "crossfade": 0,
        },
        "auto": {
            "start_channel": "",
            "empty_timeout": 60,
        },
    }
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path) as f:
                user_cfg = yaml.safe_load(f) or {}
            # Deep merge: user values override defaults
            def deep_merge(base, override):
                for k, v in override.items():
                    if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                        deep_merge(base[k], v)
                    else:
                        base[k] = v
            deep_merge(defaults, user_cfg)
        except Exception as e:
            log.warning("Failed to load config.yaml: %s", e)
    return defaults

CONFIG = load_config()

# ── Environment / Config values ──────────────────────────────────
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", CONFIG.get("token", ""))
SINK_NAME = CONFIG["audio"]["sink_name"]
TEMP_DIR = tempfile.mkdtemp(prefix="asma_bot_")
ASMA_BASE = CONFIG["asma"]["base_url"]
CRAWL_TIMEOUT = CONFIG["asma"]["crawl_timeout"]
CACHE_TTL = CONFIG["asma"]["cache_ttl"]
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asma_cache.json")
QUEUE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "queues")
COMMAND_PREFIX = CONFIG["command_prefix"]
PLAYBACK_LOOP = CONFIG["playback"]["loop"]
PLAYBACK_SHUFFLE = CONFIG["playback"]["shuffle"]

# ── Favorites System ────────────────────────────────────────────
FAVORITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favorites.json")
OGNJEN_USER_ID = 693164855066099814  # Master's Discord ID

# ── HVSC Collection (C64 SID) ────────────────────────────────────
HVSC_BASE = CONFIG.get("hvsc", {}).get("base_url", "https://www.hvsc.c64.org/download/C64Music/")
HVSC_SONGLENGTHS_URL = CONFIG.get("hvsc", {}).get("songlengths_url", "")
HVSC_CACHE_TTL = CONFIG.get("hvsc", {}).get("cache_ttl", 168)
HVSC_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hvsc_cache.json")
COLLECTION_MODE = "hvsc" if CONFIG.get("hvsc", {}).get("enabled", False) else "asma"
gst_process: subprocess.Popen | None = None  # GStreamer process for SID playback

CROSSFADE_SECS = CONFIG["playback"].get("crossfade", 0)
AUTO_START_CHANNEL = CONFIG["auto"].get("start_channel", "")
AUTO_EMPTY_TIMEOUT = CONFIG["auto"].get("empty_timeout", 60)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

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
        self.pre_downloaded: str | None = None  # next track pre-downloaded
        self.search_results: list[str] = []     # last search results

guilds: dict[int, PlaylistState] = {}

# Track message IDs → track info for reaction-based favorites
message_track_map: dict[int, dict] = {}

def get_state(guild_id: int) -> PlaylistState:
    if guild_id not in guilds:
        guilds[guild_id] = PlaylistState()
    return guilds[guild_id]

def save_queue(state: PlaylistState):
    """Persist queue to disk for this guild."""
    if not state.guild_id:
        return
    os.makedirs(QUEUE_DIR, exist_ok=True)
    path = os.path.join(QUEUE_DIR, f"{state.guild_id}.json")
    data = {
        "queue": state.queue,
        "index": state.index,
        "loop": state.loop,
    }
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def load_queue(guild_id: int) -> dict | None:
    """Load persisted queue for a guild, or None."""
    path = os.path.join(QUEUE_DIR, f"{guild_id}.json")
    try:
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

# ── Audio Capture ───────────────────────────────────────────────
class MonitorAudioSource(discord.AudioSource):
    FRAME_SIZE = 3840  # 20ms @ 48kHz stereo s16le

    def __init__(self, sink_name: str):
        self.buffer = b""
        self.sink_name = sink_name
        self.process = self._start_ffmpeg()

    def _start_ffmpeg(self) -> subprocess.Popen:
        return subprocess.Popen(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "pulse", "-i", f"{self.sink_name}.monitor",
                "-f", CONFIG["audio"]["format"],
                "-ar", str(CONFIG["audio"]["sample_rate"]),
                "-ac", str(CONFIG["audio"]["channels"]),
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def _restart_ffmpeg(self):
        self.cleanup()
        self.process = self._start_ffmpeg()

    def read(self) -> bytes:
        while len(self.buffer) < self.FRAME_SIZE:
            if self.process.poll() is not None:
                time.sleep(0.1)
                self._restart_ffmpeg()
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

async def download_sap(url: str, retries: int = 2) -> str:
    filename = url.split("/")[-1]
    filepath = os.path.join(TEMP_DIR, filename)
    last_err = None
    for attempt in range(retries + 1):
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
            with open(filepath, "wb") as f:
                f.write(data)
            return filepath
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = e
            if attempt < retries:
                await asyncio.sleep(1)
    raise last_err

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

# ── SAP Metadata Parser ──────────────────────────────────────────
SAP_HEADER_RE = re.compile(rb'^;(.+)', re.MULTILINE)

def parse_sap_header(filepath: str) -> dict[str, str]:
    """Parse SAP file header for metadata (AUTHOR, NAME, etc.)."""
    meta = {}
    try:
        with open(filepath, "rb") as f:
            header = f.read(4096)
        for match in SAP_HEADER_RE.finditer(header):
            line = match.group(1).decode("ascii", errors="replace").strip()
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip().upper()] = val.strip()
    except Exception:
        pass
    return meta

def extract_searchable_text(url: str) -> str:
    """Extract searchable text from a SAP URL (directories + filename)."""
    # https://asma.atari.org/asma/Composers/Krzysztof_Bryla/Track_Name.sap
    # -> "krzysztof bryla track name"
    path = url.replace(ASMA_BASE, "")
    parts = path.replace(".sap", "").replace("_", " ").split("/")
    return " ".join(parts).lower()

# ── Metadata Index ──────────────────────────────────────────────
metadata_index: dict[str, dict[str, str]] = {}  # url -> {author, name, ...}
METADATA_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata_cache.json")

def load_metadata_cache() -> dict:
    try:
        if os.path.exists(METADATA_CACHE):
            with open(METADATA_CACHE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_metadata_cache(index: dict):
    try:
        with open(METADATA_CACHE, "w") as f:
            json.dump(index, f, indent=2)
    except Exception:
        pass

async def fetch_metadata_batch(session: aiohttp.ClientSession, urls: list[str], batch_size: int = 20):
    """Fetch SAP headers for metadata (just first 4KB of each file)."""
    results = {}
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i+batch_size]
        tasks = []
        for url in batch:
            if url in metadata_index:
                continue
            tasks.append(fetch_single_metadata(session, url))
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for url, result in zip(batch, batch_results):
                if isinstance(result, dict) and result:
                    results[url] = result
        if results:
            metadata_index.update(results)
            save_metadata_cache(metadata_index)
    return results

async def fetch_single_metadata(session: aiohttp.ClientSession, url: str) -> dict[str, str]:
    """Fetch just the header of a SAP file for metadata."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return {}
            # Read only first 4KB for header
            data = await resp.content.read(4096)
            meta = {}
            for match in SAP_HEADER_RE.finditer(data):
                line = match.group(1).decode("ascii", errors="replace").strip()
                if ":" in line:
                    key, _, val = line.partition(":")
                    meta[key.strip().upper()] = val.strip()
            return meta
    except Exception:
        return {}

def search_tracks(query: str, tracks: list[str], limit: int = 10) -> list[str]:
    """Search tracks by filename, directory path, or metadata."""
    query_lower = query.lower()
    results = []
    
    for url in tracks:
        # 1. Filename match
        filename = url.split("/")[-1].replace(".sap", "").replace("_", " ")
        if query_lower in filename.lower():
            results.append(url)
            if len(results) >= limit:
                break
            continue
        
        # 2. Directory path match
        searchable = extract_searchable_text(url)
        if query_lower in searchable:
            results.append(url)
            if len(results) >= limit:
                break
            continue
        
        # 3. Metadata match
        meta = metadata_index.get(url, {})
        for field in ("AUTHOR", "NAME", "SONGS"):
            if query_lower in meta.get(field, "").lower():
                results.append(url)
                if len(results) >= limit:
                    break
                break
    
    return results

# ── ASMA Crawler ────────────────────────────────────────────────
SAP_RE = re.compile(r'href="([^"]+\.sap)"', re.IGNORECASE)
DIR_RE = re.compile(r'href="([^"]+)/"')

TOP_LEVEL_DIRS = CONFIG["asma"]["top_dirs"]
CRAWL_SEMAPHORE = asyncio.Semaphore(CONFIG["asma"].get("crawl_concurrency", 5))

async def crawl_directory(session: aiohttp.ClientSession, url: str, depth: int = 0) -> list[str]:
    """Recursively crawl an ASMA directory and return .sap file URLs."""
    if depth > 10:
        return []
    
    async with CRAWL_SEMAPHORE:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=CRAWL_TIMEOUT)) as resp:
                if resp.status != 200:
                    log.warning("HTTP %d for %s", resp.status, url)
                    return []
                html = await resp.text()
        except asyncio.TimeoutError:
            log.warning("TIMEOUT %s", url)
            return []
        except Exception as e:
            log.error("ERROR %s: %s", url, e)
            return []
    
    tracks = []
    
    # Find .sap files
    for match in SAP_RE.finditer(html):
        sap_rel = match.group(1)
        sap_url = urljoin(url, sap_rel)
        tracks.append(sap_url)
    
    # Find subdirectories and recurse IN PARALLEL
    seen_dirs = set()
    sub_tasks = []
    for match in DIR_RE.finditer(html):
        subdir = match.group(1)
        # Skip parent traversal (absolute paths like /asma/) and special dirs
        if subdir in ("..", ".") or subdir.startswith("/") or "?" in subdir:
            continue
        if subdir not in seen_dirs:
            seen_dirs.add(subdir)
            sub_url = urljoin(url, subdir + "/")
            sub_tasks.append(crawl_directory(session, sub_url, depth + 1))
    
    if sub_tasks:
        results = await asyncio.gather(*sub_tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                tracks.extend(r)
    
    return tracks

async def refresh_tracklist() -> list[str]:
    """Crawl all top-level ASMA directories and return every .sap URL."""
    all_tracks = []
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        for i, top_dir in enumerate(TOP_LEVEL_DIRS):
            url = urljoin(ASMA_BASE, top_dir)
            log.info("[%d/%d] Crawling %s...", i+1, len(TOP_LEVEL_DIRS), top_dir)
            tracks = await crawl_directory(session, url)
            log.info("  -> %d tracks found in %s", len(tracks), top_dir)
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
        if age > CACHE_TTL * 3600:  # cache TTL in hours
            return None
        with open(CACHE_FILE) as f:
            data = json.load(f)
        return data.get("tracks", [])
    except Exception:
        return None

# Pre-load metadata index on startup
metadata_index.update(load_metadata_cache())

# ── Playback control ────────────────────────────────────────────
async def pre_download_next(state: PlaylistState):
    """Pre-download the next track in the queue for gapless transitions."""
    next_idx = state.index + 1
    if next_idx >= len(state.queue):
        if state.loop:
            next_idx = 0
        else:
            return
    url = state.queue[next_idx]
    try:
        filepath = await download_sap(url, retries=1)
        state.pre_downloaded = filepath
    except Exception:
        state.pre_downloaded = None


async def play_current_sid_track(ctx, state, url):
    """Download and play a SID track via GStreamer."""
    # Download full SID to temp (they're small, ~5-15KB)
    sid_path = os.path.join(TEMP_DIR, url.split("/")[-1])
    try:
        # Use async HTTP download
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.read()
        with open(sid_path, "wb") as f:
            f.write(data)
    except Exception as e:
        log.error("SID download failed: %s", e)
        await ctx.send(f"❌ Download failed: {e}")
        return False

    # Parse SID header for metadata
    meta = parse_sid_header(data)
    name = meta.get("name") or url.split("/")[-1].replace(".sid", "")
    author = meta.get("author", "")
    copyright_info = meta.get("copyright", "")

    # Play via GStreamer — stop Audacious first so they don't bleed
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    await asyncio.get_event_loop().run_in_executor(None, gst_play_sid, sid_path)
    state.current_sap_path = sid_path

    # Setup MonitorAudioSource if needed
    if state.vc and state.vc.is_connected():
        if state.guild_id not in active_streams:
            source = MonitorAudioSource(SINK_NAME)
            state.vc.play(
                source,
                after=lambda e: log.info("Stream ended: %s", e),
            )
            active_streams[state.guild_id] = source

    total = len(state.queue)
    pos = state.index + 1

    embed = discord.Embed(
        title=name,
        color=discord.Color.purple(),
    )
    if author:
        embed.add_field(name="Composer", value=author, inline=True)
    if copyright_info:
        embed.add_field(name="Copyright", value=copyright_info, inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    embed.set_footer(text="C64 SID Radio")
    np_msg = await ctx.send(embed=embed)

    # Track for reaction-based favorites
    message_track_map[np_msg.id] = {
        "url": url,
        "name": name,
        "author": author,
        "timestamp": time.time(),
    }
    log.info("SID now playing: %s — %s", name, author)
    return True


async def play_current_track(ctx):
    """Download and play the current track from the queue."""
    state = get_state(ctx.guild.id)
    if state.index < 0 or state.index >= len(state.queue):
        await ctx.send("Queue empty. Use !play to rebuild.")
        return False
    
    url = state.queue[state.index]
    await ctx.send(f"Loading... `{url.split('/')[-1]}`")
    
    try:
        if COLLECTION_MODE == "hvsc":
            return await play_current_sid_track(ctx, state, url)
        
        # ── ASMA SAP Playback ────────────────────────────────────
        # Use pre-downloaded track if available, otherwise download now
        if state.pre_downloaded and os.path.exists(state.pre_downloaded):
            filepath = state.pre_downloaded
            state.pre_downloaded = None
        else:
            filepath = await download_sap(url)
        await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
        await asyncio.get_event_loop().run_in_executor(None, audacious_play, filepath)
        
        state.current_sap_path = filepath
        
        # Only create MonitorAudioSource once per guild; reuse across tracks
        if state.vc and state.vc.is_connected():
            if state.guild_id not in active_streams:
                source = MonitorAudioSource(SINK_NAME)
                state.vc.play(
                    source,
                    after=lambda e: log.info("Stream ended: %s", e)
                )
                active_streams[state.guild_id] = source
        
        track = await asyncio.get_event_loop().run_in_executor(None, audacious_song)
        total = len(state.queue)
        pos = state.index + 1
        meta = parse_sap_header(filepath)
        name = meta.get("NAME", track or url.split("/")[-1])
        author = meta.get("AUTHOR", "")
        songs = meta.get("SONGS", "")

        embed = discord.Embed(
            title=name,
            color=discord.Color.green(),
        )
        if author:
            embed.add_field(name="Composer", value=author, inline=True)
        if songs:
            embed.add_field(name="Songs", value=songs, inline=True)
        embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
        embed.set_footer(text="ASMA Radio")
        np_msg = await ctx.send(embed=embed)
        # Track for reaction-based favorites
        message_track_map[np_msg.id] = {
            "url": url,
            "name": name,
            "author": author,
            "timestamp": time.time(),
        }
        return True
    
    except Exception as e:
        await ctx.send(f"Error playing `{url}`: {e}")
        return False

async def skip_to_next(ctx):
    """Skip to next track and play it."""
    state = get_state(ctx.guild.id)
    if not state.queue:
        await ctx.send("No tracks in queue. Use !play.")
        return
    
    state.index += 1
    
    if state.index >= len(state.queue):
        if state.loop:
            random.shuffle(state.queue)
            state.index = 0
            await ctx.send("🔁 Loop: reshuffling playlist...")
        else:
            await ctx.send("Playlist ended.")
            if state.vc and state.vc.is_connected():
                await state.vc.disconnect()
            return
    
    save_queue(state)
    await play_current_track(state.ctx or ctx)

# ── Bot Events ──────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info("Ready: %s", bot.user)
    await asyncio.get_event_loop().run_in_executor(None, setup_virtual_sink)
    await asyncio.get_event_loop().run_in_executor(None, ensure_audacious)
    
    # Preload cached tracklist for all guilds
    cached = load_cached_tracklist()
    if cached:
        log.info("Loaded %d tracks from cache", len(cached))

    # Start health watchdog
    bot.loop.create_task(health_watchdog())
    
    # Start background metadata fetching
    bot.loop.create_task(fetch_metadata_background())


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Auto-start radio when someone joins the configured channel."""
    if not AUTO_START_CHANNEL or member.bot:
        return
    if before.channel == after.channel:
        return
    if after.channel is None:
        return
    if after.channel.name != AUTO_START_CHANNEL:
        return
    if member.guild.voice_client:
        return

    log.info("Auto-start: %s joined %s", member.display_name, after.channel.name)
    try:
        vc = await after.channel.connect()
        state = get_state(member.guild.id)
        state.vc = vc
        state.guild_id = member.guild.id
        state.loop = PLAYBACK_LOOP

        if not state.tracks:
            state.tracks = await refresh_tracklist()

        if not state.tracks:
            log.warning("Auto-start: no tracks available")
            await vc.disconnect()
            return

        saved = load_queue(member.guild.id)
        if saved and saved.get("queue") and saved["queue"][0] in state.tracks:
            state.queue = saved["queue"]
            state.index = saved.get("index", 0)
            state.loop = saved.get("loop", PLAYBACK_LOOP)
        else:
            state.queue = list(state.tracks)
            if PLAYBACK_SHUFFLE:
                random.shuffle(state.queue)
            state.index = 0

        # Use system channel or first text channel for messages
        text_channel = member.guild.system_channel or member.guild.text_channels[0]
        ctx = await bot.get_context(await text_channel.send("📻 **Auto-starting ASMA Radio...**"))
        state.ctx = ctx

        if await play_current_track(ctx):
            save_queue(state)
            bot.loop.create_task(monitor_playback(ctx, vc, member.guild.id))
    except Exception as e:
        log.error("Auto-start failed: %s", e)

# ── Commands ────────────────────────────────────────────────────
@bot.command(aliases=["radio"])
async def play(ctx: commands.Context, *, query: str = ""):
    """Start shuffled ASMA radio. Usage: !play, !play <number>, or !play <search query>"""
    if not ctx.author.voice:
        return await ctx.send("Join a voice channel first!")

    state = get_state(ctx.guild.id)

    # Play from search results by number
    if query.isdigit():
        idx = int(query) - 1
        if not state.search_results or idx < 0 or idx >= len(state.search_results):
            return await ctx.send("Invalid number. Use !search first.")
        url = state.search_results[idx]
        if not state.tracks:
            state.tracks = await refresh_tracklist()
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        vc = await ctx.author.voice.channel.connect()
        state.vc = vc
        state.guild_id = ctx.guild.id
        state.ctx = ctx
        state.loop = PLAYBACK_LOOP
        state.queue = list(state.tracks)
        if PLAYBACK_SHUFFLE:
            random.shuffle(state.queue)
        try:
            state.index = state.queue.index(url)
        except ValueError:
            state.queue.insert(0, url)
            state.index = 0
        if await play_current_track(ctx):
            save_queue(state)
            bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))
        return

    # Search and play first result
    if query:
        query_lower = query.lower()
        matches = [u for u in state.tracks if query_lower in u.split("/")[-1].replace(".sap", "").replace("_", " ").lower()]
        if matches:
            url = matches[0]
            if not state.tracks:
                state.tracks = await refresh_tracklist()
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
            vc = await ctx.author.voice.channel.connect()
            state.vc = vc
            state.guild_id = ctx.guild.id
            state.ctx = ctx
            state.loop = PLAYBACK_LOOP
            state.queue = list(state.tracks)
            if PLAYBACK_SHUFFLE:
                random.shuffle(state.queue)
            try:
                state.index = state.queue.index(url)
            except ValueError:
                state.queue.insert(0, url)
                state.index = 0
            if await play_current_track(ctx):
                save_queue(state)
                bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))
            return
        return await ctx.send(f"No tracks matching `{query}`. Try !search.")

    # Default: start shuffled radio
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    
    vc = await ctx.author.voice.channel.connect()
    state = get_state(ctx.guild.id)
    state.vc = vc
    state.guild_id = ctx.guild.id
    state.ctx = ctx
    state.loop = PLAYBACK_LOOP
    
    await ctx.send("🎛️ **ASMA Radio starting...**")
    
    # Ensure we have tracks
    if not state.tracks:
        await ctx.send("🔍 Crawling ASMA archive (6400+ tracks)... this may take a minute.")
        state.crawling = True
        try:
            tracks = await refresh_tracklist()
            state.tracks = tracks
            log.info("ASMA crawl complete: %d tracks found", len(tracks))
        except Exception as e:
            log.error("CRASH during crawl: %s", e, exc_info=True)
            state.tracks = []
            await ctx.send(f"❌ Crawl failed: {e}")
        state.crawling = False
        await ctx.send(f"📀 Found **{len(state.tracks)}** tracks!")
    else:
        tracks = state.tracks
        await ctx.send(f"📀 Using cached playlist: **{len(tracks)}** tracks")
    
    # Shuffle and start
    saved = load_queue(ctx.guild.id)
    if saved and saved.get("queue") and saved["queue"][0] in state.tracks:
        state.queue = saved["queue"]
        state.index = saved.get("index", 0)
        state.loop = saved.get("loop", PLAYBACK_LOOP)
        await ctx.send("📋 Restored previous queue.")
    else:
        state.queue = list(state.tracks)
        if PLAYBACK_SHUFFLE:
            random.shuffle(state.queue)
        state.index = 0
    
    if await play_current_track(ctx):
        save_queue(state)
        bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))


@bot.command()
async def stop(ctx: commands.Context):
    """Stop playback and disconnect."""
    state = get_state(ctx.guild.id)
    if state.guild_id and state.guild_id in active_streams:
        active_streams[state.guild_id].cleanup()
        del active_streams[state.guild_id]
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    state.queue = []
    state.index = -1
    save_queue(state)
    await ctx.send("⏹️ Stopped.")


@bot.command(aliases=["next"])
async def skip(ctx: commands.Context):
    """Skip to next track."""
    state = get_state(ctx.guild.id)
    if not state.queue:
        return await ctx.send("Nothing playing.")
    await skip_to_next(ctx)


@bot.command()
async def np(ctx: commands.Context):
    """Show current track info."""
    if not is_playing():
        return await ctx.send("Nothing playing right now.")
    track = await asyncio.get_event_loop().run_in_executor(None, audacious_song)
    state = get_state(ctx.guild.id)
    total = len(state.queue)
    pos = state.index + 1
    meta = {}
    if state.current_sap_path:
        meta = parse_sap_header(state.current_sap_path)
    name = meta.get("NAME", track)
    author = meta.get("AUTHOR", "")
    songs = meta.get("SONGS", "")

    embed = discord.Embed(
        title=f"Now Playing: {name}",
        color=discord.Color.blue(),
    )
    if author:
        embed.add_field(name="Composer", value=author, inline=True)
    if songs:
        embed.add_field(name="Songs", value=songs, inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    embed.set_footer(text="ASMA Radio")
    await ctx.send(embed=embed)


@bot.command()
async def refresh(ctx: commands.Context):
    """Re-crawl ASMA and rebuild the playlist."""
    await ctx.send("🔍 Re-crawling ASMA archive... this may take a minute.")
    tracks = await refresh_tracklist()
    state = get_state(ctx.guild.id)
    state.tracks = tracks
    await ctx.send(f"✅ Refreshed! Found **{len(tracks)}** tracks.")


@bot.command()
async def reindex(ctx: commands.Context):
    """Re-fetch metadata for all tracks (search index)."""
    state = get_state(ctx.guild.id)
    if not state.tracks:
        return await ctx.send("No tracks loaded. Use !play first.")
    
    missing = [url for url in state.tracks if url not in metadata_index]
    if not missing:
        await ctx.send(f"✅ Metadata index complete: **{len(metadata_index)}** tracks.")
        return
    
    await ctx.send(f"🔍 Indexing metadata for **{len(missing)}** tracks... this may take a few minutes.")
    connector = aiohttp.TCPConnector(limit=5, limit_per_host=3)
    async with aiohttp.ClientSession(connector=connector) as session:
        await fetch_metadata_batch(session, missing)
    
    await ctx.send(f"✅ Metadata indexed: **{len(metadata_index)}** tracks total.")


@bot.command()
async def stats(ctx: commands.Context):
    """Show radio stats."""
    state = get_state(ctx.guild.id)
    total = len(state.tracks)
    queue_len = len(state.queue)
    pos = state.index + 1 if state.index >= 0 else 0
    playing = "🎵 Yes" if is_playing() else "⏸️ No"
    loop = "🔁 On" if state.loop else "➡️ Off"
    await ctx.send(
        f"📊 **ASMA Radio Stats**\n"
        f"• Total tracks in archive: **{total}**\n"
        f"• Queue remaining: **{queue_len - pos}/{queue_len}**\n"
        f"• Playing: {playing}\n"
        f"• Loop: {loop}"
    )


@bot.command()
async def search(ctx: commands.Context, *, query: str):
    """Search tracks by name, directory, or author. Usage: !search <query>"""
    state = get_state(ctx.guild.id)
    if not state.tracks:
        return await ctx.send("No tracks loaded. Use !play first.")

    matches = search_tracks(query, state.tracks, limit=10)

    if not matches:
        return await ctx.send(f"No tracks matching `{query}`.")

    state.search_results = matches
    lines = [f"🔍 **Results for `{query}`**"]
    for i, url in enumerate(matches, 1):
        filename = url.split("/")[-1].replace(".sap", "").replace("_", " ")
        # Show directory info if available
        path_parts = url.replace(ASMA_BASE, "").replace(".sap", "").split("/")
        if len(path_parts) > 1:
            dir_name = path_parts[-2].replace("_", " ")
            lines.append(f"`{i}.` {filename} *({dir_name})*")
        else:
            lines.append(f"`{i}.` {filename}")
    lines.append("")
    lines.append("Type `!play <number>` to play a track")
    await ctx.send("\n".join(lines))


# ── Favorites System ────────────────────────────────────────────
def load_favorites() -> dict:
    """Load the favorites database from disk."""
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_favorites(data: dict):
    """Save the favorites database to disk."""
    try:
        with open(FAVORITES_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error("Failed to save favorites: %s", e)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Track Ognjen's reactions on Now Playing embeds → add/remove favorites."""
    if payload.user_id != OGNJEN_USER_ID:
        return
    if payload.message_id not in message_track_map:
        return

    track = message_track_map[payload.message_id]
    favs = load_favorites()
    uid = str(payload.user_id)
    user_favs = favs.setdefault(uid, {"tracks": []})
    url = track["url"]

    existing = [t for t in user_favs["tracks"] if t["url"] == url]
    if existing:
        user_favs["tracks"] = [t for t in user_favs["tracks"] if t["url"] != url]
        save_favorites(favs)
        log.info("❤️ Removed from favorites: %s", url)
    else:
        entry = {
            "url": url,
            "name": track.get("name", url.split("/")[-1].replace(".sap", "")),
            "author": track.get("author", ""),
            "added_at": time.time(),
            "emoji": str(payload.emoji),
        }
        user_favs["tracks"].append(entry)
        save_favorites(favs)
        log.info("❤️ Added to favorites: %s — %s", track.get("name", "?"), url)


@bot.command(aliases=["favs", "playlista"])
async def favorites(ctx: commands.Context):
    """Show your favorited tracks. React to any Now Playing embed to add!"""
    favs = load_favorites()
    user_favs = favs.get(str(ctx.author.id), {}).get("tracks", [])

    if not user_favs:
        return await ctx.send("📭 **No favorites yet.** React to a 🎵 Now Playing embed with any emoji to save tracks here!")

    lines = [f"🎵 **Your Favorites ({len(user_favs)} tracks)**"]
    for i, t in enumerate(user_favs, 1):
        name = t.get("name", "Unknown")
        author_s = f" — {t['author']}" if t.get("author") else ""
        lines.append(f"`{i}.` {name}{author_s}")

    # Discord has 2000 char limit per message
    for chunk in [lines[i:i+15] for i in range(0, len(lines), 15)]:
        await ctx.send("\n".join(chunk))


# ── HVSC C64 SID Collection ─────────────────────────────────────
def parse_songlengths_to_tracks(data: str) -> list[str]:
    """Parse Songlengths.txt → list of full SID URLs."""
    urls = []
    for line in data.splitlines():
        line = line.strip()
        if line.startswith("; /"):
            path = line[2:].strip()  # "; /MUSICIANS/..." → "/MUSICIANS/..."
            full_url = HVSC_BASE.rstrip("/") + path
            urls.append(full_url)
    return urls


def download_hvsc_index() -> list[str] | None:
    """Download Songlengths.txt and return list of SID URLs."""
    if not HVSC_SONGLENGTHS_URL:
        log.error("HVSC: no songlengths_url configured")
        return None
    try:
        r = subprocess.run(
            ["curl", "-sL", "--max-time", "120", HVSC_SONGLENGTHS_URL],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0 or not r.stdout:
            log.error("HVSC index download failed (exit %d)", r.returncode)
            return None
        tracks = parse_songlengths_to_tracks(r.stdout)
        # Cache to file
        try:
            with open(HVSC_CACHE_FILE, "w") as f:
                json.dump({"tracks": tracks, "downloaded": time.time()}, f)
        except Exception as e:
            log.warning("HVSC: cache write failed: %s", e)
        log.info("HVSC: loaded %d SID tracks", len(tracks))
        return tracks
    except Exception as e:
        log.error("HVSC index error: %s", e)
        return None


def load_cached_hvsc() -> list[str] | None:
    """Load HVSC track list from cache if fresh."""
    try:
        if not os.path.exists(HVSC_CACHE_FILE):
            return None
        with open(HVSC_CACHE_FILE) as f:
            data = json.load(f)
        age = time.time() - data.get("downloaded", 0)
        if age > HVSC_CACHE_TTL * 3600:
            log.info("HVSC cache expired (%.1f hours old)", age / 3600)
            return None
        tracks = data.get("tracks", [])
        log.info("HVSC: loaded %d tracks from cache", len(tracks))
        return tracks
    except Exception as e:
        log.warning("HVSC cache load error: %s", e)
        return None


def parse_sid_header(data: bytes) -> dict[str, str]:
    """Parse PSID/RSID header for metadata."""
    meta = {"name": "", "author": "", "copyright": ""}
    if len(data) < 0x76:
        return meta
    magic = data[0:4]
    if magic not in (b"PSID", b"RSID"):
        return meta
    try:
        meta["name"] = data[0x16:0x16+32].rstrip(b"\x00").decode("ascii", errors="replace").strip()
        meta["author"] = data[0x36:0x36+32].rstrip(b"\x00").decode("ascii", errors="replace").strip()
        meta["copyright"] = data[0x56:0x56+32].rstrip(b"\x00").decode("ascii", errors="replace").strip()
    except Exception:
        pass
    return meta


async def download_sid_for_meta(url: str) -> dict[str, str]:
    """Download SID header bytes for metadata parsing."""
    meta = {}
    try:
        r = subprocess.run(
            ["curl", "-sL", "--max-time", "15", "--range", "0-255", url],
            capture_output=True, timeout=20,
        )
        if r.returncode == 0 and len(r.stdout) >= 0x76:
            meta = parse_sid_header(r.stdout)
            meta["url"] = url
            meta["sap_name"] = url.rstrip("/").split("/")[-1]
    except Exception as e:
        log.warning("SID meta fetch error for %s: %s", url, e)
    return meta


def gst_play_sid(filepath: str):
    """Play a SID file via GStreamer into the asma_bot PulseAudio sink."""
    global gst_process
    gst_stop()
    gst_process = subprocess.Popen(
        [
            "gst-launch-1.0", "-q",
            "filesrc", f"location={filepath}",
            "!", "siddec",
            "!", "audioconvert",
            "!", "audioresample",
            "!", "pulsesink", f"device={SINK_NAME}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log.info("GStreamer SID started (PID %d)", gst_process.pid)


def gst_stop():
    """Stop GStreamer SID playback."""
    global gst_process
    if gst_process and gst_process.poll() is None:
        gst_process.terminate()
        try:
            gst_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            gst_process.kill()
            gst_process.wait()
    gst_process = None


def gst_is_playing() -> bool:
    """Check if GStreamer SID is still playing."""
    global gst_process
    return gst_process is not None and gst_process.poll() is None


def stop_all_players():
    """Stop Audacious AND GStreamer — ensures no bleed between collections."""
    audacious_stop()
    gst_stop()


# ── Collection Commands ─────────────────────────────────────────
@bot.command(aliases=["c64", "sid"])
async def hvsc(ctx: commands.Context):
    """Switch to C64 SID collection (HVSC)."""
    global COLLECTION_MODE
    if COLLECTION_MODE == "hvsc":
        # Already in HVSC - try to play
        state = get_state(ctx.guild.id)
        if state.tracks:
            await ctx.send("📀 **Already in C64 SID mode.** Use `!play` to start!")
            return
    await ctx.send("🔄 **Loading C64 SID collection (60,000+ tracks)...**")
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    tracks = await asyncio.get_event_loop().run_in_executor(None, load_cached_hvsc)
    if not tracks:
        tracks = await asyncio.get_event_loop().run_in_executor(None, download_hvsc_index)
    if not tracks:
        return await ctx.send("❌ Failed to load HVSC index. Check config or try again.")
    COLLECTION_MODE = "hvsc"
    state = get_state(ctx.guild.id)
    state.tracks = tracks
    await ctx.send(f"📀 **C64 SID collection ready — {len(tracks)} tracks!**\nUse `!play` to shuffle and play.")
    # Update the search index
    global metadata_index
    metadata_index = {}
    log.info("HVSC: collection switched, %d tracks loaded", len(tracks))
    await cleanup_hvsc_file(ctx, tracks)


async def cleanup_hvsc_file(ctx, tracks):
    """Store the HVSC tracklist for search (no local copies yet)."""
    # Just let user know search won't have metadata until they use it
    pass


@bot.command()
async def asma(ctx: commands.Context):
    """Switch back to Atari SAP collection (ASMA)."""
    global COLLECTION_MODE
    COLLECTION_MODE = "asma"
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    state = get_state(ctx.guild.id)
    cached = load_cached_tracklist()
    if cached:
        state.tracks = cached
        await ctx.send(f"📀 **Switched to ASMA Atari SAP — {len(cached)} tracks!**")
    else:
        state.tracks = []
        await ctx.send("📀 **Switched to ASMA Atari SAP.** Use `!play` to crawl the archive.")
    log.info("ASMA: collection switched")


@bot.command(aliases=["mode", "collection"])
async def status(ctx: commands.Context):
    """Show current collection mode and playlist stats."""
    state = get_state(ctx.guild.id)
    mode_icon = "🟣" if COLLECTION_MODE == "hvsc" else "🟢"
    mode_name = "C64 SID (HVSC)" if COLLECTION_MODE == "hvsc" else "Atari SAP (ASMA)"
    total = len(state.tracks) if state.tracks else 0
    qlen = len(state.queue)
    pos = state.index + 1 if state.index >= 0 else 0
    playing = "🎵 Yes" if (is_playing() or gst_is_playing()) else "⏸️ No"
    await ctx.send(
        f"{mode_icon} **Collection: {mode_name}**\n"
        f"• Tracks in archive: **{total}**\n"
        f"• Queue remaining: **{qlen - pos}/{qlen}**\n"
        f"• Playing: {playing}\n"
        f"• Loop: {'🔁 On' if state.loop else '➡️ Off'}"
    )


@bot.command(aliases=["switch", "toggle", "przelacz"])
async def flip(ctx: commands.Context):
    """Toggle between Atari SAP (ASMA) and C64 SID (HVSC) collections."""
    global COLLECTION_MODE
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    if COLLECTION_MODE == "hvsc":
        # Switch to ASMA
        COLLECTION_MODE = "asma"
        state = get_state(ctx.guild.id)
        cached = load_cached_tracklist()
        if cached:
            state.tracks = cached
            await ctx.send("🟢 **Switched to Atari SAP (ASMA)!** Use `!play` to start.")
        else:
            state.tracks = []
            await ctx.send("🟢 **Switched to Atari SAP (ASMA).** Use `!play` to crawl the archive.")
        log.info("ASMA: collection switched via flip")
    else:
        # Switch to HVSC
        COLLECTION_MODE = "hvsc"
        tracks = await asyncio.get_event_loop().run_in_executor(None, load_cached_hvsc)
        if not tracks:
            await ctx.send("🔄 Loading C64 SID collection (60,000+ tracks)...")
            tracks = await asyncio.get_event_loop().run_in_executor(None, download_hvsc_index)
        if tracks:
            state = get_state(ctx.guild.id)
            state.tracks = tracks
            await ctx.send(f"🟣 **Switched to C64 SID (HVSC) — {len(tracks)} tracks!** Use `!play` to start.")
            global metadata_index
            metadata_index = {}
        else:
            await ctx.send("❌ Could not load HVSC. Try `!hvsc` manually.")
            COLLECTION_MODE = "asma"  # revert
        log.info("HVSC: collection switched via flip")


# ── Playback Monitor ────────────────────────────────────────────
async def monitor_playback(ctx: commands.Context, vc: discord.VoiceClient, guild_id: int):
    """Monitor playback, auto-advance tracks, and disconnect on empty channel."""
    empty_since = None
    not_playing_since = None
    GRACE_SECONDS = 3
    while vc.is_connected():
        await asyncio.sleep(1)

        # Check for empty channel
        if vc.channel and len(vc.channel.members) <= 1:
            if empty_since is None:
                empty_since = time.time()
            elif AUTO_EMPTY_TIMEOUT > 0 and (time.time() - empty_since) >= AUTO_EMPTY_TIMEOUT:
                log.info("Channel empty for %ds, disconnecting", AUTO_EMPTY_TIMEOUT)
                state = get_state(guild_id)
                if guild_id in active_streams:
                    active_streams[guild_id].cleanup()
                    del active_streams[guild_id]
                await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
                await vc.disconnect()
                await ctx.send("🌙 No one listening. Stopping ASMA Radio.")
                break
        else:
            empty_since = None

        playing = await asyncio.get_event_loop().run_in_executor(None, lambda: is_playing() or gst_is_playing())
        if playing:
            not_playing_since = None
        else:
            if not_playing_since is None:
                not_playing_since = time.time()
            elif (time.time() - not_playing_since) >= GRACE_SECONDS:
                state = get_state(guild_id)
                if state.loop or state.index < len(state.queue) - 1:
                    not_playing_since = None
                    await skip_to_next(ctx)
                    continue
                else:
                    if guild_id in active_streams:
                        active_streams[guild_id].cleanup()
                        del active_streams[guild_id]
                    if vc.is_connected():
                        await vc.disconnect()
                    await ctx.send("Playlist ended. Use !play to restart.")
                    break
    
    if guild_id in active_streams:
        active_streams[guild_id].cleanup()
        del active_streams[guild_id]


# ── Background Metadata Fetcher ──────────────────────────────────
async def fetch_metadata_background():
    """Fetch metadata for tracks in the background during idle time."""
    await bot.wait_until_ready()
    await asyncio.sleep(30)  # Wait for startup to complete
    
    cached = load_cached_tracklist()
    if not cached:
        return
    
    # Find tracks without metadata
    missing = [url for url in cached if url not in metadata_index]
    if not missing:
        log.info("Metadata index complete: %d tracks", len(metadata_index))
        return
    
    log.info("Fetching metadata for %d tracks...", len(missing))
    connector = aiohttp.TCPConnector(limit=5, limit_per_host=3)
    async with aiohttp.ClientSession(connector=connector) as session:
        await fetch_metadata_batch(session, missing)
    
    log.info("Metadata index updated: %d tracks indexed", len(metadata_index))


# ── Health Watchdog ─────────────────────────────────────────────
async def health_watchdog():
    """Periodically check Audacious and PulseAudio health."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(30)
        try:
            # Check Audacious
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: subprocess.run(["pgrep", "-x", "audacious"], capture_output=True)
            )
            if result.returncode != 0:
                log.warning("Audacious not running, restarting...")
                await asyncio.get_event_loop().run_in_executor(None, ensure_audacious)

            # Check PulseAudio sink
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: subprocess.run(
                    ["pactl", "list", "sinks", "short"], capture_output=True, text=True
                )
            )
            if SINK_NAME not in result.stdout:
                log.warning("Virtual sink missing, recreating...")
                await asyncio.get_event_loop().run_in_executor(None, setup_virtual_sink)
        except Exception as e:
            log.error("Watchdog error: %s", e)

# ── Main ────────────────────────────────────────────────────────
if not BOT_TOKEN:
    raise SystemExit("Set DISCORD_BOT_TOKEN environment variable.")

def cleanup_temp():
    """Remove temp directory and all downloaded SAP files."""
    try:
        if os.path.isdir(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            log.info("Cleaned up temp dir: %s", TEMP_DIR)
    except Exception as e:
        log.warning("Temp cleanup failed: %s", e)

async def graceful_shutdown():
    """Disconnect all voice clients and stop Audacious."""
    log.info("Shutting down gracefully...")
    for guild_id, source in list(active_streams.items()):
        source.cleanup()
    del active_streams
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    for vc in list(bot.voice_clients):
        await vc.disconnect()
    cleanup_temp()

def handle_signal(signum, frame):
    log.info("Received signal %d, shutting down...", signum)
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(graceful_shutdown())
    else:
        loop.run_until_complete(graceful_shutdown())

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    bot.run(BOT_TOKEN)
