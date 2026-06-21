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
from hashlib import sha1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("robbo-obibok")

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

# ── Local AY Archive (ZX Spectrum) ──────────────────────────────
AY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archiwum", "ay")
AY_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ay_cache.json")

# ── Local Tiny Music (Demoscene Modules) ────────────────────────
TINY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archiwum", "tiny")
TINY_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiny_cache.json")

# ── Favorites System ────────────────────────────────────────────
FAVORITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favorites.json")

# ── Blacklist System ────────────────────────────────────────────
BLACKLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blacklist.json")

# ── Last Collection Mode ────────────────────────────────────────
LAST_COLLECTION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_collection.txt")

def load_last_collection() -> str | None:
    try:
        with open(LAST_COLLECTION_FILE) as f:
            mode = f.read().strip()
            if mode in ("asma", "hvsc", "modarchive", "ay", "tiny", "spc"):
                return mode
    except (FileNotFoundError, OSError):
        pass
    return None

def save_last_collection(mode: str):
    try:
        with open(LAST_COLLECTION_FILE, "w") as f:
            f.write(mode)
    except OSError:
        pass

# ── SNES SPC Collection (SNESmusic.org) ──────────────────────────
SNES_BASE = "https://snesmusic.org/v2/"
SNES_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snes_cache.json")
SNES_SPC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archiwum", "spc")
HVSC_BASE = CONFIG.get("hvsc", {}).get("base_url", "https://www.hvsc.c64.org/download/C64Music/")
HVSC_SONGLENGTHS_URL = CONFIG.get("hvsc", {}).get("songlengths_url", "")
HVSC_CACHE_TTL = CONFIG.get("hvsc", {}).get("cache_ttl", 168)
HVSC_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hvsc_cache.json")
DEFAULT_COLLECTION_MODE = "hvsc" if CONFIG.get("hvsc", {}).get("enabled", False) else "asma"

# ── ModArchive Collection (FastTracker / MOD / XM / S3M / IT) ──────
MODARCHIVE_BASE = CONFIG.get("modarchive", {}).get("base_url", "https://modarchive.org/index.php")
MODARCHIVE_DOWNLOAD = CONFIG.get("modarchive", {}).get("download_url", "https://api.modarchive.org/downloads.php")
MODARCHIVE_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    CONFIG.get("modarchive", {}).get("cache_file", "modarchive_cache.json")
)
modarchive_name_map: dict[str, str] = {}  # URL -> real module name

CROSSFADE_SECS = CONFIG["playback"].get("crossfade", 0)
AUTO_START_CHANNEL = CONFIG["auto"].get("start_channel", "")
AUTO_EMPTY_TIMEOUT = CONFIG["auto"].get("empty_timeout", 60)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

active_streams: dict[int, "MonitorAudioSource"] = {}

def _after_stream_end(guild_id: int | None, error: Exception | None) -> None:
    """Cleanup callback for vc.play() — logs and removes from active_streams."""
    log.info("Stream ended for guild %s: %s", guild_id, error)
    if guild_id is not None:
        active_streams.pop(guild_id, None)

# ── Playlist state ──────────────────────────────────────────────
class PlaylistState:
    def __init__(self):
        self.tracks: list[str] = []      # all known SAP URLs
        self.queue: list[str] = []       # shuffled play queue
        self.index: int = -1             # current position in queue
        self.loop: bool = True
        self.collection_mode: str = load_last_collection() or DEFAULT_COLLECTION_MODE
        self.loaded_collection: str = "" # which collection is actually loaded into self.tracks
        self.guild_id: int | None = None
        self.ctx = None
        self.vc = None
        self.current_sap_path: str | None = None
        self.crawling: bool = False
        self.pre_downloaded: str | None = None  # next track pre-downloaded
        self.search_results: list[str] = []     # last search results
        self.monitor_task: asyncio.Task | None = None


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
        "collection_mode": state.collection_mode,
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


def build_temp_path(url: str) -> str:
    """Create a collision-resistant temp path for a downloaded track."""
    filename = url.split("/")[-1] or "track.bin"
    digest = sha1(url.encode("utf-8")).hexdigest()[:12]
    return os.path.join(TEMP_DIR, f"{digest}_{filename}")

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
            check=False,
        )

