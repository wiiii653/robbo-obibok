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

# Single computation of script directory (was repeated 21× at module level)
_ROOT = os.path.dirname(os.path.abspath(__file__))

# Shared HTTP session for downloads (connection pooling, keep-alive)
_shared_session: aiohttp.ClientSession | None = None

async def get_shared_session() -> aiohttp.ClientSession:
    """Return a shared aiohttp.ClientSession with connection pooling."""
    global _shared_session
    if _shared_session is None or _shared_session.closed:
        _shared_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=10, limit_per_host=5, enable_cleanup_closed=True),
        )
    return _shared_session

async def close_shared_session():
    """Close the shared session during shutdown."""
    global _shared_session
    if _shared_session and not _shared_session.closed:
        await _shared_session.close()
        _shared_session = None
import yaml
from urllib.parse import urljoin
from hashlib import sha1, md5

from logging.handlers import RotatingFileHandler

_LOG_FILE = os.path.join(_ROOT, "bot_output.log")
_file_handler = RotatingFileHandler(
    _LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[_file_handler, logging.StreamHandler()],
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
    cfg_path = os.path.join(_ROOT, "config.yaml")
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


def _cleanup_orphaned_temp_dirs():
    """Remove orphaned asma_bot_* temp dirs from previous crashed sessions."""
    import glob
    removed = 0
    for d in glob.glob("/tmp/asma_bot_*"):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    if removed:
        log.info("Startup cleanup: removed %d orphaned temp dirs", removed)


_cleanup_orphaned_temp_dirs()
TEMP_DIR = tempfile.mkdtemp(prefix="asma_bot_")
ASMA_BASE = CONFIG["asma"]["base_url"]
CRAWL_TIMEOUT = CONFIG["asma"]["crawl_timeout"]
CACHE_TTL = CONFIG["asma"]["cache_ttl"]
CACHE_FILE = os.path.join(_ROOT, "asma_cache.json")
QUEUE_DIR = os.path.join(_ROOT, "queues")
COMMAND_PREFIX = CONFIG["command_prefix"]
PLAYBACK_LOOP = CONFIG["playback"]["loop"]
PLAYBACK_SHUFFLE = CONFIG["playback"]["shuffle"]

# ── Local AY Archive (ZX Spectrum) ──────────────────────────────
AY_DIR = os.path.join(_ROOT, "archiwum", "ay")
AY_CACHE = os.path.join(_ROOT, "ay_cache.json")

# ── Local YM Archive (Atari ST) ─────────────────────────────────
YM_DIR = os.path.join(_ROOT, "archiwum", "ym")
YM_CACHE = os.path.join(_ROOT, "ym_cache.json")
YM_TEMP_DIR = os.path.join(YM_DIR, "tmp_wav")  # decoded WAV cache
_ym_last_wav_path: str | None = None  # track the last WAV for cleanup

# ── Local Tiny Music (Demoscene Modules) ────────────────────────
TINY_DIR = os.path.join(_ROOT, "archiwum", "tiny")
TINY_CACHE = os.path.join(_ROOT, "tiny_cache.json")
ASMA_DIR = os.path.join(_ROOT, "archiwum", "asma")
HVSC_DIR = os.path.join(_ROOT, "archiwum", "hvsc", "C64Music")

# ── Favorites System ────────────────────────────────────────────
FAVORITES_FILE = os.path.join(_ROOT, "favorites.json")
PLAYLIST_DIR = os.path.join(_ROOT, "playlists")

# ── Blacklist System ────────────────────────────────────────────
BLACKLIST_FILE = os.path.join(_ROOT, "blacklist.json")

# ── Last Collection Mode ────────────────────────────────────────
LAST_COLLECTION_FILE = os.path.join(_ROOT, "last_collection.txt")

def load_last_collection() -> str | None:
    try:
        with open(LAST_COLLECTION_FILE) as f:
            mode = f.read().strip()
            if mode in ("asma", "hvsc", "modarchive", "ay", "tiny", "spc", "ym"):
                return mode
    except (FileNotFoundError, OSError):
        pass
    return None

def _atomic_json_write(path: str, data: dict) -> None:
    """Write JSON atomically: tmp → rename prevents partial writes on crash."""
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)  # atomic rename
    except Exception as e:
        log.error("Failed atomic write to %s: %s", path, e)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

def save_last_collection(mode: str):
    try:
        with open(LAST_COLLECTION_FILE, "w") as f:
            f.write(mode)
    except OSError:
        pass

# ── SNES SPC Collection (SNESmusic.org) ──────────────────────────
SNES_BASE = "https://snesmusic.org/v2/"
SNES_CACHE_FILE = os.path.join(_ROOT, "snes_cache.json")
SNES_SPC_DIR = os.path.join(_ROOT, "archiwum", "spc")
HVSC_BASE = CONFIG.get("hvsc", {}).get("base_url", "https://www.hvsc.c64.org/download/C64Music/")
HVSC_SONGLENGTHS_URL = CONFIG.get("hvsc", {}).get("songlengths_url", "")
HVSC_CACHE_TTL = CONFIG.get("hvsc", {}).get("cache_ttl", 168)
HVSC_CACHE_FILE = os.path.join(_ROOT, "hvsc_cache.json")
DEFAULT_COLLECTION_MODE = "hvsc" if CONFIG.get("hvsc", {}).get("enabled", False) else "asma"

# ── ModArchive Collection (FastTracker / MOD / XM / S3M / IT) ──────
MODARCHIVE_BASE = CONFIG.get("modarchive", {}).get("base_url", "https://modarchive.org/index.php")
MODARCHIVE_DOWNLOAD = CONFIG.get("modarchive", {}).get("download_url", "https://api.modarchive.org/downloads.php")
MODARCHIVE_CACHE_FILE = os.path.join(
    _ROOT,
    CONFIG.get("modarchive", {}).get("cache_file", "modarchive_cache.json")
)
modarchive_name_map: dict[str, str] = {}  # URL -> real module name

CROSSFADE_SECS = CONFIG["playback"].get("crossfade", 0)
AUTO_START_CHANNEL = CONFIG["auto"].get("start_channel", "")
AUTO_EMPTY_TIMEOUT = CONFIG["auto"].get("empty_timeout", 60)

# ── Single-server lock ──────────────────────────────────────────
GUILD_ID = CONFIG.get("guild_id")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Remove default help, we provide a custom one
bot.remove_command("help")


@bot.check
def single_guild_check(ctx: commands.Context) -> bool:
    """If GUILD_ID is set, only allow commands from that guild."""
    if GUILD_ID and ctx.guild and ctx.guild.id != GUILD_ID:
        return False
    return True

# ── Permission helper: only server admins / bot owner can run destructive commands
def mod_only():
    """Check if user has Manage Channels permission or is bot owner."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author == ctx.bot.owner:
            return True
        if hasattr(ctx.author, "guild_permissions") and ctx.author.guild_permissions.manage_channels:
            return True
        raise commands.MissingPermissions(["manage_channels"])
    return commands.check(predicate)

active_streams: dict[int, "MonitorAudioSource"] = {}

_source_counter: int = 0

def _next_source_id() -> int:
    """Monotonic counter for source identity — never reuses numbers."""
    global _source_counter
    _source_counter += 1
    return _source_counter

def _after_stream_end(guild_id: int | None, error: Exception | None, source_id: int = 0) -> None:
    """Cleanup callback for vc.play() — logs, kills FFmpeg, removes from active_streams.
    Uses source_id to ensure stale callbacks don't clean up a newer source."""
    log.info("Stream ended for guild %s: %s", guild_id, error)
    if guild_id is not None:
        current = active_streams.get(guild_id)
        if current is not None and id(current) == source_id:
            active_streams.pop(guild_id, None)
            current.cleanup()
        elif current is not None and source_id:
            log.debug("Stale _after_stream_end for guild %s — current source differs, ignoring", guild_id)

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
        self.pre_downloaded_url: str | None = None  # URL the pre-download was for
        self.search_results: list[str] = []     # last search results
        self.monitor_task: asyncio.Task | None = None

        # Subsong support — module files (S3M/XM/IT/MOD) with multiple sub-songs
        self.subsong_current: int = -1   # -1 = not in subsong mode, 0+ = current subsong index
        self.subsong_total: int = 0       # total subsongs including main (0 = none/unknown)
        self.subsong_path: str | None = None  # path to original module file
        self.subsong_wavs: list[str] = [] # temp WAV paths for all subsongs ("" = not yet converted)