def ensure_audacious():
    result = subprocess.run(["pgrep", "-x", "audacious"], capture_output=True)
    if result.returncode != 0:
        subprocess.Popen(
            ["audacious", "--headless"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for D-Bus to be ready (audtool can take 5-10s to connect)
        for _ in range(20):
            r = subprocess.run(["audtool", "version"], capture_output=True, timeout=2)
            if r.returncode == 0:
                return
            time.sleep(1)
        log.warning("Audacious D-Bus not ready after 20s, continuing anyway")


def setup_audacious_sid_config():
    """Ensure Audacious SID plugin config and Songlengths.md5 are set for auto-advance."""
    # Set SID plugin configuration
    subprocess.run(["audtool", "config-set", "SID Player:playMaxTimeEnable", "TRUE"], capture_output=True)
    subprocess.run(["audtool", "config-set", "SID Player:playMaxTime", "180"], capture_output=True)
    subprocess.run(["audtool", "config-set", "SID Player:playMaxTimeUnknown", "TRUE"], capture_output=True)
    log.info("Audacious SID plugin config set")


# ── Volume normalization per collection ──────────────────────────
COLLECTION_VOLUMES = {
    "hvsc": 120,       # SIDy są cichsze, lekki boost
    "asma": 100,       # SAPy normalnie
    "modarchive": 100, # MODy normalnie
    "ay": 100,         # AY normalnie
    "tiny": 100,       # Tiny normalnie
    "spc": 100,        # SPC normalnie
}

def set_volume_for_collection(mode: str):
    """Set playback volume based on collection for consistent loudness."""
    vol = COLLECTION_VOLUMES.get(mode, 100)
    subprocess.run(["pactl", "set-sink-volume", "asma_bot", f"{vol}%"], capture_output=True)
    log.info("Volume set to %d%% for collection %s", vol, mode)


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
    filepath = build_temp_path(url)
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
    ensure_audacious()
    subprocess.run(["audtool", "playlist-clear"], capture_output=True)
    subprocess.run(["audtool", "playlist-addurl", filepath], capture_output=True)
    # Retry play until it actually starts (first play after idle Audacious can fail)
    for attempt in range(3):
        subprocess.run(["audtool", "playback-play"], capture_output=True)
        time.sleep(0.5)
        r = subprocess.run(["audtool", "playback-playing"], capture_output=True)
        if r.returncode == 0:
            break
        log.warning("audacious_play: attempt %d failed, retrying...", attempt + 1)
    move_playback_to_sink()

def audacious_stop():
    """Stop Audacious playback and clear its playlist."""
    subprocess.run(["audtool", "playback-stop"], capture_output=True)
    subprocess.run(["audtool", "playlist-clear"], capture_output=True)


def audacious_kill():
    """Kill the Audacious process entirely — prevents audio bleed between collections."""
    subprocess.run(["audtool", "playback-stop"], capture_output=True)
    subprocess.run(["pkill", "-x", "audacious"], capture_output=True)


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
    # For ModArchive URLs, use the module name from cache
    if url.startswith("https://api.modarchive.org/") or "modarchive" in url:
        name = modarchive_name_map.get(url, "")
        return name.lower().replace("_", " ")
    path = url.replace(ASMA_BASE, "").replace(HVSC_BASE, "")
    name_part = path.split("/")[-1]
    # Strip known extensions for search
    for ext in [".sap", ".sid", ".mod", ".xm", ".s3m", ".it"]:
        name_part = name_part.replace(ext, "")
    return name_part.replace("_", " ").lower()

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
        batch_urls = []
        tasks = []
        for url in batch:
            if url in metadata_index:
                continue
            batch_urls.append(url)
            tasks.append(fetch_single_metadata(session, url))
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for url, result in zip(batch_urls, batch_results):
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
        if url.startswith("https://api.modarchive.org/") or "modarchive" in url:
            filename = modarchive_name_map.get(url, "").replace("_", " ")
        else:
            filename = url.split("/")[-1]
            for ext in [".sap", ".sid", ".mod", ".xm", ".s3m", ".it"]:
                filename = filename.replace(ext, "")
            filename = filename.replace("_", " ")
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
    """Download and play a SID track via Audacious."""
    # Download full SID to temp (they're small, ~5-15KB)
    sid_path = build_temp_path(url)
    try:
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

    # Play via Audacious
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    await asyncio.get_event_loop().run_in_executor(None, audacious_play, sid_path)

    state.current_sap_path = sid_path

    # Setup MonitorAudioSource (always stop old and create fresh)
    if state.vc and state.vc.is_connected():
        state.vc.stop()
        old_source = active_streams.pop(state.guild_id, None)
        if old_source:
            old_source.cleanup()
        source = MonitorAudioSource(SINK_NAME)
        state.vc.play(
            source,
            after=lambda e: _after_stream_end(state.guild_id, e),
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


async def play_current_modarchive_track(ctx, state, url):
    """Download and play a module (MOD/XM/S3M/IT) from ModArchive via Audacious."""
    try:
        filepath = await download_modarchive_module(url)
    except Exception as e:
        log.error("ModArchive download failed: %s", e)
        await ctx.send(f"❌ Download failed: {e}")
        return False

    # Extract filename for display
    fname = os.path.basename(filepath) if filepath else url.split("moduleid=")[-1]

    # Play via Audacious
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    await asyncio.get_event_loop().run_in_executor(None, audacious_play, filepath)

    state.current_sap_path = filepath

    # Setup MonitorAudioSource (always stop old and create fresh)
    if state.vc and state.vc.is_connected():
        state.vc.stop()
        old_source = active_streams.pop(state.guild_id, None)
        if old_source:
            old_source.cleanup()
        source = MonitorAudioSource(SINK_NAME)
        state.vc.play(
            source,
            after=lambda e: _after_stream_end(state.guild_id, e),
        )
        active_streams[state.guild_id] = source

    total = len(state.queue)
    pos = state.index + 1

    # Try to extract a human-friendly name from the filename
    display_name = fname
    if "." in fname:
        display_name = fname.rsplit(".", 1)[0]
    # Replace underscores with spaces for readability
    display_name = display_name.replace("_", " ").strip()

    embed = discord.Embed(
        title=display_name[:256],
        color=discord.Color.from_str("#E67E22"),  # orange / tracker vibe
    )
    fmt = fname.rsplit(".", 1)[-1].upper() if "." in fname else "MODULE"
    embed.add_field(name="Format", value=fmt, inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    embed.set_footer(text="ModArchive Radio — FastTracker / MOD / XM / S3M / IT")
    np_msg = await ctx.send(embed=embed)

    # Track for reaction-based favorites
    message_track_map[np_msg.id] = {
        "url": url,
        "name": display_name,
        "author": "",
        "timestamp": time.time(),
    }
    log.info("ModArchive now playing: %s (%s)", display_name, fmt)
    return True


# ── Collection Helpers ──────────────────────────────────────────────

COLLECTION_INFO = {
    "asma": {
        "icon": "🟢",
        "name": "Atari SAP (ASMA)",
        "station": "ASMA Radio",
        "footer": "ASMA Radio",
        "color": discord.Color.green(),
        "load_tracks": lambda: refresh_tracklist(),
        "download": lambda url: download_sap(url),
    },
    "hvsc": {
        "icon": "🟣",
        "name": "C64 SID (HVSC)",
        "station": "C64 SID Radio",
        "footer": "C64 SID Radio",
        "color": discord.Color.purple(),
        "load_tracks": lambda: load_cached_hvsc(),
        "fallback_load": lambda: download_hvsc_index(),
        "download": lambda url: None,  # SID has its own download in play_current_sid_track
    },
    "modarchive": {
        "icon": "🟠",
        "name": "Tracker Modules (ModArchive)",
        "station": "ModArchive Radio",
        "footer": "ModArchive Radio — FastTracker / MOD / XM / S3M / IT",
        "color": discord.Color.from_str("#E67E22"),
        "load_tracks": lambda: load_modarchive_cache(),
        "download": lambda url: None,  # uses download_modarchive_module in play func
    },
    "ay": {
        "icon": "🔵",
        "name": "ZX Spectrum AY (Local Archive)",
        "station": "ZX Spectrum Radio",
        "footer": "ZX Spectrum Radio — AY chiptunes",
        "color": discord.Color.blue(),
        "load_tracks": lambda: load_ay_cache(),
    },
    "tiny": {
        "icon": "🎵",
        "name": "Tiny Music (Demoscene Modules)",
        "station": "Tiny Music Radio",
        "footer": "Tiny Music — curated demoscene modules",
        "color": discord.Color.purple(),
        "load_tracks": lambda: load_tiny_cache(),
    },
    "spc": {
        "icon": "🔴",
        "name": "SNES SPC (SNESmusic.org)",
        "station": "SNES Radio",
        "footer": "SNES Radio — Super Nintendo SPC chiptunes",
        "color": discord.Color.from_str("#E74C3C"),
        "load_tracks": lambda: load_snes_cache(),
    },
}


def get_collection_info(mode: str) -> dict:
    return COLLECTION_INFO.get(mode, COLLECTION_INFO["asma"])


async def load_tracks_for_mode(mode: str) -> list | None:
    """Load track list for the given collection mode."""
    info = get_collection_info(mode)
    result = info["load_tracks"]()
    if asyncio.iscoroutine(result):
        tracks = await result
    else:
        tracks = result
    # Fallback for HVSC
    if not tracks and mode == "hvsc" and "fallback_load" in info:
        log.info("HVSC: cache empty, downloading index...")
        result = info["fallback_load"]()
        if asyncio.iscoroutine(result):
            tracks = await result
        else:
            tracks = result
    return tracks


async def ensure_tracks(state) -> bool:
    """Ensure tracks are loaded for the current collection mode. Returns True if ready."""
    if state.tracks and state.loaded_collection == state.collection_mode:
        return True
    state.tracks = await load_tracks_for_mode(state.collection_mode)
    state.loaded_collection = state.collection_mode if state.tracks else state.loaded_collection
    return bool(state.tracks)


async def play_current_ay_track(ctx, state, filepath):
    """Play a local AY file via ffplay (libgme)."""
    full_path = os.path.join(AY_DIR, filepath)

    if not os.path.exists(full_path):
        await ctx.send(f"❌ File not found: `{filepath}`")
        return False

    # Stop any existing playback and play via Audacious (console.so handles AY through GME)
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    await asyncio.get_event_loop().run_in_executor(None, audacious_play, full_path)

    # Setup MonitorAudioSource (same sink as Audacious)
    if state.vc and state.vc.is_connected():
        state.vc.stop()
        old_source = active_streams.pop(state.guild_id, None)
        if old_source:
            old_source.cleanup()
        source = MonitorAudioSource(SINK_NAME)
        state.vc.play(
            source,
            after=lambda e: _after_stream_end(state.guild_id, e),
        )
        active_streams[state.guild_id] = source

    total = len(state.queue)
    pos = state.index + 1

    # Get metadata from Audacious (console.so/GME provides it)
    track = await asyncio.get_event_loop().run_in_executor(None, audacious_song)
    name = track or filepath.split("/")[-1].replace(".ay", "")
    author = ""

    embed = discord.Embed(
        title=name[:256],
        color=discord.Color.blue(),
    )
    if author:
        embed.add_field(name="Composer", value=author, inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    embed.set_footer(text="ZX Spectrum AY — via libgme")

    np_msg = await ctx.send(embed=embed)
    message_track_map[np_msg.id] = {
        "url": filepath,
        "name": name,
        "author": author,
        "timestamp": time.time(),
    }
    log.info("AY now playing: %s — %s", name, author)
    return True


async def play_current_tiny_track(ctx, state, filepath):
    """Play a local Tiny Music module via Audacious."""
    full_path = os.path.join(TINY_DIR, filepath)

    if not os.path.exists(full_path):
        await ctx.send(f"❌ File not found: `{filepath}`")
        return False

    # Stop existing playback and play via Audacious
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    await asyncio.get_event_loop().run_in_executor(None, audacious_play, full_path)

    state.current_sap_path = full_path

    # Setup MonitorAudioSource
    if state.vc and state.vc.is_connected():
        state.vc.stop()
        old_source = active_streams.pop(state.guild_id, None)
        if old_source:
            old_source.cleanup()
        source = MonitorAudioSource(SINK_NAME)
        state.vc.play(
            source,
            after=lambda e: _after_stream_end(state.guild_id, e),
        )
        active_streams[state.guild_id] = source

    total = len(state.queue)
    pos = state.index + 1

    # Get metadata from Audacious
    track = await asyncio.get_event_loop().run_in_executor(None, audacious_song)
    name = track or filepath.split("/")[-1].replace(".mod", "").replace(".xm", "").replace(".it", "").replace(".s3m", "").replace(".med", "").replace(".dmf", "").replace(".mo3", "").replace(".mptm", "")
    author = ""

    embed = discord.Embed(
        title=name[:256],
        color=discord.Color.purple(),
    )
    if author:
        embed.add_field(name="Composer", value=author, inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    embed.set_footer(text="Tiny Music — curated demoscene modules")

    np_msg = await ctx.send(embed=embed)
    message_track_map[np_msg.id] = {
        "url": filepath,
        "name": name,
        "author": author,
        "timestamp": time.time(),
    }
    log.info("Tiny now playing: %s — %s", name, author)
    return True


async def play_current_track(ctx):
    """Download and play the current track from the queue."""
    state = get_state(ctx.guild.id)
    if state.index < 0 or state.index >= len(state.queue):
        await ctx.send("Queue empty. Use !play to rebuild.")
        return False
    
    url = state.queue[state.index]
    log.info("play_current_track: url=%s, index=%d", str(url)[:80], state.index)

    # ── SNES SPC (game entry dict) ──
    if state.collection_mode == "spc" or url in snes_metadata:
        game_entry = snes_metadata.get(url)
        if not game_entry:
            await ctx.send(f"❌ Unknown SNES track")
            return False
        return await play_current_spc_track(ctx, state, game_entry)

    await ctx.send(f"Loading... `{url.split('/')[-1]}`")
    
    try:
        # Detect archive type from current URL (supports mixed playlists like !favplay)
        is_hvsc = "hvsc.c64.org" in url or url.endswith(".sid")

        # ── Local Tiny Music (Demoscene Modules) ──
        is_tiny = "://" not in url and url.endswith((".mod", ".xm", ".it", ".s3m", ".med", ".dmf", ".mo3"))
        if is_tiny:
            if state.collection_mode != "tiny":
                state.collection_mode = "tiny"
                await ensure_tracks(state)
            return await play_current_tiny_track(ctx, state, url)

        is_modarchive = "modarchive" in url or url.endswith((".mod", ".xm", ".s3m", ".it"))
        
        if is_hvsc:
            if state.collection_mode != "hvsc":
                state.collection_mode = "hvsc"
                await ensure_tracks(state)
            return await play_current_sid_track(ctx, state, url)
        
        if is_modarchive:
            if state.collection_mode != "modarchive":
                state.collection_mode = "modarchive"
                await ensure_tracks(state)
            return await play_current_modarchive_track(ctx, state, url)

        # ── Local AY Archive (ZX Spectrum) ──
        is_ay = url.endswith(".ay")
        if is_ay:
            if state.collection_mode != "ay":
                state.collection_mode = "ay"
                await ensure_tracks(state)
            return await play_current_ay_track(ctx, state, url)

        # ── ASMA SAP Playback (default) ──
        if state.collection_mode != "asma":
            state.collection_mode = "asma"
            await ensure_tracks(state)
        # Use pre-downloaded track if available, otherwise download now
        if state.pre_downloaded and os.path.exists(state.pre_downloaded):
            filepath = state.pre_downloaded
            state.pre_downloaded = None
        else:
            filepath = await download_sap(url)
        await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
        await asyncio.get_event_loop().run_in_executor(None, audacious_play, filepath)
        
        state.current_sap_path = filepath
        
        # Setup MonitorAudioSource (always stop old and create fresh)
        if state.vc and state.vc.is_connected():
            state.vc.stop()
            old_source = active_streams.pop(state.guild_id, None)
            if old_source:
                old_source.cleanup()
            source = MonitorAudioSource(SINK_NAME)
            state.vc.play(
                source,
                after=lambda e: _after_stream_end(state.guild_id, e)
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
    # Kill any orphaned Audacious from crashed bot sessions
    try:
        await asyncio.get_event_loop().run_in_executor(None, cleanup_orphan_players)
    except Exception as e:
        log.error("cleanup_orphan_players failed: %s", e)
    try:
        await asyncio.get_event_loop().run_in_executor(None, setup_virtual_sink)
    except Exception as e:
        log.error("setup_virtual_sink failed: %s", e)
    try:
        await asyncio.get_event_loop().run_in_executor(None, ensure_audacious)
    except Exception as e:
        log.error("ensure_audacious failed: %s", e)
    # Ensure Audacious SID plugin config is set for song-length-based auto-advance
    try:
        await asyncio.get_event_loop().run_in_executor(None, setup_audacious_sid_config)
    except Exception as e:
        log.error("setup_audacious_sid_config failed: %s", e)
    
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
            await ensure_tracks(state)

        if not state.tracks:
            log.warning("Auto-start: no tracks available")
            await vc.disconnect()
            return

        saved = load_queue(member.guild.id)
        if saved and saved.get("queue") and saved["queue"][0] in state.tracks and saved.get("collection_mode") == state.collection_mode:
            state.queue = saved["queue"]
            state.index = saved.get("index", 0)
            state.loop = saved.get("loop", PLAYBACK_LOOP)
        else:
            state.queue = list(state.tracks)
            if PLAYBACK_SHUFFLE:
                random.shuffle(state.queue)
            state.index = 0

        # Send messages to the voice channel (Discord supports text in voice channels)
        info = get_collection_info(state.collection_mode)
        ctx = await bot.get_context(await after.channel.send(f"📻 **Auto-starting {info['station']}...**"))
        state.ctx = ctx

        if await play_current_track(ctx):
            save_queue(state)
            if state.monitor_task and not state.monitor_task.done():
                state.monitor_task.cancel()
            state.monitor_task = bot.loop.create_task(monitor_playback(ctx, vc, member.guild.id))
    except Exception as e:
        log.error("Auto-start failed: %s", e)

# ── Commands ────────────────────────────────────────────────────
@bot.command()
async def radi(ctx: commands.Context):
    """NI MA RADI"""
    await ctx.send("https://www.youtube.com/watch?v=SbuBkGrpSl0")

@bot.command(aliases=["radio", "start", "pl"])
async def play(ctx: commands.Context, *, query: str = ""):
    """Start shuffled radio. Usage: !play, !play <number>, or !play <search query>"""
    if not ctx.author.voice:
        return await ctx.send("Join a voice channel first!")

    state = get_state(ctx.guild.id)

    # Play from search results by number
    if query.isdigit():
        idx = int(query) - 1
        if not state.search_results or idx < 0 or idx >= len(state.search_results):
            return await ctx.send("Invalid number. Use !search first.")
        if not state.tracks:
            await ensure_tracks(state)
        url = state.search_results[idx]
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        vc = await ctx.author.voice.channel.connect()
        state.vc = vc
        state.guild_id = ctx.guild.id
        state.ctx = ctx
        state.loop = PLAYBACK_LOOP
        state.queue = filter_blacklisted(list(state.tracks), ctx.author.id)
        if PLAYBACK_SHUFFLE:
            random.shuffle(state.queue)
        try:
            state.index = state.queue.index(url)
        except ValueError:
            state.queue.insert(0, url)
            state.index = 0
        if await play_current_track(ctx):
            save_queue(state)
            if state.monitor_task and not state.monitor_task.done():
                state.monitor_task.cancel()
            state.monitor_task = bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))
        return

    # Search and play first result
    if query:
        if not state.tracks:
            await ensure_tracks(state)
        query_lower = query.lower()
        matches = [u for u in state.tracks if query_lower in u.split("/")[-1].rsplit(".", 1)[0].replace("_", " ").lower()]
        if matches:
            url = matches[0]
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
            vc = await ctx.author.voice.channel.connect()
            state.vc = vc
            state.guild_id = ctx.guild.id
            state.ctx = ctx
            state.loop = PLAYBACK_LOOP
            state.queue = filter_blacklisted(list(state.tracks), ctx.author.id)
            if PLAYBACK_SHUFFLE:
                random.shuffle(state.queue)
            try:
                state.index = state.queue.index(url)
            except ValueError:
                state.queue.insert(0, url)
                state.index = 0
            if await play_current_track(ctx):
                save_queue(state)
                if state.monitor_task and not state.monitor_task.done():
                    state.monitor_task.cancel()
                state.monitor_task = bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))
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
    
    info = get_collection_info(state.collection_mode)
    await ctx.send(f"🎛️ **{info['station']} starting...**")
    
    # Ensure we have tracks
    if not state.tracks:
        await ensure_tracks(state)

    track_count = len(state.tracks) if state.tracks else 0
    await ctx.send(f"📀 Ready with **{track_count}** tracks!")
    
    # Shuffle and start
    saved = load_queue(ctx.guild.id)
    if saved and saved.get("queue") and saved["queue"][0] in state.tracks and saved.get("collection_mode") == state.collection_mode:
        state.queue = saved["queue"]
        state.index = saved.get("index", 0)
        state.loop = saved.get("loop", PLAYBACK_LOOP)
        await ctx.send("📋 Restored previous queue.")
    else:
        state.queue = filter_blacklisted(list(state.tracks), ctx.author.id)
        if PLAYBACK_SHUFFLE:
            random.shuffle(state.queue)
        state.index = 0
    
    if await play_current_track(ctx):
        save_queue(state)
        if state.monitor_task and not state.monitor_task.done():
            state.monitor_task.cancel()
        state.monitor_task = bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))


@bot.command(aliases=["st"])
async def stop(ctx: commands.Context):
    """Stop playback and disconnect."""
    state = get_state(ctx.guild.id)
    if state.guild_id and state.guild_id in active_streams:
        stream = active_streams.pop(state.guild_id, None)
        if stream:
            stream.cleanup()
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    state.queue = []
    state.index = -1
    save_queue(state)
    await ctx.send("⏹️ Stopped.")


@bot.command(aliases=["next", "nt"])
async def skip(ctx: commands.Context):
    """Skip to next track."""
    state = get_state(ctx.guild.id)
    if not state.queue:
        return await ctx.send("Nothing playing.")
    await skip_to_next(ctx)


@bot.command()
async def np(ctx: commands.Context):
    """Show current track info."""
    state = get_state(ctx.guild.id)
    if not is_playing():
        return await ctx.send("Nothing playing right now.")
    track = await asyncio.get_event_loop().run_in_executor(None, audacious_song)
    total = len(state.queue)
    pos = state.index + 1
    meta = {}
    if state.current_sap_path:
        if state.current_sap_path.lower().endswith(".sid"):
            try:
                with open(state.current_sap_path, "rb") as f:
                    meta = parse_sid_header(f.read(0x76))
            except Exception:
                meta = {}
        else:
            meta = parse_sap_header(state.current_sap_path)
    name = meta.get("name", meta.get("NAME", track))
    author = meta.get("author", "") or meta.get("AUTHOR", "")
    copyright_info = meta.get("copyright", "")
    info = get_collection_info(state.collection_mode)
    embed = discord.Embed(
        title=f"Now Playing: {name}",
        color=info["color"],
    )
    if author:
        embed.add_field(name="Composer", value=author, inline=True)
    if copyright_info:
        embed.add_field(name="Copyright", value=copyright_info, inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    # Add elapsed time info
    elapsed_r = await asyncio.get_event_loop().run_in_executor(
        None, lambda: subprocess.run(["audtool", "current-song-output-length-seconds"], capture_output=True, text=True)
    )
    total_r = await asyncio.get_event_loop().run_in_executor(
        None, lambda: subprocess.run(["audtool", "current-song-length-seconds"], capture_output=True, text=True)
    )
    try:
        elapsed = int(elapsed_r.stdout.strip())
        total_s = int(total_r.stdout.strip())
        if total_s > 0:
            elapsed_m, elapsed_s = divmod(elapsed, 60)
            total_m, total_ss = divmod(total_s, 60)
            embed.add_field(name="Duration", value=f"{elapsed_m}:{elapsed_s:02d} / {total_m}:{total_ss:02d}", inline=True)
    except (ValueError, OSError):
        pass
    embed.set_footer(text=info["footer"])
    np_msg = await ctx.send(embed=embed)
    # Track for reaction-based favorites
    message_track_map[np_msg.id] = {
        "url": state.queue[state.index] if state.queue and 0 <= state.index < len(state.queue) else "unknown",
        "name": name,
        "author": author,
        "timestamp": time.time(),
    }
    return


@bot.command()
async def volume(ctx: commands.Context, *, level: str = ""):
    """Set or show playback volume (0-200%). Usage: !volume <level>"""
    if not level:
        r = subprocess.run(["pactl", "get-sink-volume", "asma_bot"], capture_output=True, text=True)
        m = re.search(r"(\d+)%", r.stdout)
        if m:
            current = m.group(1)
            embed = discord.Embed(title=f"🔊 Current volume: **{current}%**", color=discord.Color.green())
            await ctx.send(embed=embed)
        else:
            await ctx.send("Could not read volume.")
        return

    try:
        vol = int(level)
        if vol < 0 or vol > 200:
            await ctx.send("Volume must be between 0 and 200.")
            return
        subprocess.run(["pactl", "set-sink-volume", "asma_bot", f"{vol}%"], capture_output=True)
        embed = discord.Embed(title=f"🔊 Volume set to **{vol}%**", color=discord.Color.green())
        await ctx.send(embed=embed)
    except ValueError:
        await ctx.send("Usage: `!volume <0-200>` or `!volume` to show current.")


@bot.command(aliases=["q"])
async def queue(ctx: commands.Context):
    """Show the next 10 tracks in queue. Usage: !queue"""
    state = get_state(ctx.guild.id)
    if not state.queue:
        return await ctx.send("Queue is empty. Use !play to start.")

    total = len(state.queue)
    pos = state.index

    if pos < 0 or pos >= total:
        return await ctx.send("Nothing currently playing.")

    upcoming = state.queue[pos+1:pos+11]
    if not upcoming:
        await ctx.send("No upcoming tracks — this is the last one.")
        return

    info = get_collection_info(state.collection_mode)
    lines = [f"📜 **Upcoming tracks ({len(upcoming)}/{total-pos-1} remaining)**"]

    for i, url in enumerate(upcoming, 1):
        name = url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
        if len(name) > 60:
            name = name[:57] + "..."
        lines.append(f"`{i}.` {name}")

    embed = discord.Embed(
        title="🎵 Queue",
        description="\n".join(lines),
        color=discord.Color.blue()
    )
    embed.set_footer(text=info["footer"])
    await ctx.send(embed=embed)


@bot.command()
async def sleep(ctx: commands.Context, *, minutes: str = ""):
    """Stop playback after N minutes. Usage: !sleep 30"""
    if not minutes:
        await ctx.send("Usage: `!sleep <minutes>` — stops playback after N minutes.")
        return

    try:
        mins = float(minutes.replace(",", "."))
        if mins <= 0:
            await ctx.send("Time must be positive.")
            return
        if mins > 360:
            await ctx.send("Max 360 minutes (6 hours).")
            return

        secs = int(mins * 60)
        embed = discord.Embed(
            title="⏰ Sleep timer set",
            description=f"Playback will stop in **{mins:.0f} minute{s if mins != 1 else ''}**.",
            color=discord.Color.dark_blue()
        )
        await ctx.send(embed=embed)

        await asyncio.sleep(secs)

        # Check if still playing
        state = get_state(ctx.guild.id)
        if ctx.voice_client and ctx.voice_client.is_connected():
            # Stop and disconnect
            if state.guild_id and state.guild_id in active_streams:
                stream = active_streams.pop(state.guild_id, None)
                if stream:
                    stream.cleanup()
            await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
            await ctx.voice_client.disconnect()
            await ctx.send("🌙 **Sleep timer expired.** Radio stopped.")
    except ValueError:
        await ctx.send("Usage: `!sleep <minutes>` — e.g. `!sleep 30`")


@bot.command(aliases=["repeat"])
async def loop(ctx: commands.Context):
    """Toggle playlist loop. Usage: !loop"""
    state = get_state(ctx.guild.id)
    state.loop = not state.loop
    status = "🔁 On" if state.loop else "➡️ Off"
    save_queue(state)
    embed = discord.Embed(title=f"Loop {status}", color=discord.Color.blue())
    await ctx.send(embed=embed)


@bot.command()
async def history(ctx: commands.Context):
    """Show last 10 played tracks. Usage: !history"""
    state = get_state(ctx.guild.id)
    if not state.queue or state.index < 0:
        return await ctx.send("Nothing has been played yet.")
    
    start = max(0, state.index - 10)
    played = state.queue[start:state.index]
    if not played:
        return await ctx.send("Nothing has been played yet.")
    
    lines = [f"📜 **Last {len(played)} tracks**"]
    for i, url in enumerate(reversed(played), 1):
        name = url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
        if len(name) > 55:
            name = name[:52] + "..."
        lines.append(f"`{i}.` {name}")
    
    await ctx.send("\n".join(lines))


@bot.command()
async def jump(ctx: commands.Context, *, position: str = ""):
    """Jump to a specific track in the queue. Usage: !jump <number>"""
    if not position:
        return await ctx.send("Usage: `!jump <number>` — jump to track position in queue.")
    
    state = get_state(ctx.guild.id)
    if not state.queue:
        return await ctx.send("Queue is empty.")
    
    try:
        idx = int(position) - 1
        if idx < 0 or idx >= len(state.queue):
            return await ctx.send(f"Position must be between 1 and {len(state.queue)}.")
        
        await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
        state.index = idx
        if await play_current_track(ctx):
            save_queue(state)
    except ValueError:
        await ctx.send("Usage: `!jump <number>` — e.g. `!jump 5`")


@bot.command()
async def clear(ctx: commands.Context):
    """Clear the queue and stop playback. Usage: !clear"""
    state = get_state(ctx.guild.id)
    state.queue = []
    state.index = -1
    save_queue(state)
    
    if ctx.voice_client and ctx.voice_client.is_connected():
        if state.guild_id and state.guild_id in active_streams:
            stream = active_streams.pop(state.guild_id, None)
            if stream:
                stream.cleanup()
        await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
        await ctx.voice_client.disconnect()
    
    await ctx.send("🗑️ Queue cleared.")


@bot.command()
async def ocko(ctx: commands.Context):
    """Show a random ASCII owl. Usage: !ocko"""
    owls = [
        "🦉 **OCKO**\n      ___  \n     / _ \\ \n  _ | |_| |\n / | | __ |\n|  | | |_| |\n \\  \\|  _  |\n  \\   \\_/  |\n   |       |\n   |   |   |\n   |___|___|",
        "🦉 **OCKO**\n    .---.\n   / .-._)\n .´:  _  `.\n |  (_)  |\n :       ;\n  `.___.´",
        "🦉 **OCKO**\n  ,___,\n  {o,o}\n  |)__)\n  -\"--\"-\n  m   m",
        "🦉 **OCKO**\n    ___  \n   (o o) \n  (  V  )\n  --m-m---",
        "🦉 **OCKO**\n  .------.\n  |O  O  |\n  |  V   |\n  `------´\n    ww ww",
    ]
    import random
    owl = random.choice(owls)
    await ctx.send(f"```\n{owl}\n```")


@bot.command()
async def export(ctx: commands.Context):
    """Export the current queue to a text message. Usage: !export"""
    state = get_state(ctx.guild.id)
    if not state.queue:
        return await ctx.send("Queue is empty.")
    
    total = len(state.queue)
    pos = max(0, state.index)
    lines = [f"🎵 Robbo Queue Export ({total} tracks)"]
    
    for i, url in enumerate(state.queue):
        name = url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
        marker = "→ " if i == pos else "  "
        if len(name) > 60:
            name = name[:57] + "..."
        lines.append(f"{marker}{i+1}. {name}")
    
    text = "\n".join(lines)
    if len(text) > 1900:
        text = text[:1900] + f"\n... and {len(text) - 1900} more chars"
    
    await ctx.send(f"```\n{text}\n```")


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
    playing_now = is_playing()
    playing = "🎵 Yes" if playing_now else "⏸️ No"
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
        if url.startswith("https://api.modarchive.org/") or "modarchive" in url:
            filename = modarchive_name_map.get(url, url.split("=")[-1]).replace("_", " ")
            lines.append(f"`{i}.` {filename}")
        elif ASMA_BASE in url:
            filename = url.split("/")[-1].replace(".sap", "").replace("_", " ")
            path_parts = url.replace(ASMA_BASE, "").replace(".sap", "").split("/")
            if len(path_parts) > 1:
                dir_name = path_parts[-2].replace("_", " ")
                lines.append(f"`{i}.` {filename} *({dir_name})*")
            else:
                lines.append(f"`{i}.` {filename}")
        else:
            # HVSC or others - just filename
            filename = url.split("/")[-1]
            for ext in [".sap", ".sid", ".mod", ".xm", ".s3m", ".it"]:
                filename = filename.replace(ext, "")
            filename = filename.replace("_", " ")
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


# ── Blacklist System ────────────────────────────────────────────
def load_blacklist() -> dict:
    """Load the blacklist database from disk."""
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_blacklist(data: dict):
    """Save the blacklist database to disk."""
    try:
        with open(BLACKLIST_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error("Failed to save blacklist: %s", e)


def filter_blacklisted(tracks: list[str], user_id: int | str) -> list[str]:
    """Remove blacklisted URLs from a track list for a given user."""
    blk = load_blacklist()
    user_blk = blk.get(str(user_id), {}).get("tracks", [])
    if not user_blk:
        return tracks
    blacklisted_urls = {t["url"] for t in user_blk}
    filtered = [u for u in tracks if u not in blacklisted_urls]
    if len(filtered) < len(tracks):
        log.info("Filtered %d blacklisted tracks for user %s", len(tracks) - len(filtered), user_id)
    return filtered


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Track reactions on Now Playing embeds → add/remove favorites."""
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


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """Remove favorites when a user removes their reaction from a tracked message."""
    if payload.message_id not in message_track_map:
        return

    track = message_track_map[payload.message_id]
    favs = load_favorites()
    uid = str(payload.user_id)
    user_favs = favs.get(uid, {}).get("tracks", [])
    url = track["url"]
    updated = [t for t in user_favs if t["url"] != url]
    if len(updated) == len(user_favs):
        return

    if uid not in favs:
        return
    favs[uid]["tracks"] = updated
    save_favorites(favs)
    log.info("❤️ Removed from favorites via reaction removal: %s", url)


@bot.command(aliases=["favs", "playlist"])
async def favorites(ctx: commands.Context):
    """Show your favorited tracks. React to any Now Playing embed to add!"""
    favs = load_favorites()
    user_favs = favs.get(str(ctx.author.id), {}).get("tracks", [])

    if not user_favs:
        return await ctx.send("📭 **No favorites yet.** React to a Now Playing embed with any emoji to save tracks here!")

    lines = [f"🎵 **Your Favorites ({len(user_favs)} tracks)**"]
    for i, t in enumerate(user_favs, 1):
        name = t.get("name", "Unknown")
        author_s = f" — {t['author']}" if t.get("author") else ""
        lines.append(f"`{i}.` {name}{author_s}")

    # Discord has 2000 char limit per message
    for chunk in [lines[i:i+15] for i in range(0, len(lines), 15)]:
        await ctx.send("\n".join(chunk))


@bot.command(aliases=["fp"])
async def favplay(ctx: commands.Context, *, number: str = ""):
    """Play your favorited tracks. Usage: !favplay or !favplay <number>"""
    favs = load_favorites()
    user_favs = favs.get(str(ctx.author.id), {}).get("tracks", [])

    if not user_favs:
        return await ctx.send("📭 **No favorites yet.** React to any Now Playing embed with an emoji to save tracks!")

    if not ctx.author.voice:
        return await ctx.send("Join a voice channel first!")

    # Single track by number
    if number:
        try:
            idx = int(number) - 1
            if idx < 0 or idx >= len(user_favs):
                return await ctx.send(f"Number must be between 1 and {len(user_favs)}.")
            tracks_to_play = [user_favs[idx]]
        except ValueError:
            return await ctx.send("Usage: `!favplay <number>` or `!favplay` to play all.")
    else:
        # Play all shuffled, minus blacklisted
        tracks_to_play = list(user_favs)
        # Filter out blacklisted tracks
        blk = load_blacklist()
        user_blk_urls = {t["url"] for t in blk.get(str(ctx.author.id), {}).get("tracks", [])}
        tracks_to_play = [t for t in tracks_to_play if t["url"] not in user_blk_urls]
        random.shuffle(tracks_to_play)

    if not tracks_to_play:
        return await ctx.send("⛔ All your favorites are blacklisted. Nothing to play!")

    # Detect URL types and set collection mode
    state = get_state(ctx.guild.id)
    first_url = tracks_to_play[0]["url"]

    if "asma.atari.org" in first_url or first_url.endswith(".sap"):
        state.collection_mode = "asma"
    elif "hvsc.c64.org" in first_url or first_url.endswith(".sid"):
        state.collection_mode = "hvsc"
    elif "modarchive" in first_url:
        state.collection_mode = "modarchive"

    # Ensure tracks loaded
    if not state.tracks:
        await ensure_tracks(state)

    # Connect to voice
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    vc = await ctx.author.voice.channel.connect()
    state.vc = vc
    state.guild_id = ctx.guild.id
    state.ctx = ctx
    state.loop = True

    # Build queue from favorite URLs
    state.queue = [t["url"] for t in tracks_to_play]
    state.index = 0

    await ctx.send(f"🎵 **Playing {len(tracks_to_play)} favorites!**")

    if await play_current_track(ctx):
        save_queue(state)
        if state.monitor_task and not state.monitor_task.done():
            state.monitor_task.cancel()
        state.monitor_task = bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))


# ── Blacklist Commands ──────────────────────────────────────────
@bot.command(aliases=["blk"])
async def blacklist_track(ctx: commands.Context, *, number: str = ""):
    """Blacklist the current playing track or a queue number. Usage: !blk [number]"""
    state = get_state(ctx.guild.id)

    if number:
        # Blacklist by queue number
        try:
            idx = int(number) - 1
            if idx < 0 or idx >= len(state.queue):
                return await ctx.send(f"Number must be between 1 and {len(state.queue)}.")
            url = state.queue[idx]
            # Get name from the URL
            name = url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
        except ValueError:
            return await ctx.send("Usage: `!blk <number>` to blacklist a track from the queue, or `!blk` for the current track.")
    else:
        # Blacklist currently playing track
        if not state.queue or state.index < 0 or state.index >= len(state.queue):
            return await ctx.send("Nothing is playing right now.")
        url = state.queue[state.index]
        name = (await asyncio.get_event_loop().run_in_executor(None, audacious_song)) or url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")

    blk = load_blacklist()
    uid = str(ctx.author.id)
    user_blk = blk.setdefault(uid, {"tracks": []})

    existing = [t for t in user_blk["tracks"] if t["url"] == url]
    if existing:
        # Already blacklisted — remove it
        user_blk["tracks"] = [t for t in user_blk["tracks"] if t["url"] != url]
        save_blacklist(blk)
        await ctx.send(f"✅ **Un-blacklisted** — `{name}`")
        log.info("⛔ Removed from blacklist by %s: %s", ctx.author, url)
    else:
        # Add to blacklist
        entry = {
            "url": url,
            "name": name,
            "added_at": time.time(),
        }
        user_blk["tracks"].append(entry)
        save_blacklist(blk)
        await ctx.send(f"⛔ **Blacklisted** — `{name}`\n*This track will be skipped when you use !play*")
        log.info("⛔ Added to blacklist by %s: %s — %s", ctx.author, name, url)

    # If this track is currently playing and was blacklisted, skip it
    if existing:
        # It was removed from blacklist, no need to skip
        pass
    elif url == state.queue[state.index] if state.queue and 0 <= state.index < len(state.queue) else False:
        # Currently playing this and blacklisted now — skip
        if ctx.voice_client and ctx.voice_client.is_connected():
            await ctx.send("⏭️ Skipping blacklisted track...")
            await skip_to_next(ctx)


@bot.command(aliases=["blks", "blklist"])
async def blacklist_list(ctx: commands.Context):
    """Show your blacklisted tracks."""
    blk = load_blacklist()
    user_blk = blk.get(str(ctx.author.id), {}).get("tracks", [])

    if not user_blk:
        return await ctx.send("📭 **No blacklisted tracks.** Use `!blk` on a playing track to add it here.")

    lines = [f"⛔ **Your Blacklist ({len(user_blk)} tracks)**"]
    for i, t in enumerate(user_blk, 1):
        name = t.get("name", "Unknown")
        lines.append(f"`{i}.` {name}")

    for chunk in [lines[i:i+15] for i in range(0, len(lines), 15)]:
        await ctx.send("\n".join(chunk))


@bot.command(aliases=["blkrm"])
async def blacklist_remove(ctx: commands.Context, *, number: str):
    """Remove a track from your blacklist by number. Usage: !blkrm <number>"""
    blk = load_blacklist()
    uid = str(ctx.author.id)
    user_blk = blk.get(uid, {}).get("tracks", [])

    if not user_blk:
        return await ctx.send("📭 Your blacklist is empty.")

    try:
        idx = int(number) - 1
        if idx < 0 or idx >= len(user_blk):
            return await ctx.send(f"Number must be between 1 and {len(user_blk)}.")
    except ValueError:
        return await ctx.send("Usage: `!blkrm <number>`")

    removed = user_blk.pop(idx)
    blk[uid]["tracks"] = user_blk
    save_blacklist(blk)
    await ctx.send(f"✅ **Removed from blacklist** — `{removed.get('name', 'Unknown')}`")


# ── HVSC C64 SID Collection ─────────────────────────────────────
# URL → duration in seconds, parsed from Songlengths.txt
sid_durations: dict[str, int] = {}

def _parse_duration(dur_str: str) -> int:
    """Parse duration string 'M:SS', 'M:SS (alt X:XX)' → seconds."""
    dur_str = dur_str.strip().split()[0].split("(")[0].strip()
    if ":" in dur_str:
        try:
            parts = dur_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            pass
    return 0


def parse_songlengths_to_tracks(data: str) -> list[str]:
    """Parse Songlengths.txt → list of full SID URLs.

    Handles both current HVSC MD5 format::

        ; /MUSICIANS/A/Author/Track.sid
        md5hash=1:23

    And older plaintext format::

        ; /MUSICIANS/A/Author/Track.sid = 1:23

    Also populates sid_durations with track durations (seconds).
    """
    urls: list[str] = []
    pending_path: str | None = None

    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("; /"):
            rest = line[2:].strip()  # e.g. "/MUSICIANS/A/Author/Track.sid[ = 1:23]"
            if " = " in rest:
                # Old single-line format: "; /path = M:SS"
                path_part, dur_part = rest.split(" = ", 1)
            else:
                # MD5 format: path on its own line, duration follows
                path_part = rest
                dur_part = None
                pending_path = path_part

            full_url = HVSC_BASE.rstrip("/") + path_part
            urls.append(full_url)

            if dur_part:
                sec = _parse_duration(dur_part)
                if sec:
                    sid_durations[full_url] = sec

        elif "=" in line and pending_path is not None:
            # MD5 duration line: "hash=1:23" or "hash=1:23 (alt 2:34)"
            dur_part = line.split("=", 1)[1]
            full_url = HVSC_BASE.rstrip("/") + pending_path
            sec = _parse_duration(dur_part)
            if sec:
                sid_durations[full_url] = sec
            pending_path = None

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
                json.dump({
                    "tracks": tracks,
                    "durations": sid_durations,
                    "downloaded": time.time(),
                }, f)
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
        # Restore duration map from cache (if available)
        cached_durs = data.get("durations", {})
        if cached_durs:
            sid_durations.clear()
            # Convert string keys back to int if needed (JSON has string keys)
            for k, v in cached_durs.items():
                sid_durations[k] = int(v) if not isinstance(v, int) else v
            log.info("HVSC: restored %d durations from cache", len(cached_durs))
        log.info("HVSC: loaded %d tracks from cache", len(tracks))
        return tracks
    except Exception as e:
        log.warning("HVSC cache load error: %s", e)
        return None


def load_modarchive_cache() -> list[str] | None:
    """Load ModArchive track list from cache."""
    try:
        if not os.path.exists(MODARCHIVE_CACHE_FILE):
            return None
        with open(MODARCHIVE_CACHE_FILE) as f:
            modules = json.load(f)
        if not isinstance(modules, list) or len(modules) < 10:
            log.warning("ModArchive cache too small (%d entries), rebuilding needed", len(modules))
            return None
        global modarchive_name_map
        modarchive_name_map = {}
        # Convert to URL list (like HVSC/ASMA track lists)
        tracks = []
        for m in modules:
            if isinstance(m, dict) and "url" in m:
                tracks.append(m["url"])
                modarchive_name_map[m["url"]] = m.get("name", m["url"].split("=")[-1])
        log.info("ModArchive: loaded %d tracks from cache (%d raw entries)", len(tracks), len(modules))
        return tracks
    except Exception as e:
        log.warning("ModArchive cache load error: %s", e)
        return None


def load_ay_cache() -> list[str] | None:
    """Load AY track list from local cache."""
    try:
        if not os.path.exists(AY_CACHE):
            return None
        with open(AY_CACHE) as f:
            data = json.load(f)
        tracks = [t["path"] for t in data.get("tracks", [])]
        log.info("AY: loaded %d tracks from cache", len(tracks))
        return tracks
    except Exception as e:
        log.warning("AY cache load error: %s", e)
        return None


def load_tiny_cache() -> list[str] | None:
    """Load Tiny Music track list from local cache."""
    try:
        if not os.path.exists(TINY_CACHE):
            return None
        with open(TINY_CACHE) as f:
            data = json.load(f)
        tracks = [t["path"] for t in data.get("tracks", [])]
        log.info("Tiny: loaded %d tracks from cache", len(tracks))
        return tracks
    except Exception as e:
        log.warning("Tiny cache load error: %s", e)
        return None


# ── SNES SPC Collection ────────────────────────────────────────────
# RSN URL → game metadata
snes_metadata: dict[str, dict] = {}

def load_snes_cache() -> list[str] | None:
    """Load SNES SPC game set list from cache. Returns list of RSN URLs."""
    try:
        if not os.path.exists(SNES_CACHE_FILE):
            return None
        with open(SNES_CACHE_FILE) as f:
            data = json.load(f)
        game_sets = data.get("tracks", [])
        urls = []
        snes_metadata.clear()
        for g in game_sets:
            url = g.get("rsn_url", "")
            if url:
                urls.append(url)
                snes_metadata[url] = g
        log.info("SNES: loaded %d game sets from cache", len(urls))
        return urls
    except Exception as e:
        log.warning("SNES cache load error: %s", e)
        return None


async def download_spc_rsn(rsn_url: str, spc_now: str, game_name: str) -> str | None:
    """Download an RSN file and extract SPC files to a local cache dir.
    Returns the directory path containing extracted SPCs."""
    game_dir = os.path.join(SNES_SPC_DIR, re.sub(r'[^a-zA-Z0-9_-]', '_', spc_now))
    os.makedirs(game_dir, exist_ok=True)

    # Check if already cached
    existing = [f for f in os.listdir(game_dir) if f.endswith(".spc")]
    if existing:
        log.info("SNES: using cached SPCs for %s (%d files)", game_name, len(existing))
        return game_dir

    # Download RSN
    rsn_path = os.path.join(game_dir, f"{spc_now}.rsn")
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(rsn_url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                resp.raise_for_status()
                data = await resp.read()
        with open(rsn_path, "wb") as f:
            f.write(data)
    except Exception as e:
        log.error("SNES: RSN download failed for %s: %s", game_name, e)
        return None

    # Extract SPC files
    try:
        proc = await asyncio.create_subprocess_exec(
            "unrar", "e", "-y", rsn_path, game_dir + "/",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        # Clean up RSN after extraction
        os.remove(rsn_path)
        extracted = [f for f in os.listdir(game_dir) if f.endswith(".spc")]
        log.info("SNES: extracted %d SPC files for %s", len(extracted), game_name)
        return game_dir
    except Exception as e:
        log.error("SNES: RSN extraction failed for %s: %s", game_name, e)
        return None


async def play_current_spc_track(ctx, state, game_entry: dict):
    """Download RSN, extract SPCs, and play via Audacious."""
    spc_now = game_entry["spc_now"]
    game_name = game_entry.get("name", "Unknown")
    composers = game_entry.get("composers", [])

    # Download and extract
    game_dir = await download_spc_rsn(game_entry["rsn_url"], spc_now, game_name)
    if not game_dir:
        await ctx.send(f"❌ Failed to download/extract `{game_name}`")
        return False

    # Get sorted SPC files
    spc_files = sorted([f for f in os.listdir(game_dir) if f.endswith(".spc")])
    if not spc_files:
        await ctx.send(f"❌ No SPC files found for `{game_name}`")
        return False

    first_spc = os.path.join(game_dir, spc_files[0])

    # Stop existing playback and play via Audacious
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    await asyncio.get_event_loop().run_in_executor(None, audacious_play, first_spc)

    state.current_sap_path = first_spc

    # Setup MonitorAudioSource
    if state.vc and state.vc.is_connected():
        state.vc.stop()
        old_source = active_streams.pop(state.guild_id, None)
        if old_source:
            old_source.cleanup()
        source = MonitorAudioSource(SINK_NAME)
        state.vc.play(
            source,
            after=lambda e: _after_stream_end(state.guild_id, e),
        )
        active_streams[state.guild_id] = source

    total = len(state.queue)
    pos = state.index + 1

    embed = discord.Embed(
        title=game_name[:256],
        color=discord.Color.from_str("#E74C3C"),
    )
    if composers:
        embed.add_field(name="Composer(s)", value=", ".join(composers[:5]), inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    embed.add_field(name="Tracks", value=str(len(spc_files)), inline=True)
    embed.set_footer(text="SNES Radio — Super Nintendo SPC")

    np_msg = await ctx.send(embed=embed)
    message_track_map[np_msg.id] = {
        "url": game_entry["rsn_url"],
        "name": game_name,
        "author": ", ".join(composers) if composers else "Unknown",
        "timestamp": time.time(),
    }
    log.info("SNES now playing: %s — %s", game_name, ", ".join(composers) if composers else "?")
    return True


async def download_modarchive_module(url: str, retries: int = 2) -> str:
    """Download a module from ModArchive API and return local filepath.
    Preserves the real filename from Content-Disposition header."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            filepath = build_temp_path(url)
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BorutaBot)"}) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
                    # Try to get real filename from Content-Disposition
                    cd = resp.headers.get("Content-Disposition", "")
                    m = re.search(r'filename=([^;]+)', cd)
                    if m:
                        fname = m.group(1).strip('" ')
                        if fname:
                            # Use real filename in temp path
                            digest = sha1(url.encode("utf-8")).hexdigest()[:12]
                            filepath = os.path.join(TEMP_DIR, f"{digest}_{fname}")
            with open(filepath, "wb") as f:
                f.write(data)
            return filepath
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = e
            if attempt < retries:
                await asyncio.sleep(2)
    raise last_err  # type: ignore[reportGeneralTypeIssues]


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
            meta["sid_name"] = url.rstrip("/").split("/")[-1]
    except Exception as e:
        log.warning("SID meta fetch error for %s: %s", url, e)
    return meta


def cleanup_orphan_players():
    """Kill orphaned audacious/ffmpeg processes from crashed bot sessions.
    Does NOT kill ffmpeg (MonitorAudioSource) since that's managed in-band."""
    subprocess.run(["pkill", "-x", "audacious"], capture_output=True)


def stop_all_players():
    """Stop Audacious playback and clear playlist for collection switch."""
    audacious_stop()


# ── Collection Commands ─────────────────────────────────────────
@bot.command(aliases=["c64", "sid"])
async def hvsc(ctx: commands.Context):
    """Switch to C64 SID collection (HVSC)."""
    state = get_state(ctx.guild.id)
    if state.collection_mode == "hvsc" and state.tracks:
        await ctx.send("📀 **Already in C64 SID mode.** Use `!play` to start!")
        return
    await ctx.send("🔄 **Loading C64 SID collection (60,000+ tracks)...**")
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    # ── Cancel old monitor IMMEDIATELY to prevent race with 3s grace timer ──
    if state.monitor_task and not state.monitor_task.done():
        state.monitor_task.cancel()
        try:
            await state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass
    tracks = await asyncio.get_event_loop().run_in_executor(None, load_cached_hvsc)
    if not tracks:
        tracks = await asyncio.get_event_loop().run_in_executor(None, download_hvsc_index)
    if not tracks:
        return await ctx.send("❌ Failed to load HVSC index. Check config or try again.")
    state.collection_mode = "hvsc"
    save_last_collection("hvsc")
    await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, "hvsc")
    state.tracks = tracks
    state.queue = []
    state.index = -1
    await ctx.send(f"📀 **C64 SID collection ready — {len(tracks)} tracks!**")
    log.info("HVSC: collection switched, %d tracks loaded", len(tracks))
    await cleanup_hvsc_file(ctx, tracks)
    await auto_play_after_switch(ctx, state)


async def cleanup_hvsc_file(ctx, tracks):
    """Store the HVSC tracklist for search (no local copies yet)."""
    # Just let user know search won't have metadata until they use it
    pass


@bot.command()
async def asma(ctx: commands.Context):
    """Switch back to Atari SAP collection (ASMA)."""
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    state = get_state(ctx.guild.id)
    # ── Cancel old monitor IMMEDIATELY to prevent race with 3s grace timer ──
    if state.monitor_task and not state.monitor_task.done():
        state.monitor_task.cancel()
        try:
            await state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass
    state.collection_mode = "asma"
    save_last_collection("asma")
    await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, "asma")
    cached = load_cached_tracklist()
    if cached:
        state.tracks = cached
        await ctx.send(f"📀 **Switched to ASMA Atari SAP — {len(cached)} tracks!**")
    else:
        state.tracks = []
        await ctx.send("📀 **Switched to ASMA Atari SAP.** Use `!play` to crawl the archive.")
    state.queue = []
    state.index = -1
    log.info("ASMA: collection switched")
    await auto_play_after_switch(ctx, state)


@bot.command(aliases=["modarchive", "tracker", "modules"])
async def mod(ctx: commands.Context):
    """Switch to ModArchive collection (MOD/XM/S3M/IT modules)."""
    state = get_state(ctx.guild.id)
    if state.collection_mode == "modarchive" and state.tracks:
        await ctx.send("🟠 **Already in ModArchive mode.** Use `!play` to start!")
        return
    await ctx.send("🟠 **Loading ModArchive collection (100,000+ modules)...**")
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    # ── Cancel old monitor IMMEDIATELY to prevent race with 3s grace timer ──
    if state.monitor_task and not state.monitor_task.done():
        state.monitor_task.cancel()
        try:
            await state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass
    tracks = await asyncio.get_event_loop().run_in_executor(None, load_modarchive_cache)
    if not tracks:
        return await ctx.send("❌ ModArchive cache not found. Run `build_modarchive_index.py` first!\n"
                              "The index builder is running in the background — wait a few minutes and try again.")
    state.collection_mode = "modarchive"
    save_last_collection("modarchive")
    await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, "modarchive")
    state.tracks = tracks
    state.queue = []
    state.index = -1
    await ctx.send(f"🟠 **ModArchive collection ready — {len(tracks)} modules!**\n"
                   "FastTracker / ProTracker / ScreamTracker / Impulse Tracker — all formats!")
    log.info("ModArchive: collection switched, %d tracks loaded", len(tracks))
    await auto_play_after_switch(ctx, state)