guilds: dict[int, PlaylistState] = {}

# Track message IDs → track info for reaction-based favorites
message_track_map: dict[int, dict] = {}
MESSAGE_TRACK_MAP_MAX = 50  # prune old entries to prevent unbounded growth


def _prune_message_track_map():
    """Keep only the most recent MESSAGE_TRACK_MAP_MAX entries."""
    if len(message_track_map) <= MESSAGE_TRACK_MAP_MAX:
        return
    # Sort by timestamp, keep newest
    sorted_ids = sorted(message_track_map.items(),
                        key=lambda x: x[1].get("timestamp", 0), reverse=True)
    keep = dict(sorted_ids[:MESSAGE_TRACK_MAP_MAX])
    message_track_map.clear()
    message_track_map.update(keep)


def _register_np_message(msg_id: int, url: str, name: str, author: str) -> None:
    """Register a Now Playing message for reaction-based favorites.
    Replaces 8× copy-pasted blocks across all play_current_* functions."""
    message_track_map[msg_id] = {
        "url": url,
        "name": name,
        "author": author,
        "timestamp": time.time(),
    }
    _prune_message_track_map()


def get_state(guild_id: int) -> PlaylistState:
    if guild_id not in guilds:
        guilds[guild_id] = PlaylistState()
    return guilds[guild_id]

def save_queue(state: PlaylistState):
    """Persist queue to disk for this guild (atomic)."""
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
    _atomic_json_write(path, data)

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

    MAX_RESTARTS = 5
    RESTART_COOLDOWN = 1.0

    def __init__(self, sink_name: str):
        self.buffer = b""
        self.sink_name = sink_name
        self.process = self._start_ffmpeg()
        self._restart_count = 0
        self._last_restart_ts = 0.0
        self._ever_produced = False

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
                if self._restart_count >= self.MAX_RESTARTS:
                    log.warning("MonitorAudioSource: max restarts (%d) reached, ending stream",
                                self.MAX_RESTARTS)
                    return b""
                if time.time() - self._last_restart_ts < self.RESTART_COOLDOWN:
                    time.sleep(0.05)
                    continue
                self._last_restart_ts = time.time()
                self._restart_count += 1
                time.sleep(0.1)
                self._restart_ffmpeg()
            chunk = self.process.stdout.read(4096)
            if not chunk:
                return b""
            self.buffer += chunk
            self._ever_produced = True
            self._restart_count = 0
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


def _setup_monitor_source(state: PlaylistState) -> None:
    """Stop old source and create a fresh MonitorAudioSource for the current voice client.
    Replaces 7× copy-pasted blocks across all play_current_* functions."""
    if state.vc and state.vc.is_connected():
        state.vc.stop()
        old_source = active_streams.pop(state.guild_id, None)
        if old_source:
            old_source.cleanup()
        source = MonitorAudioSource(SINK_NAME)
        state.vc.play(
            source,
            after=lambda e, sid=_next_source_id(): _after_stream_end(state.guild_id, e, sid),
        )
        active_streams[state.guild_id] = source


async def _cancel_monitor(state: PlaylistState) -> None:
    """Cancel the current monitor task and await its cleanup.
    Replaces 8× copy-pasted blocks across all collection switch commands."""
    if state.monitor_task and not state.monitor_task.done():
        state.monitor_task.cancel()
        try:
            await state.monitor_task
        except (asyncio.CancelledError, Exception):
            pass


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

_audacious_ready = False