@bot.command(aliases=["zx", "zxspectrum", "spectrum"])
async def ay(ctx: commands.Context):
    """Switch to local ZX Spectrum AY archive."""
    state = get_state(ctx.guild.id)
    if state.collection_mode == "ay" and state.tracks:
        await ctx.send("🔵 **Already in ZX Spectrum AY mode.** Use `!play` to start!")
        return
    await ctx.send("🔵 **Loading local AY archive (4,500+ tracks)...**")
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    # ── Cancel old monitor IMMEDIATELY to prevent race with 3s grace timer ──
    if state.monitor_task and not state.monitor_task.done():
        state.monitor_task.cancel()
        try:
            await state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass
    tracks = await asyncio.get_event_loop().run_in_executor(None, load_ay_cache)
    if not tracks:
        return await ctx.send("❌ AY cache not found. Run `build_ay_index.py` first!")
    state.collection_mode = "ay"
    save_last_collection("ay")
    await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, "ay")
    state.tracks = tracks
    state.queue = []
    state.index = -1
    await ctx.send(f"🔵 **ZX Spectrum AY archive ready — {len(tracks)} tracks!**\\n"
                   "AY-3-8910 chiptunes — AYGOR / Ironfist / Tr_Songs / SoLOCPC / Bulba")
    log.info("AY: collection switched, %d tracks loaded", len(tracks))
    await auto_play_after_switch(ctx, state)


@bot.command(aliases=["tm", "demoscene"])
async def tiny(ctx: commands.Context):
    """Switch to local Tiny Music demoscene module archive."""
    state = get_state(ctx.guild.id)
    if state.collection_mode == "tiny" and state.tracks:
        await ctx.send("🎵 **Already in Tiny Music mode.** Use `!play` to start!")
        return
    await ctx.send("🎵 **Loading Tiny Music archive (418 curated demoscene modules)...**")
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    # ── Cancel old monitor IMMEDIATELY to prevent race ──
    if state.monitor_task and not state.monitor_task.done():
        state.monitor_task.cancel()
        try:
            await state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass
    tracks = await asyncio.get_event_loop().run_in_executor(None, load_tiny_cache)
    if not tracks:
        return await ctx.send("❌ Tiny Music cache not found. Run `build_tiny_index.py` first!")
    state.collection_mode = "tiny"
    save_last_collection("tiny")
    await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, "tiny")
    state.tracks = tracks
    state.queue = []
    state.index = -1
    await ctx.send(f"🎵 **Tiny Music archive ready — {len(tracks)} modules!**\n"
                   "Curated demoscene — MOD / XM / IT / S3M / MED / DMF")
    log.info("Tiny: collection switched, %d tracks loaded", len(tracks))
    await auto_play_after_switch(ctx, state)