def ensure_audacious():
    global _audacious_ready
    if _audacious_ready:
        # Fast path: verify audacious is alive AND audtool can talk to it
        r = subprocess.run(["pgrep", "-x", "audacious"], capture_output=True)
        if r.returncode == 0:
            r2 = subprocess.run(["audtool", "version"], capture_output=True, timeout=2)
            if r2.returncode == 0:
                return
            # Audacious process exists but D-Bus is dead — restart it
            log.warning("Audacious process alive but audtool unresponsive — restarting")
            subprocess.run(["pkill", "-x", "audacious"], capture_output=True)
        _audacious_ready = False
    subprocess.Popen(
        ["audacious", "--headless"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for D-Bus to be ready (audtool can take 5-10s to connect)
    for _ in range(20):
        r = subprocess.run(["audtool", "version"], capture_output=True, timeout=2)
        if r.returncode == 0:
            _audacious_ready = True
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
    "ym": 100,         # YM normalnie
    "tiny": 100,       # Tiny normalnie
    "spc": 100,        # SPC normalnie
}

def set_volume_for_collection(mode: str):
    """Set playback volume based on collection for consistent loudness."""
    vol = COLLECTION_VOLUMES.get(mode, 100)
    subprocess.run(["pactl", "set-sink-volume", "asma_bot", f"{vol}%"], capture_output=True)
    log.info("Volume set to %d%% for collection %s", vol, mode)


def move_playback_to_sink():
    """Move all Audacious sink inputs to the bot's PulseAudio sink in one shot."""
    subprocess.run(
        f"pactl list sink-inputs short | cut -d' ' -f1 | "
        f"while read id; do pactl move-sink-input \"$id\" {SINK_NAME}; done",
        shell=True, capture_output=True,
    )


# ── YM → WAV Converter (Atari ST YM2149) ───────────────────────
YM_FORMATS = (".ym", ".YM")
YM_CACHE_MAX_SIZE = 200 * 1024 * 1024  # 200MB max cache for decoded WAVs
YM_CACHE_MAX_ENTRIES = 50  # max number of cached YM dirs


def _ym_cache_enforce_limits():
    """Evict oldest entries from YM WAV cache if over size/count limits."""
    if not os.path.isdir(YM_TEMP_DIR):
        return
    entries = []
    for name in os.listdir(YM_TEMP_DIR):
        d = os.path.join(YM_TEMP_DIR, name)
        if os.path.isdir(d):
            try:
                mtime = os.path.getmtime(d)
                size = sum(os.path.getsize(os.path.join(d, f))
                           for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))
                entries.append((mtime, size, d))
            except OSError:
                pass
    entries.sort(key=lambda x: x[0])  # oldest first
    total_size = sum(e[1] for e in entries)
    while entries and (total_size > YM_CACHE_MAX_SIZE or len(entries) > YM_CACHE_MAX_ENTRIES):
        mtime, size, d = entries.pop(0)
        shutil.rmtree(d, ignore_errors=True)
        total_size -= size
        log.info("YM cache LRU evict: %s (%dKB)", os.path.basename(d), size // 1024)


def ym_to_wav(ym_path: str) -> str:
    """Convert an LHa-compressed .ym file to .wav for Audacious playback.

    Uses 7z to extract the raw YM from the LHa archive, then ym2wav (from
    stymulator package, via ST-Sound library) to decode to 48kHz WAV.

    Returns path to the generated WAV file.
    """
    os.makedirs(YM_TEMP_DIR, exist_ok=True)

    # Create a safe unique directory from the input path hash
    h = md5(ym_path.encode()).hexdigest()[:12]
    work_dir = os.path.join(YM_TEMP_DIR, h)
    os.makedirs(work_dir, exist_ok=True)

    wav_path = os.path.join(work_dir, "decoded.wav")

    # Return cached WAV if it already exists
    if os.path.exists(wav_path):
        return wav_path

    # Step 1: Extract LHa archive
    extract_ok = False
    try:
        r = subprocess.run(
            ["7z", "x", "-y", ym_path, f"-o{work_dir}"],
            capture_output=True, timeout=15
        )
        if r.returncode == 0:
            extract_ok = True
    except Exception:
        pass

    if not extract_ok:
        # Maybe it's not an LHa archive — try raw YM directly
        raw_ym = ym_path
    else:
        # Find the extracted .YM file
        raw_candidates = [f for f in os.listdir(work_dir)
                          if f.upper().endswith(".YM")]
        if raw_candidates:
            raw_ym = os.path.join(work_dir, raw_candidates[0])
        else:
            # No YM found — maybe it's a non-archive file, try original
            raw_ym = ym_path

    # Step 2: Convert YM to WAV
    log.info("YM→WAV: converting %s -> %s", os.path.basename(raw_ym), wav_path)
    r = subprocess.run(
        ["ym2wav", raw_ym, wav_path],
        capture_output=True, timeout=300, text=True
    )
    for line in r.stdout.splitlines():
        log.info("ym2wav: %s", line)
    for line in r.stderr.splitlines():
        log.warning("ym2wav err: %s", line)

    if r.returncode != 0 or not os.path.exists(wav_path):
        raise RuntimeError(f"ym2wav failed (exit={r.returncode}) for {ym_path}")

    wav_size = os.path.getsize(wav_path)
    log.info("YM→WAV: done — %d bytes -> %d bytes", os.path.getsize(ym_path), wav_size)
    _ym_cache_enforce_limits()
    return wav_path


def ym_cleanup():
    """Remove all previously decoded YM WAV files to free space."""
    global _ym_last_wav_path
    if _ym_last_wav_path and os.path.exists(_ym_last_wav_path):
        try:
            parent = os.path.dirname(_ym_last_wav_path)
            os.remove(_ym_last_wav_path)
            # Also remove the raw extracted YM if it exists
            for f in os.listdir(parent):
                fp = os.path.join(parent, f)
                if f != os.path.basename(_ym_last_wav_path):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
            log.info("YM cleanup: removed %s", parent)
        except Exception as e:
            log.warning("YM cleanup error: %s", e)
    _ym_last_wav_path = None

def resolve_local_path(url: str) -> str | None:
    """Map remote URL to local file path if available. Returns None if not found."""
    # ASMA: https://asma.atari.org/asma/Composers/... → archiwum/asma/Composers/...
    if url.startswith(ASMA_BASE):
        rel = url[len(ASMA_BASE):]
        local = os.path.join(ASMA_DIR, rel)
        if os.path.exists(local):
            log.info("Local ASMA path: %s", local)
            return local
    # HVSC: https://www.hvsc.c64.org/download/C64Music/... → archiwum/hvsc/C64Music/...
    if url.startswith(HVSC_BASE):
        rel = url[len(HVSC_BASE):]
        local = os.path.join(HVSC_DIR, rel)
        if os.path.exists(local):
            log.info("Local HVSC path: %s", local)
            return local
    return None


async def download_sap(url: str, retries: int = 2) -> str:
    filepath = build_temp_path(url)
    last_err = None
    session = await get_shared_session()
    for attempt in range(retries + 1):
        try:
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
SAP_LINE_RE = re.compile(rb'^([A-Z]+)\s+(.+)')

def parse_sap_header(filepath: str) -> dict[str, str]:
    """Parse SAP file header for metadata (AUTHOR, NAME, etc.).

    Handles both:
      AUTHOR "Pawel Grabowski"   (standard SAP, no semicolon)
      ; AUTHOR: Pawel Grabowski  (comment-style fallback)
    """
    meta = {}
    try:
        with open(filepath, "rb") as f:
            header = f.read(4096)
        for raw_line in header.split(b"\n"):
            line = raw_line.strip()
            if not line:
                continue
            # Skip opening SAP marker
            if line == b"SAP":
                continue
            # Strip leading ; if present (comment-style fallback)
            if line.startswith(b";"):
                line = line[1:].strip()
            # Match KEY VALUE pattern
            m = SAP_LINE_RE.match(line)
            if not m:
                continue
            key = m.group(1).decode("ascii", errors="replace").strip().upper()
            val_raw = m.group(2).decode("ascii", errors="replace").strip()
            # Strip surrounding quotes if present
            val = val_raw.strip("\"'")
            meta[key] = val
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
    for ext in [".sap", ".sid", ".mod", ".xm", ".s3m", ".it", ".ym"]:
        name_part = name_part.replace(ext, "")
    return name_part.replace("_", " ").lower()

# ── Metadata Index ──────────────────────────────────────────────
metadata_index: dict[str, dict[str, str]] = {}  # url -> {author, name, ...}
METADATA_CACHE = os.path.join(_ROOT, "metadata_cache.json")

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
    # Save once after all batches (was: saving inside loop = N writes)
    if metadata_index:
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
            for raw_line in data.split(b"\n"):
                line = raw_line.strip()
                if not line or line == b"SAP":
                    continue
                if line.startswith(b";"):
                    line = line[1:].strip()
                m = SAP_LINE_RE.match(line)
                if not m:
                    continue
                key = m.group(1).decode("ascii", errors="replace").strip().upper()
                val_raw = m.group(2).decode("ascii", errors="replace").strip()
                val = val_raw.strip("\"'")
                meta[key] = val
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
    """Crawl all top-level ASMA directories and return every .sap URL.
    Uses cached tracklist first — only re-crawls if cache is stale or missing."""
    # Try cache first
    cached = load_cached_tracklist()
    if cached:
        log.info("ASMA: loaded %d tracks from cache", len(cached))
        return cached
    log.info("ASMA: cache stale or missing, crawling...")
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
        state.pre_downloaded_url = url
    except Exception:
        state.pre_downloaded = None
        state.pre_downloaded_url = None


async def play_current_sid_track(ctx, state, url):
    """Download and play a SID track via Audacious."""
    # Try local path first
    local_path = resolve_local_path(url)
    if local_path:
        sid_path = local_path
        with open(sid_path, "rb") as f:
            data = f.read()
    else:
        # Download full SID to temp (they're small, ~5-15KB)
        sid_path = build_temp_path(url)
        try:
            session = await get_shared_session()
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

    _setup_monitor_source(state)

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

    _register_np_message(np_msg.id, url, name, author)
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

    _setup_monitor_source(state)

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

    _register_np_message(np_msg.id, url, display_name, "")
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
    "ym": {
        "icon": "🎹",
        "name": "Atari ST YM (Local Archive)",
        "station": "Atari ST YM Radio",
        "footer": "Atari ST YM Radio — YM2149 chiptunes",
        "color": discord.Color.from_str("#F1C40F"),
        "load_tracks": lambda: load_ym_cache(),
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

    _setup_monitor_source(state)

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
    _register_np_message(np_msg.id, filepath, name, author)
    log.info("AY now playing: %s — %s", name, author)
    return True


async def play_current_ym_track(ctx, state, filepath):
    """Play a local YM file (Atari ST YM2149) via YM→WAV conversion + Audacious."""
    full_path = os.path.join(YM_DIR, filepath)

    if not os.path.exists(full_path):
        await ctx.send(f"❌ File not found: `{filepath}`")
        return False

    # Clean up previous YM WAV
    await asyncio.get_event_loop().run_in_executor(None, ym_cleanup)

    # Convert YM to WAV (extracts LHa, decodes YM2149 registers to PCM)
    try:
        wav_path = await asyncio.get_event_loop().run_in_executor(None, ym_to_wav, full_path)
    except Exception as e:
        log.error("YM→WAV conversion failed: %s", e)
        await ctx.send(f"❌ Failed to decode YM file: `{filepath}`")
        return False

    global _ym_last_wav_path
    _ym_last_wav_path = wav_path

    # Stop old Audacious and play the WAV
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    await asyncio.get_event_loop().run_in_executor(None, audacious_play, wav_path)

    state.current_sap_path = full_path

    _setup_monitor_source(state)

    total = len(state.queue)
    pos = state.index + 1

    # Extract name from filepath (ym2wav gives real title but we can't await its output here)
    name = filepath.split("/")[-1].replace(".ym", "").replace(".YM", "")
    author = ""

    embed = discord.Embed(
        title=name[:256],
        color=discord.Color.from_str("#F1C40F"),
    )
    if author:
        embed.add_field(name="Composer", value=author, inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    embed.set_footer(text="Atari ST YM2149 — decoded via ST-Sound + Audacious")

    np_msg = await ctx.send(embed=embed)
    _register_np_message(np_msg.id, filepath, name, author)
    log.info("YM now playing: %s — %s", name, author)
    return True


async def play_current_tiny_track(ctx, state, filepath):
    """Play a local Tiny Music module via Audacious."""
    full_path = os.path.join(TINY_DIR, filepath)

    if not os.path.exists(full_path):
        await ctx.send(f"❌ File not found: `{filepath}`")
        return False

    # Clean up any previous subsong temp files
    _cleanup_subsong_temp_wavs(state)

    # ── Subsong detection ──
    subsongs = _get_subsongs(full_path)
    has_multi = len(subsongs) > 1
    if has_multi:
        state.subsong_total = len(subsongs)
        state.subsong_current = 0
        state.subsong_path = full_path
        log.info("Subsong: %s has %d sub-songs (main=%.1fs, extra=%d)",
                 os.path.basename(full_path), len(subsongs), subsongs[0], len(subsongs) - 1)
    else:
        _cleanup_subsong_temp_wavs(state)

    # Stop existing playback and play via Audacious (subsong 0 plays natively)
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    await asyncio.get_event_loop().run_in_executor(None, audacious_play, full_path)

    state.current_sap_path = full_path

    _setup_monitor_source(state)

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
    if has_multi:
        embed.set_footer(text=f"Tiny Music — curated demoscene modules · {len(subsongs)} parts")
    else:
        embed.set_footer(text="Tiny Music — curated demoscene modules")

    np_msg = await ctx.send(embed=embed)
    _register_np_message(np_msg.id, filepath, name, author)
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

        # ── Local YM Archive (Atari ST) ──
        is_ym = url.endswith(".ym")
        if is_ym:
            if state.collection_mode != "ym":
                state.collection_mode = "ym"
                await ensure_tracks(state)
            return await play_current_ym_track(ctx, state, url)

        # ── ASMA SAP Playback (default) ──
        if state.collection_mode != "asma":
            state.collection_mode = "asma"
            await ensure_tracks(state)
        # Try local path first, then pre-downloaded, then download now
        local_path = resolve_local_path(url)
        if local_path:
            filepath = local_path
            state.pre_downloaded = None
            state.pre_downloaded_url = None
        elif state.pre_downloaded and state.pre_downloaded_url == url and os.path.exists(state.pre_downloaded):
            filepath = state.pre_downloaded
            state.pre_downloaded = None
            state.pre_downloaded_url = None
        else:
            state.pre_downloaded = None
            state.pre_downloaded_url = None
            filepath = await download_sap(url)
        await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
        await asyncio.get_event_loop().run_in_executor(None, audacious_play, filepath)
        
        state.current_sap_path = filepath
        
        _setup_monitor_source(state)

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
        _register_np_message(np_msg.id, url, name, author)
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

    # ── Subsong: more parts of current module? ──
    if state.subsong_total > 0 and state.subsong_path:
        next_sub = state.subsong_current + 1
        if next_sub < state.subsong_total:
            log.info("Subsong: advancing to part %d/%d of %s",
                     next_sub + 1, state.subsong_total,
                     os.path.basename(state.subsong_path))
            ok = await play_subsong(ctx, state, next_sub)
            if ok:
                # Send updated embed for this part
                name = os.path.basename(state.subsong_path).rsplit('.', 1)[0]
                total = len(state.queue)
                pos = state.index + 1
                embed = discord.Embed(
                    title=f"{name} (part {next_sub + 1}/{state.subsong_total})",
                    color=discord.Color.purple(),
                )
                embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
                embed.set_footer(text=f"Tiny Music — curated demoscene modules · {state.subsong_total} parts")
                np_msg = await ctx.send(embed=embed)
                _register_np_message(np_msg.id, state.subsong_path, name, "")
                return
            else:
                # Conversion failed — fall through to next queue item
                log.error("Subsong %d conversion failed, skipping to next queue item", next_sub)
                _cleanup_subsong_temp_wavs(state)
        else:
            # All subsongs done
            _cleanup_subsong_temp_wavs(state)

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
        if (saved and saved.get("queue") and len(saved["queue"]) >= 10
                and saved["queue"][0] in state.tracks
                and saved.get("collection_mode") == state.collection_mode):
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
        state.pre_downloaded = None  # clear stale
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
            state.pre_downloaded = None  # clear stale
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
    state.pre_downloaded = None  # clear stale
    
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
@mod_only()
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
    _register_np_message(np_msg.id, state.queue[state.index] if state.queue and 0 <= state.index < len(state.queue) else "unknown", name, author)
    return


@bot.command()
async def volume(ctx: commands.Context, *, level: str = ""):
    """Set or show playback volume (0-200%). Usage: !volume <level>"""
    if not level:
        r = await asyncio.get_event_loop().run_in_executor(
            None, lambda: subprocess.run(["pactl", "get-sink-volume", "asma_bot"], capture_output=True, text=True)
        )
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
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: subprocess.run(["pactl", "set-sink-volume", "asma_bot", f"{vol}%"], capture_output=True)
        )
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
@mod_only()
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
    owl = random.choice(owls)
    await ctx.send(f"```\n{owl}\n```")


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    """Show all commands and collections. Usage: !help"""
    embed = discord.Embed(
        title="🤖 Robbo Obibok — Help",
        description="Seven collections, one bot — **the biggest chiptune radio on Discord.**\n"
                    "Join a voice channel and `!play`!",
        color=discord.Color.from_str("#2ECC71"),
    )

    embed.add_field(
        name="🎮 Playback",
        value=(
            "`!play` / `!radio` / `!start` / `!pl` — start shuffled radio\n"
            "`!stop` / `!st` — stop & disconnect\n"
            "`!skip` / `!next` / `!nt` — next track\n"
            "`!jump <n>` — jump to track N\n"
            "`!np` — now playing\n"
            "`!queue` / `!q` — show queue\n"
            "`!history` — last 10 tracks\n"
            "`!sleep <min>` — stop after N minutes\n"
            "`!loop` / `!repeat` — toggle loop\n"
            "`!volume <0-200>` — set volume\n"
            "`!clear` — clear queue"
        ),
        inline=False,
    )

    embed.add_field(
        name="🎵 Collections",
        value=(
            "`!asma`  — 🟢 Atari SAP (~6 300)\n"
            "`!hvsc` / `!c64` / `!sid` — 🟣 C64 SID (~60 500)\n"
            "`!mod` / `!modarchive` / `!tracker` / `!modules` — 🟠 Tracker Modules (~175 000)\n"
            "`!ay` / `!zx` / `!zxspectrum` / `!spectrum` — 🔵 ZX Spectrum AY (~4 500)\n"
            "`!ym` / `!atarist` / `!ym2149` — 🎹 **Atari ST YM (~7 200)**\n"
            "`!tiny` / `!tm` / `!demoscene` — 🎵 Demoscene Modules (~418)\n"
            "`!snes` / `!spc` / `!supernintendo` / `!nintendo` — 🔴 SNES SPC (~60 000)"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔄 Navigation",
        value=(
            "`!flip` / `!switch` / `!toggle` / `!fl` — cycle through all collections\n"
            "`!status` / `!mode` / `!collection` / `!all` — show all collections & current mode\n"
            "`!search <query>` — search across current collection\n"
            "`!snes search <term>` — search SNES by game/composer"
        ),
        inline=False,
    )

    embed.add_field(
        name="❤️ Favorites & Blacklist",
        value=(
            "React to any **Now Playing** embed to save/remove favorites\n"
            "`!favplay` / `!fp` — play favorites\n"
            "`!favsave` / `!pls` — save favorites as playlist\n"
            "`!favload` / `!fpl` — load & play a playlist\n"
            "`!favorites` / `!favs` — list favorites\n"
            "`!playlists` / `!plist` / `!list-playlists` / `!playlist-dir` — list saved playlists\n"
            "`!blk` — blacklist current track\n"
            "`!blks` / `!blklist` — show blacklist\n"
            "`!blkrm <n>` — remove track from blacklist"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔧 Tools & Info",
        value=(
            "`!stats` — radio stats (tracks, queue, playing)\n"
            "`!export` — export queue as text\n"
            "`!ocko` — 🦉 random ASCII owl\n"
            "`!refresh` — re-crawl ASMA archive *(mod only)*\n"
            "`!reindex` — re-fetch metadata *(mod only)*"
        ),
        inline=False,
    )

    embed.set_footer(text="Made with 🔥 by the forest spirit")

    await ctx.send(embed=embed)


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
@mod_only()
@commands.cooldown(1, 300, commands.BucketType.guild)
async def refresh(ctx: commands.Context):
    """Re-crawl ASMA and rebuild the playlist."""
    await ctx.send("🔍 Re-crawling ASMA archive... this may take a minute.")
    tracks = await refresh_tracklist()
    state = get_state(ctx.guild.id)
    state.tracks = tracks
    await ctx.send(f"✅ Refreshed! Found **{len(tracks)}** tracks.")


@bot.command()
@mod_only()
@commands.cooldown(1, 300, commands.BucketType.guild)
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
_favorites_cache = None
_favorites_mtime = None

def load_favorites() -> dict:
    """Load the favorites database from disk, with in-memory caching (mtime invalidation)."""
    global _favorites_cache, _favorites_mtime
    try:
        mtime = os.path.getmtime(FAVORITES_FILE)
    except OSError:
        return {}
    if _favorites_cache is not None and mtime == _favorites_mtime:
        return _favorites_cache
    try:
        with open(FAVORITES_FILE) as f:
            data = json.load(f)
            _favorites_cache = data
            _favorites_mtime = mtime
            return data
    except Exception:
        return {}


def save_favorites(data: dict):
    """Save the favorites database to disk (atomic) and update cache."""
    global _favorites_cache, _favorites_mtime
    _atomic_json_write(FAVORITES_FILE, data)
    _favorites_cache = data
    try:
        _favorites_mtime = os.path.getmtime(FAVORITES_FILE)
    except OSError:
        pass


# ── Named Playlists ──────────────────────────────────────────────

def _ensure_playlist_dir():
    """Create playlists directory if it doesn't exist."""
    try:
        os.makedirs(PLAYLIST_DIR, exist_ok=True)
    except Exception as e:
        log.error("Failed to create playlists dir: %s", e)

def _sanitize_playlist_name(name: str) -> str:
    """Sanitize a playlist name to a safe filename."""
    safe = "".join(c if c.isalnum() or c in " _-." else "_" for c in name)
    return safe.strip().strip(".") or "unnamed"

def save_playlist(name: str, tracks: list[dict], author_id: int, author_name: str) -> str:
    """Save a named playlist file. Returns the filename used."""
    _ensure_playlist_dir()
    safe_name = _sanitize_playlist_name(name)
    filename = f"{safe_name}.json"
    path = os.path.join(PLAYLIST_DIR, filename)
    data = {
        "name": name,
        "author": author_name,
        "author_id": author_id,
        "created": time.time(),
        "tracks": tracks,
    }
    _atomic_json_write(path, data)
    return safe_name

def load_playlist(name: str) -> dict | None:
    """Load a named playlist. Returns None if not found."""
    safe_name = _sanitize_playlist_name(name)
    for ext in ("", ".json"):
        path = os.path.join(PLAYLIST_DIR, f"{safe_name}{ext}")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception as e:
                log.error("Failed to load playlist '%s': %s", name, e)
                return None
    return None

def list_playlists() -> list[dict]:
    """List all saved playlists (name + track count)."""
    _ensure_playlist_dir()
    playlists = []
    for fname in sorted(os.listdir(PLAYLIST_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(PLAYLIST_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            playlists.append({
                "name": data.get("name", fname[:-5]),
                "author": data.get("author", "?"),
                "tracks": len(data.get("tracks", [])),
                "created": data.get("created", 0),
            })
        except Exception:
            playlists.append({
                "name": fname[:-5],
                "author": "?",
                "tracks": 0,
                "created": 0,
            })
    return playlists


# ── Blacklist System ────────────────────────────────────────────
_blacklist_cache: dict | None = None
_blacklist_mtime: float = 0

def load_blacklist() -> dict:
    """Load the blacklist database from disk, with in-memory caching."""
    global _blacklist_cache, _blacklist_mtime
    try:
        mtime = os.path.getmtime(BLACKLIST_FILE)
    except OSError:
        return {}
    if _blacklist_cache is not None and mtime == _blacklist_mtime:
        return _blacklist_cache
    try:
        with open(BLACKLIST_FILE) as f:
            data = json.load(f)
            _blacklist_cache = data
            _blacklist_mtime = mtime
            return data
    except Exception:
        return {}


def save_blacklist(data: dict):
    """Save the blacklist database to disk (atomic) and update cache."""
    global _blacklist_cache
    _atomic_json_write(BLACKLIST_FILE, data)
    _blacklist_cache = data
    try:
        global _blacklist_mtime
        _blacklist_mtime = os.path.getmtime(BLACKLIST_FILE)
    except OSError:
        pass


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

    await _play_track_list(ctx, tracks_to_play, "favorites")


# ── Playlist Commands ────────────────────────────────────────────

async def _play_track_list(ctx, tracks: list[dict], label: str) -> bool:
    """Shared helper: connect to voice and play a list of track dicts.
    Used by !favplay and !favload."""
    state = get_state(ctx.guild.id)
    first_url = tracks[0]["url"]

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
    state.pre_downloaded = None  # clear stale pre-download from previous session

    # Build queue from URLs
    state.queue = [t["url"] for t in tracks]
    state.index = 0

    await ctx.send(f"🎵 **Playing {len(tracks)} {label}!**")

    if await play_current_track(ctx):
        save_queue(state)
        if state.monitor_task and not state.monitor_task.done():
            state.monitor_task.cancel()
        state.monitor_task = bot.loop.create_task(monitor_playback(ctx, vc, ctx.guild.id))
    return True


@bot.command(aliases=["pls"])
async def favsave(ctx: commands.Context, *, name: str):
    """Save your favorites as a named playlist. Usage: !favsave <name>"""
    favs = load_favorites()
    user_favs = favs.get(str(ctx.author.id), {}).get("tracks", [])

    if not user_favs:
        return await ctx.send("📭 **No favorites to save.** React to a Now Playing embed with any emoji to add tracks first!")

    safe_name = save_playlist(name.strip(), user_favs, ctx.author.id, str(ctx.author))
    if not safe_name:
        return await ctx.send("❌ Failed to save playlist.")

    await ctx.send(f"💾 **Saved!** `{safe_name}` — {len(user_favs)} tracks from your favorites.")


@bot.command(aliases=["fpl"])
async def favload(ctx: commands.Context, *, name: str):
    """Load and play a saved playlist. Usage: !favload <name> or !favload list"""
    if name.strip().lower() == "list":
        playlists = list_playlists()
        if not playlists:
            return await ctx.send("📂 **No playlists saved yet.** Use `!favsave <name>` to create one!")
        lines = ["📂 **Saved Playlists**"]
        for p in playlists:
            author_s = f" by {p['author']}" if p['author'] != "?" else ""
            lines.append(f"`{p['name']}` — {p['tracks']} tracks{author_s}")
        return await ctx.send("\n".join(lines))

    if not ctx.author.voice:
        return await ctx.send("Join a voice channel first!")

    playlist = load_playlist(name.strip())
    if not playlist:
        return await ctx.send(f"❌ Playlist `{name.strip()}` not found. Use `!favload list` to see saved playlists.")

    tracks = playlist.get("tracks", [])
    if not tracks:
        return await ctx.send(f"📭 Playlist `{playlist['name']}` is empty!")

    await _play_track_list(ctx, tracks, f"playlist \"{playlist['name']}\"")


@bot.command(aliases=["plist", "list-playlists", "playlist-dir"])
async def playlists(ctx: commands.Context):
    """List all saved playlists in the playlists directory. Usage: !playlists"""
    _ensure_playlist_dir()
    files = sorted(os.listdir(PLAYLIST_DIR))
    json_files = [f for f in files if f.endswith(".json")]

    if not json_files:
        return await ctx.send("📂 **No playlists saved yet.** Use `!favsave <name>` to create one!")

    lines = ["📂 **Playlists Directory**"]

    for fname in json_files:
        path = os.path.join(PLAYLIST_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            display_name = data.get("name", fname[:-5])
            author = data.get("author", "?")
            tracks = len(data.get("tracks", []))
            created = data.get("created", 0)
            if created:
                created_str = time.strftime("%Y-%m-%d", time.localtime(created))
            else:
                created_str = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
            author_s = f" by {author}" if author and author != "?" else ""
            lines.append(f"`{display_name}` — {tracks} tracks{author_s} ({created_str})")
        except Exception as e:
            # Fallback: show raw filename with file info
            size = os.path.getsize(path)
            mtime = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
            lines.append(f"`{fname}` — {size} bytes ({mtime}) — ⚠️ parse error")

    # Split into chunks if too long (Discord 2000 char limit)
    msg = "\n".join(lines)
    if len(msg) <= 2000:
        await ctx.send(msg)
    else:
        # Send in chunks
        for i in range(0, len(lines), 10):
            chunk = "\n".join(lines[i:i+10])
            await ctx.send(chunk)


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


def _load_json_cache(cache_path: str) -> dict | list | None:
    """Load a JSON cache file. Returns parsed data or None on error."""
    try:
        if not os.path.exists(cache_path):
            return None
        with open(cache_path) as f:
            return json.load(f)
    except Exception as e:
        log.warning("Cache load error (%s): %s", os.path.basename(cache_path), e)
        return None


def _load_path_cache(cache_path: str, label: str) -> list[str] | None:
    """Load a track list from cache where each entry has a 'path' field.
    Used by AY, YM, Tiny — eliminates 3× duplicate file-I/O logic."""
    data = _load_json_cache(cache_path)
    if data is None:
        return None
    tracks = [t["path"] for t in data.get("tracks", [])]
    log.info("%s: loaded %d tracks from cache", label, len(tracks))
    return tracks


def load_ay_cache() -> list[str] | None:
    return _load_path_cache(AY_CACHE, "AY")


def load_ym_cache() -> list[str] | None:
    return _load_path_cache(YM_CACHE, "YM")


def load_tiny_cache() -> list[str] | None:
    return _load_path_cache(TINY_CACHE, "Tiny")


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
        session = await get_shared_session()
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

    _setup_monitor_source(state)

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
    _register_np_message(np_msg.id, game_entry["rsn_url"], game_name, ", ".join(composers) if composers else "Unknown")
    log.info("SNES now playing: %s — %s", game_name, ", ".join(composers) if composers else "?")
    return True


async def download_modarchive_module(url: str, retries: int = 2) -> str:
    """Download a module from ModArchive API and return local filepath.
    Preserves the real filename from Content-Disposition header."""
    last_err = None
    session = await get_shared_session()
    for attempt in range(retries + 1):
        try:
            filepath = build_temp_path(url)
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



def cleanup_orphan_players():
    """Kill orphaned audacious processes from crashed bot sessions.
    Scoped to current user — does not touch system-wide processes."""
    user = os.environ.get("USER", "") or os.environ.get("LOGNAME", "")
    subprocess.run(["pkill", "-u", user, "-x", "audacious"], capture_output=True)


def stop_all_players():
    """Stop Audacious playback and clear playlist for collection switch."""
    audacious_stop()
    # Cleanup any lingering subsong temp WAVs across all guilds
    for g_state in guilds.values():
        _cleanup_subsong_temp_wavs(g_state)


async def cleanup_hvsc_file(ctx, tracks):
    """Store the HVSC tracklist for search (no local copies yet)."""
    # Just let user know search won't have metadata until they use it
    pass


# ── Collection Switch Engine ──────────────────────────────────────
_COLLECTIONS = {
    "hvsc": {
        "label": "HVSC",
        "flip_tag": "🟣HVSC",
        "load_func": load_cached_hvsc,
        "fallback_func": download_hvsc_index,
        "already_msg": "📀 **Already in C64 SID mode.** Use `!play` to start!",
        "load_msg": "🔄 **Loading C64 SID collection (60,000+ tracks)...**",
        "flip_load_msg": "🔄 Loading C64 SID collection (60,000+ tracks)...",
        "error_msg": "❌ Failed to load HVSC index. Check config or try again.",
        "ready_msg": "📀 **C64 SID collection ready — {count} tracks!**",
        "flip_ready_msg": "🟣 **Switched to C64 SID (HVSC) — {count} tracks!**",
        "flip_fail_msg": "❌ Could not load HVSC. Try `!hvsc` manually.",
        "log_msg": "HVSC: collection switched, %d tracks loaded",
        "log_args": True,
        "after_hook": cleanup_hvsc_file,
        "allow_empty": False,
    },
    "asma": {
        "label": "ASMA",
        "flip_tag": "🟢ASMA",
        "load_func": load_cached_tracklist,
        "fallback_func": None,
        "already_msg": None,
        "load_msg": None,
        "error_msg": None,
        "ready_msg": "📀 **Switched to ASMA Atari SAP — {count} tracks!**",
        "ready_empty_msg": "📀 **Switched to ASMA Atari SAP.** Use `!play` to crawl the archive.",
        "flip_ready_msg": "🟢 **Switched to Atari SAP (ASMA)!**",
        "flip_ready_empty_msg": "🟢 **Switched to Atari SAP (ASMA).**",
        "log_msg": "ASMA: collection switched",
        "log_args": False,
        "after_hook": None,
        "allow_empty": True,
    },
    "modarchive": {
        "label": "ModArchive",
        "flip_tag": "🟠Mod",
        "load_func": load_modarchive_cache,
        "fallback_func": None,
        "already_msg": "🟠 **Already in ModArchive mode.** Use `!play` to start!",
        "load_msg": "🟠 **Loading ModArchive collection (100,000+ modules)...**",
        "error_msg": "❌ ModArchive cache not found. Run `build_modarchive_index.py` first!\n"
                     "The index builder is running in the background — wait a few minutes and try again.",
        "ready_msg": "🟠 **ModArchive collection ready — {count} modules!**\n"
                     "FastTracker / ProTracker / ScreamTracker / Impulse Tracker — all formats!",
        "flip_ready_msg": "🟠 **Switched to ModArchive — {count} modules!**",
        "flip_fail_msg": "🟠 **ModArchive cache not ready.** Staying on {prev}.",
        "log_msg": "ModArchive: collection switched, %d tracks loaded",
        "log_args": True,
        "after_hook": None,
        "allow_empty": False,
    },
    "ay": {
        "label": "AY",
        "flip_tag": "🔵AY",
        "load_func": load_ay_cache,
        "fallback_func": None,
        "already_msg": "🔵 **Already in ZX Spectrum AY mode.** Use `!play` to start!",
        "load_msg": "🔵 **Loading local AY archive (4,500+ tracks)...**",
        "error_msg": "❌ AY cache not found. Run `build_ay_index.py` first!",
        "ready_msg": "🔵 **ZX Spectrum AY archive ready — {count} tracks!**\n"
                     "AY-3-8910 chiptunes — AYGOR / Ironfist / Tr_Songs / SoLOCPC / Bulba",
        "flip_ready_msg": "🔵 **Switched to ZX Spectrum AY — {count} tracks!**",
        "flip_fail_msg": "🔵 **AY cache not ready.** Staying on {prev}.",
        "log_msg": "AY: collection switched, %d tracks loaded",
        "log_args": True,
        "after_hook": None,
        "allow_empty": False,
    },
    "ym": {
        "label": "YM",
        "flip_tag": "🎹YM",
        "load_func": load_ym_cache,
        "fallback_func": None,
        "already_msg": "🎹 **Already in Atari ST YM mode.** Use `!play` to start!",
        "load_msg": "🎹 **Loading local YM archive (7,200+ Atari ST chiptunes)...**",
        "error_msg": "❌ YM cache not found. Run `build_ym_index.py` first!",
        "ready_msg": "🎹 **Atari ST YM archive ready — {count} tracks!**\n"
                     "YM2149 chiptunes — Mad Max / Scavenger / Big Alec / David Whittaker / Jochen Hippel",
        "flip_ready_msg": "🎹 **Switched to Atari ST YM — {count} tracks!**",
        "flip_fail_msg": "🎹 **YM cache not ready.** Staying on {prev}.",
        "log_msg": "YM: collection switched, %d tracks loaded",
        "log_args": True,
        "after_hook": None,
        "allow_empty": False,
    },
    "tiny": {
        "label": "Tiny",
        "flip_tag": "🎵Tiny",
        "load_func": load_tiny_cache,
        "fallback_func": None,
        "already_msg": "🎵 **Already in Tiny Music mode.** Use `!play` to start!",
        "load_msg": "🎵 **Loading Tiny Music archive (418 curated demoscene modules)...**",
        "error_msg": "❌ Tiny Music cache not found. Run `build_tiny_index.py` first!",
        "ready_msg": "🎵 **Tiny Music archive ready — {count} modules!**\n"
                     "Curated demoscene — MOD / XM / IT / S3M / MED / DMF",
        "flip_ready_msg": "🎵 **Switched to Tiny Music — {count} modules!**",
        "flip_fail_msg": "🎵 **Tiny cache not ready.** Staying on {prev}.",
        "log_msg": "Tiny: collection switched, %d tracks loaded",
        "log_args": True,
        "after_hook": None,
        "allow_empty": False,
    },
    "spc": {
        "label": "SNES",
        "flip_tag": "🔴SNES",
        "load_func": load_snes_cache,
        "fallback_func": None,
        "already_msg": "🔴 **Already in SNES SPC mode.** Use `!play` to start!",
        "load_msg": "🔴 **Loading SNES SPC collection (Super Nintendo chiptunes)...**",
        "error_msg": "❌ SNES SPC cache not found. Run `build_snes_index.py` first!",
        "ready_msg": "🔴 **SNES SPC collection ready — {count} games!**\n"
                     "Super Nintendo chiptunes via SNESmusic.org — download & play on demand",
        "flip_ready_msg": "🔴 **Switched to SNES SPC — {count} games!**",
        "flip_fail_msg": "🔴 **SNES cache not ready.** Staying on {prev}.",
        "log_msg": "SNES: collection switched, %d game sets loaded",
        "log_args": True,
        "after_hook": None,
        "allow_empty": False,
    },
}

_FLIP_ORDER = ["hvsc", "asma", "modarchive", "ay", "ym", "tiny", "spc"]
_FLIP_SEQ = ["🟣HVSC", "🟢ASMA", "🟠Mod", "🔵AY", "🎹YM", "🎵Tiny", "🔴SNES"]


async def _switch_collection(ctx, mode, *, flip_seq=None):
    """Switch to a collection. Returns True on success, False on failure.

    When flip_seq is provided, operates in flip mode: no loading/already
    messages, shows flip-sequence visual, rolls back on failure.
    """
    state = get_state(ctx.guild.id)
    cfg = _COLLECTIONS[mode]

    # Already-in-mode check (skip during flip)
    if not flip_seq and cfg.get("already_msg") and state.collection_mode == mode and state.tracks:
        await ctx.send(cfg["already_msg"])
        return False

    # Loading message (not shown during flip)
    if not flip_seq and cfg.get("load_msg"):
        await ctx.send(cfg["load_msg"])

    await asyncio.get_event_loop().run_in_executor(None, stop_all_players)
    await _cancel_monitor(state)
    state.pre_downloaded = None
    state.pre_downloaded_url = None

    # Load tracks
    tracks = await asyncio.get_event_loop().run_in_executor(None, cfg["load_func"])
    if not tracks and cfg.get("fallback_func"):
        if flip_seq:
            seq = " → ".join("**" + s + "**" if s == cfg["flip_tag"] else s for s in flip_seq)
            await ctx.send(cfg.get("flip_load_msg", "") + f"\n{seq}")
        tracks = await asyncio.get_event_loop().run_in_executor(None, cfg["fallback_func"])

    if not tracks:
        if cfg.get("allow_empty"):
            # ASMA: empty cache is OK — user can !play to crawl
            state.collection_mode = mode
            save_last_collection(mode)
            await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, mode)
            state.tracks = []
            state.queue = []
            state.index = -1
            if flip_seq:
                seq = " → ".join("**" + s + "**" if s == cfg["flip_tag"] else s for s in flip_seq)
                await ctx.send(cfg.get("flip_ready_empty_msg", "") + f"\n{seq}")
            else:
                await ctx.send(cfg.get("ready_empty_msg", ""))
            log.info(cfg["log_msg"])
            await auto_play_after_switch(ctx, state)
            return True
        else:
            if flip_seq:
                seq = " → ".join("**" + s + "**" if s == cfg["flip_tag"] else s for s in flip_seq)
                prev_label = _COLLECTIONS.get(state.collection_mode, {}).get("label", "?")
                await ctx.send(cfg["flip_fail_msg"].format(prev=prev_label) + f"\n{seq}")
            else:
                await ctx.send(cfg["error_msg"])
            return False

    # Success
    state.collection_mode = mode
    save_last_collection(mode)
    await asyncio.get_event_loop().run_in_executor(None, set_volume_for_collection, mode)
    state.tracks = tracks
    state.queue = []
    state.index = -1

    if flip_seq:
        seq = " → ".join("**" + s + "**" if s == cfg["flip_tag"] else s for s in flip_seq)
        await ctx.send(cfg["flip_ready_msg"].format(count=len(tracks)) + f"\n{seq}")
    else:
        await ctx.send(cfg["ready_msg"].format(count=len(tracks)))

    if cfg.get("log_args", True):
        log.info(cfg["log_msg"], len(tracks))
    else:
        log.info(cfg["log_msg"])

    if cfg.get("after_hook"):
        await cfg["after_hook"](ctx, tracks)

    await auto_play_after_switch(ctx, state)
    return True


# ── Collection Commands ─────────────────────────────────────────
@bot.command(aliases=["c64", "sid"])
async def hvsc(ctx: commands.Context):
    """Switch to C64 SID collection (HVSC)."""
    await _switch_collection(ctx, "hvsc")


@bot.command()
async def asma(ctx: commands.Context):
    """Switch back to Atari SAP collection (ASMA)."""
    await _switch_collection(ctx, "asma")


@bot.command(aliases=["modarchive", "tracker", "modules"])
async def mod(ctx: commands.Context):
    """Switch to ModArchive collection (MOD/XM/S3M/IT modules)."""
    await _switch_collection(ctx, "modarchive")


@bot.command(aliases=["zx", "zxspectrum", "spectrum"])
async def ay(ctx: commands.Context):
    """Switch to local ZX Spectrum AY archive."""
    await _switch_collection(ctx, "ay")


@bot.command(aliases=["atarist", "ym2149"])
async def ym(ctx: commands.Context):
    """Switch to local Atari ST YM2149 archive."""
    await _switch_collection(ctx, "ym")


@bot.command(aliases=["tm", "demoscene"])
async def tiny(ctx: commands.Context):
    """Switch to local Tiny Music demoscene module archive."""
    await _switch_collection(ctx, "tiny")


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

    # ── Switch mode ──
    await _switch_collection(ctx, "spc")


_status_count_cache: dict[str, tuple[float, int | str]] = {}


def _get_cache_count(fname: str) -> int | str:
    """Get track count from a cache file, with mtime-based caching."""
    fpath = os.path.join(_ROOT, fname)
    try:
        mtime = os.path.getmtime(fpath)
    except OSError:
        return "⚠️"
    cached = _status_count_cache.get(fname)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(fpath) as f:
            data = json.load(f)
        if isinstance(data, list):
            count: int | str = len(data)
        elif isinstance(data, dict):
            count = data.get("total_sets") or len(data.get("tracks", data.get("count", [])))
        else:
            count = "?"
    except Exception:
        count = "⚠️"
    _status_count_cache[fname] = (mtime, count)
    return count


def _get_all_cache_counts(cache_map: dict) -> dict:
    """Read all cache counts in one batch (call via executor)."""
    result = {}
    for fname, (icon, label) in cache_map.items():
        result[label] = (icon, _get_cache_count(fname))
    return result


@bot.command(aliases=["mode", "collection", "all"])
async def status(ctx: commands.Context):
    """Show all collections overview and current playlist stats."""
    state = get_state(ctx.guild.id)

    # ── Cache counts (mtime-cached, offloaded to executor) ──
    cache_map = {
        "asma_cache.json": ("🟢", "Atari SAP (ASMA)"),
        "hvsc_cache.json": ("🟣", "C64 SID (HVSC)"),
        "modarchive_cache.json": ("🟠", "Tracker Modules (ModArchive)"),
        "ay_cache.json": ("🔵", "ZX Spectrum AY"),
        "ym_cache.json": ("🎹", "Atari ST YM"),
        "tiny_cache.json": ("🎵", "Tiny Music (Demoscene)"),
        "snes_cache.json": ("🔴", "SNES SPC"),
    }
    cache_counts = await asyncio.get_event_loop().run_in_executor(
        None, _get_all_cache_counts, cache_map
    )

    # ── Current state ──
    mode_icons = {
        "hvsc": "🟣", "asma": "🟢", "modarchive": "🟠",
        "ay": "🔵", "ym": "🎹", "tiny": "🎵", "spc": "🔴",
    }
    mode_labels = {
        "hvsc": "HVSC", "asma": "ASMA", "modarchive": "ModArchive",
        "ay": "AY", "ym": "Atari ST YM", "tiny": "Tiny", "spc": "SNES",
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
    """Toggle between collections: HVSC → ASMA → ModArchive → AY → YM → Tiny → SNES → HVSC ..."""
    state = get_state(ctx.guild.id)
    try:
        idx = _FLIP_ORDER.index(state.collection_mode)
    except ValueError:
        idx = -1
    next_mode = _FLIP_ORDER[(idx + 1) % len(_FLIP_ORDER)]
    await _switch_collection(ctx, next_mode, flip_seq=_FLIP_SEQ)


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
def _audtool_output_length() -> int:
    """Get current-song-output-length-seconds from audtool."""
    r = subprocess.run(
        ["audtool", "current-song-output-length-seconds"],
        capture_output=True, text=True
    )
    try:
        return int(r.stdout.strip())
    except (ValueError, OSError):
        return -1


def _audtool_song_length() -> int:
    """Get current-song-length-seconds from audtool."""
    r = subprocess.run(
        ["audtool", "current-song-length-seconds"],
        capture_output=True, text=True
    )
    try:
        return int(r.stdout.strip())
    except (ValueError, OSError):
        return -1


# ── Subsong Detection & Conversion ───────────────────────────────
_subsong_cache: dict[str, list[float]] = {}

def _get_subsongs(filepath: str) -> list[float]:
    """Return list of subsong durations for a module file. Empty list = no subsongs."""
    if filepath in _subsong_cache:
        return _subsong_cache[filepath]

    durations: list[float] = []
    for sub in range(0, 20):  # Max 20 subsongs (more than any module should have)
        try:
            res = subprocess.run(
                ['ffprobe', '-subsong', str(sub), '-v', 'quiet', '-print_format', 'json',
                 '-show_entries', 'format=duration', filepath],
                capture_output=True, text=True, timeout=10
            )
            if not res.stdout.strip():
                break
            data = json.loads(res.stdout)
            dur = data.get("format", {}).get("duration")
            if dur is not None:
                durations.append(float(dur))
            else:
                break
        except Exception:
            break

    _subsong_cache[filepath] = durations
    return durations


def _has_subsongs(filepath: str) -> bool:
    """Quick check: does this file have multiple sub-songs?"""
    subs = _get_subsongs(filepath)
    return len(subs) > 1


def _convert_subsong(filepath: str, subsong: int, output_path: str) -> bool:
    """Convert a specific subsong from a module file to WAV via ffmpeg."""
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-subsong', str(subsong), '-i', filepath,
             '-ac', '1', '-ar', '48000', '-f', 'wav', output_path],
            capture_output=True, timeout=60
        )
        return os.path.exists(output_path) and os.path.getsize(output_path) > 100
    except Exception:
        return False


def _subsong_temp_path(filepath: str, subsong: int) -> str:
    """Generate a temp path for a converted subsong WAV."""
    basename = os.path.basename(filepath).rsplit('.', 1)[0]
    safe = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in basename)
    return os.path.join(tempfile.gettempdir(), f"subsong_{safe}_{subsong}.wav")


async def play_subsong(ctx, state: PlaylistState, subsong: int) -> bool:
    """Convert and play a specific subsong via ffmpeg → WAV → Audacious."""
    if not state.subsong_path:
        return False

    orig_path = state.subsong_path
    wav_path = _subsong_temp_path(orig_path, subsong)

    # Convert in executor
    ok = await asyncio.get_event_loop().run_in_executor(
        None, _convert_subsong, orig_path, subsong, wav_path
    )
    if not ok:
        log.error("Subsong %d conversion failed for %s", subsong, orig_path)
        return False

    # Ensure WAV is tracked for cleanup
    while len(state.subsong_wavs) <= subsong:
        state.subsong_wavs.append("")
    state.subsong_wavs[subsong] = wav_path
    state.subsong_current = subsong

    # Stop old Audacious and play the WAV
    await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
    await asyncio.get_event_loop().run_in_executor(None, audacious_play, wav_path)
    state.current_sap_path = wav_path

    _setup_monitor_source(state)
    return True


def _cleanup_subsong_temp_wavs(state: PlaylistState) -> None:
    """Remove all temp WAVs for the current subsong group."""
    for wav in state.subsong_wavs:
        if wav and os.path.exists(wav):
            try:
                os.remove(wav)
            except OSError:
                pass
    state.subsong_wavs.clear()
    state.subsong_total = 0
    state.subsong_current = -1
    state.subsong_path = None


async def monitor_playback(ctx: commands.Context, vc: discord.VoiceClient, guild_id: int):
    """Monitor playback, auto-advance tracks, and disconnect on empty channel.
    Uses Audacious is_playing() for ALL formats (SAP, SID, MOD, AY via console/GME).

    Subprocess budget per poll cycle (2s):
      - is_playing() → 1 subprocess (always)
      - output-length → 1 subprocess (only when SAP is playing)
      - song-length  → 0 subprocesses after first read (cached per-track)
    """
    empty_since = None
    not_playing_since = None
    drop_confirmed_since = None
    GRACE_SECONDS = 3
    poll_interval = 2  # seconds between monitor checks
    last_output_len = -1  # track drops in output-length
    cached_song_length = -1  # per-track cache for song-length (<0 = not yet read)
    cached_sap_path: str | None = "__init__"  # track change detector
    while vc.is_connected() and not _shutdown_flag.is_set():
        try:
            await asyncio.sleep(poll_interval)
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
        playing = await asyncio.get_event_loop().run_in_executor(None, is_playing)

        # SAP-specific monitoring: drop detection + per-track timeout
        if playing and state.current_sap_path:
            # Detect track change → invalidate song-length cache
            if state.current_sap_path != cached_sap_path:
                cached_sap_path = state.current_sap_path
                cached_song_length = -1
                last_output_len = -1
                drop_confirmed_since = None

            # Output length — needed every cycle for drop detection
            secs = await asyncio.get_event_loop().run_in_executor(None, _audtool_output_length)

            # Song length — cached per-track (doesn't change during playback)
            if cached_song_length < 0:
                cached_song_length = await asyncio.get_event_loop().run_in_executor(None, _audtool_song_length)

            try:
                # Output length dropped below last seen value — track likely ended
                if last_output_len > 10 and secs < 5:
                    if drop_confirmed_since is None:
                        drop_confirmed_since = time.time()
                    elif (time.time() - drop_confirmed_since) >= GRACE_SECONDS:
                        log.info("Output length drop confirmed (%ds): %d→%d — forcing skip",
                                 GRACE_SECONDS, last_output_len, secs)
                        drop_confirmed_since = None
                        not_playing_since = None
                        await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
                        if state.loop or state.index < len(state.queue) - 1:
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
                else:
                    drop_confirmed_since = None
                last_output_len = secs

                # Per-track fallback timeout using cached song length
                reported = cached_song_length
                timeout_secs = reported + 15 if 10 < reported < 36000 else 600
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
            # Pre-download next track while current one plays (gapless transitions)
            if state.pre_downloaded is None and state.queue:
                next_idx = state.index + 1
                if next_idx < len(state.queue) or state.loop:
                    url = state.queue[next_idx % len(state.queue)]
                    if url.startswith("http"):
                        asyncio.create_task(pre_download_next(state))
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
LOCK_FILE = os.path.join(_ROOT, "obibok.pid")

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
    await close_shared_session()
    cleanup_temp()

_shutdown_flag = asyncio.Event()

def handle_signal(signum, frame):
    """Signal handler: schedule shutdown gracefully via thread-safe API."""
    log.info("Received signal %d, shutting down...", signum)
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.run_coroutine_threadsafe(graceful_shutdown(), loop)
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