@bot.command(aliases=["snes", "spc", "supernintendo", "nintendo"])
async def snes_cmd(ctx: commands.Context, *, query: str = None):
    """Switch to SNES SPC or search. Usage: !snes [search <term>]"""
    state = get_state(ctx.guild.id)

    # ── Search mode ──
    if query:
        query_lower = query.strip().lower()
        # Load metadata if not already loaded
        if not snes_metadata:
            await asyncio.get_event_loop().run_in_executor(None, load_snes_cache)
        if not snes_metadata:
            return await ctx.send("❌ SNES SPC cache not found. Run `build_snes_index.py` first!")

        results = []
        for url, entry in snes_metadata.items():
            name = entry.get("name", "")
            composers = ", ".join(entry.get("composers", []))
            haystack = (name + " " + composers).lower()
            # Split query into words — all must match (AND search)
            words = query_lower.split()
            if all(w in haystack for w in words):
                results.append(entry)
                if len(results) >= 10:
                    break

        if not results:
            return await ctx.send(f"🔍 **No SNES games matching `{query}`.**")

        lines = [f"🔍 **SNES results for `{query}`**"]
        for i, g in enumerate(results, 1):
            c = ", ".join(g.get("composers", [])) or "Unknown"
            lines.append(f"`{i}.` **{g.get('name', '?')}** — {c} ({g.get('tracks', '?')}t)")
        lines.append("")
        lines.append("Use `!play <number>` to play, or `!snes` to switch to SPC collection.")
        state.search_results = [g["rsn_url"] for g in results]
        return await ctx.send("\n".join(lines))

    # ── Switch mode (original behaviour) ──
    if state.collection_mode == "spc" and state.tracks:
        await ctx.send("🔴 **Already in SNES SPC mode.** Use `!play` to start!")
        return
    await ctx.send("🔴 **Loading SNES SPC collection (Super Nintendo chiptunes)...**")
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    # ── Cancel old monitor IMMEDIATELY to prevent race ──
    if state.monitor_task and not state.monitor_task.done():
        state.monitor_task.cancel()
        try:
            await state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass
    tracks = await asyncio.get_event_loop().run_in_executor(None, load_snes_cache)
    if not tracks:
        return await ctx.send("❌ SNES SPC cache not found. Run `build_snes_index.py` first!")
    state.collection_mode = "spc"
    save_last_collection("spc")
    await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, "spc")
    state.tracks = tracks
    state.queue = []
    state.index = -1
    await ctx.send(f"🔴 **SNES SPC collection ready — {len(tracks)} games!**\n"
                   "Super Nintendo chiptunes via SNESmusic.org — download & play on demand")
    log.info("SNES: collection switched, %d game sets loaded", len(tracks))
    await auto_play_after_switch(ctx, state)


@bot.command(aliases=["mode", "collection", "all"])
async def status(ctx: commands.Context):
    """Show all collections overview and current playlist stats."""
    state = get_state(ctx.guild.id)

    # ── Quick cache counts (reads JSON headers only) ──
    cache_counts = {}
    cache_map = {
        "hvsc_cache.json":     ("🟣", "C64 SID (HVSC)"),
        "asma_cache.json":     ("🟢", "Atari SAP (ASMA)"),
        "modarchive_cache.json": ("🟠", "Tracker (ModArchive)"),
        "ay_cache.json":       ("🔵", "ZX Spectrum AY"),
        "tiny_cache.json":     ("🎵", "Tiny Music"),
        "snes_cache.json":     ("🔴", "SNES SPC"),
    }
    for fname, (icon, label) in cache_map.items():
        try:
            import json
            fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
            with open(fpath) as f:
                data = json.load(f)
            if isinstance(data, list):
                count = len(data)
            elif isinstance(data, dict):
                count = data.get("total_sets") or len(data.get("tracks", data.get("count", [])))
            else:
                count = "?"
        except Exception:
            count = "⚠️"
        cache_counts[label] = (icon, count)

    # ── Current state ──
    mode_icons = {
        "hvsc": "🟣", "asma": "🟢", "modarchive": "🟠",
        "ay": "🔵", "tiny": "🎵", "spc": "🔴",
    }
    mode_labels = {
        "hvsc": "HVSC", "asma": "ASMA", "modarchive": "ModArchive",
        "ay": "AY", "tiny": "Tiny", "spc": "SNES",
    }
    current_icon = mode_icons.get(state.collection_mode, "⚪")
    current_label = mode_labels.get(state.collection_mode, "Unknown")
    total = len(state.tracks) if state.tracks else 0
    qlen = len(state.queue)
    pos = state.index + 1 if state.index >= 0 else 0
    playing_now = is_playing()
    playing = "🎵 Yes" if playing_now else "⏸️ No"

    # ── Build message ──
    lines = [
        f"🌲 **Robbo — wszystkie kolekcje**",
        "",
    ]
    for label, (icon, count) in cache_counts.items():
        hl = "◀" if label == current_label else ""
        lines.append(f"{icon} **{label}**: `{count:,}` {hl}".replace(",", " "))
    lines += [
        "",
        f"━━━━━━━━━━━━━━━━━",
        f"{current_icon} **Teraz: {current_label}** — {total} tracków",
        f"• Kolejka: **{qlen - pos}/{qlen}** | Odtwarzanie: {playing} | Pętla: {'🔁 On' if state.loop else '➡️ Off'}",
    ]
    await ctx.send("\n".join(lines))


@bot.command(aliases=["switch", "toggle", "fl"])
async def flip(ctx: commands.Context):
    """Toggle between collections: HVSC → ASMA → ModArchive → AY → Tiny → SNES → HVSC ..."""
    state = get_state(ctx.guild.id)
    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)

    # ── Cancel old monitor IMMEDIATELY — prevent race with 3s grace timer ──
    if state.monitor_task and not state.monitor_task.done():
        state.monitor_task.cancel()
        try:
            await state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass
    state.pre_downloaded = None

    # Flip sequence for visual indicator
    flip_seq = ["🟣HVSC", "🟢ASMA", "🟠Mod", "🔵AY", "🎵Tiny", "🔴SNES"]

    if state.collection_mode == "hvsc":
        # HVSC → ASMA
        state.collection_mode = "asma"
        save_last_collection("asma")
        await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, state.collection_mode)
        cached = await asyncio.get_event_loop().run_in_executor(None, load_cached_tracklist)
        seq = " → ".join("**" + s + "**" if s == "🟢ASMA" else s for s in flip_seq)
        if cached:
            state.tracks = cached
            await ctx.send(f"🟢 **Switched to Atari SAP (ASMA)!**\n{seq}")
        else:
            state.tracks = []
            await ctx.send(f"🟢 **Switched to Atari SAP (ASMA).**\n{seq}")
        log.info("ASMA: collection switched via flip")

    elif state.collection_mode == "asma":
        # ASMA → ModArchive
        old_tracks = list(state.tracks) if state.tracks else []
        state.collection_mode = "modarchive"
        save_last_collection("modarchive")
        await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, state.collection_mode)
        tracks = await asyncio.get_event_loop().run_in_executor(None, load_modarchive_cache)
        seq = " → ".join("**" + s + "**" if s == "🟠Mod" else s for s in flip_seq)
        if tracks:
            state.tracks = tracks
            await ctx.send(f"🟠 **Switched to ModArchive — {len(tracks)} modules!**\n{seq}")
        else:
            await ctx.send(f"🟠 **ModArchive cache not ready.** Staying on ASMA.\n{seq}")
            state.collection_mode = "asma"
            state.tracks = old_tracks
            save_last_collection("asma")
        log.info("ModArchive: collection switched via flip")

    elif state.collection_mode == "modarchive":
        # ModArchive → AY
        old_tracks = list(state.tracks) if state.tracks else []
        state.collection_mode = "ay"
        save_last_collection("ay")
        await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, state.collection_mode)
        tracks = await asyncio.get_event_loop().run_in_executor(None, load_ay_cache)
        seq = " → ".join("**" + s + "**" if s == "🔵AY" else s for s in flip_seq)
        if tracks:
            state.tracks = tracks
            await ctx.send(f"🔵 **Switched to ZX Spectrum AY — {len(tracks)} tracks!**\n{seq}")
        else:
            await ctx.send(f"🔵 **AY cache not ready.** Staying on ModArchive.\n{seq}")
            state.collection_mode = "modarchive"
            state.tracks = old_tracks
            save_last_collection("modarchive")
        log.info("AY: collection switched via flip")

    elif state.collection_mode == "ay":
        # AY → Tiny Music
        old_tracks = list(state.tracks) if state.tracks else []
        state.collection_mode = "tiny"
        save_last_collection("tiny")
        await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, state.collection_mode)
        tracks = await asyncio.get_event_loop().run_in_executor(None, load_tiny_cache)
        seq = " → ".join("**" + s + "**" if s == "🎵Tiny" else s for s in flip_seq)
        if tracks:
            state.tracks = tracks
            await ctx.send(f"🎵 **Switched to Tiny Music — {len(tracks)} modules!**\n{seq}")
        else:
            await ctx.send(f"🎵 **Tiny cache not ready.** Staying on AY.\n{seq}")
            state.collection_mode = "ay"
            state.tracks = old_tracks
            save_last_collection("ay")
        log.info("Tiny: collection switched via flip")

    elif state.collection_mode == "tiny":
        # Tiny → SNES SPC
        old_tracks = list(state.tracks) if state.tracks else []
        state.collection_mode = "spc"
        save_last_collection("spc")
        await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, state.collection_mode)
        tracks = await asyncio.get_event_loop().run_in_executor(None, load_snes_cache)
        seq = " → ".join("**" + s + "**" if s == "🔴SNES" else s for s in flip_seq)
        if tracks:
            state.tracks = tracks
            await ctx.send(f"🔴 **Switched to SNES SPC — {len(tracks)} games!**\n{seq}")
        else:
            await ctx.send(f"🔴 **SNES cache not ready.** Staying on Tiny.\n{seq}")
            state.collection_mode = "tiny"
            state.tracks = old_tracks
            save_last_collection("tiny")
        log.info("SNES: collection switched via flip")

    else:
        # SPC → HVSC
        old_mode = state.collection_mode
        old_tracks = list(state.tracks) if state.tracks else []
        state.collection_mode = "hvsc"
        save_last_collection("hvsc")
        await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, state.collection_mode)
        tracks = await asyncio.get_event_loop().run_in_executor(None, load_cached_hvsc)
        seq = " → ".join("**" + s + "**" if s == "🟣HVSC" else s for s in flip_seq)
        if not tracks:
            await ctx.send(f"🔄 Loading C64 SID collection (60,000+ tracks)...\n{seq}")
            tracks = await asyncio.get_event_loop().run_in_executor(None, download_hvsc_index)
        if tracks:
            state = get_state(ctx.guild.id)
            state.tracks = tracks
            await ctx.send(f"🟣 **Switched to C64 SID (HVSC) — {len(tracks)} tracks!**\n{seq}")
        else:
            await ctx.send(f"❌ Could not load HVSC. Try `!hvsc` manually.\n{seq}")
            state.collection_mode = old_mode
            state.tracks = old_tracks
            save_last_collection(old_mode)
        log.info("HVSC: collection switched via flip")

    # ── Auto-play after switching if user is in voice ──
    await auto_play_after_switch(ctx, state)


async def auto_play_after_switch(ctx: commands.Context, state) -> None:
    """Auto-play after collection switch if user is in voice."""
    if not ctx.author.voice or not state.tracks:
        return
    log.info("auto_play_after_switch: queue_len=%d, index=%d", len(state.queue), state.index)
    state.queue = filter_blacklisted(list(state.tracks), ctx.author.id)
    if PLAYBACK_SHUFFLE:
        random.shuffle(state.queue)
    state.index = 0
    state.loop = PLAYBACK_LOOP

    if not state.vc or not state.vc.is_connected():
        try:
            state.vc = await ctx.author.voice.channel.connect()
        except Exception as e:
            await ctx.send(f"❌ Could not connect: {e}")
            return
    state.guild_id = ctx.guild.id
    state.ctx = ctx
    result = await play_current_track(ctx)
    log.info("auto_play_after_switch: play_current_track returned %s", result)
    if result:
        save_queue(state)
        if state.monitor_task and not state.monitor_task.done():
            state.monitor_task.cancel()
        state.monitor_task = bot.loop.create_task(monitor_playback(ctx, state.vc, ctx.guild.id))


# ── Playback Monitor ────────────────────────────────────────────
async def monitor_playback(ctx: commands.Context, vc: discord.VoiceClient, guild_id: int):
    """Monitor playback, auto-advance tracks, and disconnect on empty channel.
    Uses Audacious is_playing() for ALL formats (SAP, SID, MOD, AY via console/GME)."""
    empty_since = None
    not_playing_since = None
    GRACE_SECONDS = 3
    while vc.is_connected() and not _shutdown_flag.is_set():
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        state = get_state(guild_id)

        # Check for empty channel
        if vc.channel and len(vc.channel.members) <= 1:
            if empty_since is None:
                empty_since = time.time()
            elif AUTO_EMPTY_TIMEOUT > 0 and (time.time() - empty_since) >= AUTO_EMPTY_TIMEOUT:
                log.info("Channel empty for %ds, disconnecting", AUTO_EMPTY_TIMEOUT)
                state = get_state(guild_id)
                stream = active_streams.pop(guild_id, None)
                if stream:
                    stream.cleanup()
                await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
                await vc.disconnect()
                await ctx.send("🌙 No one listening. Stopping Radio.")
                break
        else:
            empty_since = None

        # Check if Audacious is still playing
        # For SID: Songlengths.md5 tells Audacious when to stop, so it auto-advances
        # For SAP/MOD: natural end triggers stop
        # When stopped → grace 3s → skip to next track
        playing = await asyncio.get_event_loop().run_in_executor(None, is_playing)

        # Also stop tracks with unknown length after max time (fallback for SID and modarchive)
        timeout_secs = 180 if state.collection_mode == "hvsc" else 300  # 3min for SID, 5min for modules
        if playing and state.current_sap_path:
            elapsed_s = await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(
                ["audtool", "current-song-output-length-seconds"], capture_output=True, text=True
            ))
            try:
                secs = int(elapsed_s.stdout.strip())
                if secs > timeout_secs and secs < 10000:
                    log.info("Track exceeded %ds fallback (%ds), force-stopping", timeout_secs, secs)
                    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
                    not_playing_since = None
                    if state.loop or state.index < len(state.queue) - 1:
                        log.info("monitor_playback: skip_to_next (timeout_exceeded)")
                        await skip_to_next(ctx)
                        continue
                    else:
                        stream = active_streams.pop(guild_id, None)
                        if stream:
                            stream.cleanup()
                        if vc.is_connected():
                            await vc.disconnect()
                        await ctx.send("Playlist ended. Use !play to restart.")
                        break
            except (ValueError, OSError):
                pass

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
    
    stream = active_streams.pop(guild_id, None)
    if stream:
        stream.cleanup()


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

# ── PID Lock (zapobiega duplikatom) ─────────────────────────────
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "obibok.pid")

def acquire_lock() -> int:
    """Sprawdź czy inna instancja bota już żyje. Jeśli tak — wyjdź.
    Jeśli lock jest stary (proces nie żyje) — nadpisz.
    Zwraca własne PID.
    """
    my_pid = os.getpid()
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE) as f:
                old_pid_str = f.read().strip()
            if old_pid_str:
                old_pid = int(old_pid_str)
                # Sprawdź czy ten PID jeszcze żyje i czy to nasz bot
                try:
                    os.kill(old_pid, 0)  # test czy proces istnieje
                    # Żyje — sprawdź czy to na pewno bot, a nie przypadkowy PID
                    with open(f"/proc/{old_pid}/cmdline", "rb") as cf:
                        cmd = cf.read().decode("utf-8", errors="replace")
                    if "robbo-obibok.py" in cmd:
                        print(f"PID {old_pid} już uruchomiony. Zabij go najpierw lub poczekaj aż zgaśnie.")
                        sys.exit(1)
                except (OSError, ProcessLookupError):
                    # Stary PID nie żyje — nadpisujemy
                    pass
    except Exception as e:
        print(f"Błąd locka ({e}), startuję mimo wszystko...")

    with open(LOCK_FILE, "w") as f:
        f.write(str(my_pid))
    return my_pid

def release_lock():
    """Usuń lock file przy czystym wyjściu."""
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE) as f:
                lock_pid = f.read().strip()
            if lock_pid == str(os.getpid()):
                os.unlink(LOCK_FILE)
    except Exception:
        pass

# ── Main ────────────────────────────────────────────────────────
if not BOT_TOKEN:
    raise SystemExit("Set DISCORD_BOT_TOKEN environment variable.")

acquire_lock()

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
    global active_streams
    _shutdown_flag.set()
    log.info("Shutting down gracefully...")
    release_lock()
    for guild_id, source in list(active_streams.items()):
        source.cleanup()
    active_streams.clear()
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    for vc in list(bot.voice_clients):
        await vc.disconnect()
    cleanup_temp()

_shutdown_flag = asyncio.Event()

def handle_signal(signum, frame):
    """Signal handler: close the bot gracefully. Thread-safe."""
    log.info("Received signal %d, shutting down...", signum)
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(graceful_shutdown())
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(bot.close()))

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    ate = __import__("atexit")
    ate.register(release_lock)
    try:
        bot.run(BOT_TOKEN)
    finally:
        release_lock()
