"""Runtime support helpers shared across startup and playback orchestration."""

from __future__ import annotations

import os
import random
import shutil
import json
from typing import Callable, Iterable


REQUIRED_EXTERNAL_TOOLS: dict[str, str] = {
    "audacious": "headless playback engine",
    "audtool": "Audacious remote control",
    "pactl": "PipeWire/PulseAudio sink management",
    "ffmpeg": "audio capture and transcoding",
    "ffprobe": "module subsong inspection",
    "7z": "YM archive extraction",
    "unrar": "SNES RSN extraction",
}


def load_dotenv_file(dotenv_path: str) -> bool:
    """Load simple KEY=VALUE pairs from .env into the process environment."""
    if not os.path.exists(dotenv_path):
        return False
    with open(dotenv_path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                os.environ.setdefault(key, value)
    return True


def get_missing_dependencies(required_tools: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """Return missing command-line tools as (binary, purpose) tuples."""
    tools = required_tools or REQUIRED_EXTERNAL_TOOLS
    missing = []
    for binary, purpose in tools.items():
        if shutil.which(binary) is None:
            missing.append((binary, purpose))
    return missing


def format_missing_dependencies(missing: Iterable[tuple[str, str]]) -> str:
    """Format a clear startup error for missing external dependencies."""
    items = list(missing)
    lines = ["Missing required external tools:"]
    for binary, purpose in items:
        lines.append(f"- {binary}: {purpose}")
    lines.append("Install the missing packages before starting the bot.")
    return "\n".join(lines)


def validate_runtime_dependencies(required_tools: dict[str, str] | None = None) -> None:
    """Raise RuntimeError when required external dependencies are unavailable."""
    missing = get_missing_dependencies(required_tools)
    if missing:
        raise RuntimeError(format_missing_dependencies(missing))


def can_restore_queue(
    saved: dict | None,
    tracks: list[str] | None,
    collection_mode: str,
    *,
    min_queue_length: int = 1,
) -> bool:
    """Return True when a saved queue is compatible with the current track set."""
    if not saved or not tracks:
        return False
    queue = saved.get("queue")
    if not isinstance(queue, list) or len(queue) < min_queue_length:
        return False
    if saved.get("collection_mode") != collection_mode:
        return False
    return queue[0] in tracks


def format_flip_sequence(flip_seq: list[str], current_tag: str) -> str:
    """Render the collection flip sequence with the active tag highlighted."""
    return " -> ".join(f"**{tag}**" if tag == current_tag else tag for tag in flip_seq)


def prepare_playback_queue(
    tracks: list[str] | None,
    saved: dict | None,
    collection_mode: str,
    default_loop: bool,
    *,
    shuffle_enabled: bool,
    min_queue_length: int = 1,
    track_filter: Callable[[list[str]], list[str]] | None = None,
    shuffle_func: Callable[[list[str]], None] | None = None,
) -> dict[str, object]:
    """Build queue/index/loop state from saved data or a fresh track list."""
    if can_restore_queue(saved, tracks, collection_mode, min_queue_length=min_queue_length):
        return {
            "queue": list(saved["queue"]),
            "index": saved.get("index", 0),
            "loop": saved.get("loop", default_loop),
            "restored": True,
        }

    queue = list(tracks or [])
    if track_filter is not None:
        queue = list(track_filter(queue))
    if shuffle_enabled:
        (shuffle_func or random.shuffle)(queue)
    return {
        "queue": queue,
        "index": 0 if queue else -1,
        "loop": default_loop,
        "restored": False,
    }


def build_collection_state_update(mode: str, tracks: list[str] | None) -> dict[str, object]:
    """Return normalized state fields for a collection switch."""
    normalized_tracks = list(tracks or [])
    return {
        "collection_mode": mode,
        "loaded_collection": mode if normalized_tracks else "",
        "tracks": normalized_tracks,
        "queue": [],
        "index": -1,
    }


def classify_track_route(url: str, current_mode: str, *, snes_known: bool = False) -> dict[str, str]:
    """Classify a track URL/path into a collection mode and playback handler key."""
    if current_mode == "spc" or snes_known:
        return {"mode": "spc", "handler": "spc"}
    if "://" not in url and url.endswith((".mod", ".xm", ".it", ".s3m", ".med", ".dmf", ".mo3")):
        return {"mode": "tiny", "handler": "tiny"}
    if "hvsc.c64.org" in url or url.endswith(".sid"):
        return {"mode": "hvsc", "handler": "hvsc"}
    if "modarchive" in url or url.endswith((".mod", ".xm", ".s3m", ".it")):
        return {"mode": "modarchive", "handler": "modarchive"}
    if url.endswith(".ay"):
        return {"mode": "ay", "handler": "ay"}
    if url.endswith(".ym"):
        return {"mode": "ym", "handler": "ym"}
    return {"mode": "asma", "handler": "asma"}


def should_disconnect_for_empty_channel(
    member_count: int,
    empty_since: float | None,
    now: float,
    timeout_seconds: int,
) -> tuple[bool, float | None]:
    """Decide whether an empty voice channel should trigger disconnect."""
    if member_count > 1:
        return False, None
    if empty_since is None:
        return False, now
    if timeout_seconds > 0 and (now - empty_since) >= timeout_seconds:
        return True, empty_since
    return False, empty_since


def is_gme_format_path(path: str | None) -> bool:
    """Return True when the current path is a GME-driven format with noisy timing data."""
    return bool(path and path.endswith((".ay", ".ym", ".spc", ".sid")))


def should_confirm_output_drop(
    last_output_len: int,
    current_secs: int,
    drop_confirmed_since: float | None,
    now: float,
    grace_seconds: int,
    *,
    is_gme_format: bool,
) -> tuple[bool, float | None]:
    """Evaluate SAP output-length drop detection state."""
    if is_gme_format:
        return False, None
    if last_output_len > 10 and current_secs < 5:
        if drop_confirmed_since is None:
            return False, now
        if (now - drop_confirmed_since) >= grace_seconds:
            return True, None
        return False, drop_confirmed_since
    return False, None


def compute_timeout_seconds(reported_length: int, *, is_gme_format: bool) -> int:
    """Compute fallback timeout for the active track."""
    if is_gme_format:
        return 600
    return reported_length + 15 if 10 < reported_length < 36000 else 600


def should_force_timeout_stop(current_secs: int, timeout_secs: int) -> bool:
    """Return True when playback exceeded the acceptable timeout window."""
    return current_secs > timeout_secs and current_secs < 10000


def should_start_predownload(
    queue_length: int,
    current_index: int,
    *,
    loop_enabled: bool,
    predownload_ready: bool,
    predownload_inflight: bool,
    next_url: str | None,
) -> bool:
    """Return True when the next remote track should be pre-downloaded."""
    if predownload_ready or predownload_inflight or queue_length <= 0:
        return False
    next_idx = current_index + 1
    if next_idx >= queue_length and not loop_enabled:
        return False
    return bool(next_url and next_url.startswith("http"))


def should_advance_after_stop(
    not_playing_since: float | None,
    now: float,
    grace_seconds: int,
    *,
    still_loaded: bool,
) -> tuple[bool, float | None]:
    """Decide whether a not-playing state is a real track end."""
    if not_playing_since is None:
        return False, now
    if (now - not_playing_since) >= grace_seconds and not still_loaded:
        return True, None
    return False, not_playing_since


def load_cached_json_file(path: str, cache_state: dict[str, object]) -> dict:
    """Load a JSON mapping file with mtime-based in-memory caching."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    if cache_state.get("data") is not None and cache_state.get("mtime") == mtime:
        return dict(cache_state["data"])
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    cache_state["data"] = data
    cache_state["mtime"] = mtime
    return dict(data)


def save_cached_json_file(
    path: str,
    data: dict,
    cache_state: dict[str, object],
    *,
    writer: Callable[[str, dict], None],
) -> None:
    """Persist a JSON mapping file and refresh its cache metadata."""
    writer(path, data)
    cache_state["data"] = dict(data)
    try:
        cache_state["mtime"] = os.path.getmtime(path)
    except OSError:
        cache_state["mtime"] = None


def ensure_directory(path: str) -> None:
    """Create a directory if needed."""
    os.makedirs(path, exist_ok=True)


def sanitize_playlist_name(name: str) -> str:
    """Sanitize a playlist name to a safe filename stem."""
    safe = "".join(c if c.isalnum() or c in " _-." else "_" for c in name)
    return safe.strip().strip(".") or "unnamed"


def build_playlist_record(
    name: str,
    tracks: list[dict],
    author_id: int,
    author_name: str,
    *,
    created: float,
) -> dict:
    """Build the persisted playlist payload."""
    return {
        "name": name,
        "author": author_name,
        "author_id": author_id,
        "created": created,
        "tracks": tracks,
    }


def load_playlist_record(playlists_dir: str, name: str) -> dict | None:
    """Load a named playlist file from disk."""
    safe_name = sanitize_playlist_name(name)
    for ext in ("", ".json"):
        path = os.path.join(playlists_dir, f"{safe_name}{ext}")
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    return json.load(handle)
            except Exception:
                return None
    return None


def summarize_playlists(playlists_dir: str) -> list[dict]:
    """Summarize saved playlist files for listing commands."""
    ensure_directory(playlists_dir)
    playlists = []
    for fname in sorted(os.listdir(playlists_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(playlists_dir, fname)
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
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


def get_user_tracks(data: dict, user_id: int | str) -> list[dict]:
    """Return track records for a user from favorites/blacklist storage."""
    return list(data.get(str(user_id), {}).get("tracks", []))


def toggle_user_track(data: dict, user_id: int | str, entry: dict) -> tuple[dict, bool]:
    """Toggle a track entry in a user-owned track collection."""
    uid = str(user_id)
    bucket = data.setdefault(uid, {"tracks": []})
    url = entry["url"]
    existing = any(track.get("url") == url for track in bucket["tracks"])
    if existing:
        bucket["tracks"] = [track for track in bucket["tracks"] if track.get("url") != url]
        return data, False
    bucket["tracks"].append(entry)
    return data, True


def remove_user_track(data: dict, user_id: int | str, url: str) -> tuple[dict, bool]:
    """Remove a track URL from a user-owned track collection."""
    uid = str(user_id)
    if uid not in data:
        return data, False
    tracks = data[uid].get("tracks", [])
    updated = [track for track in tracks if track.get("url") != url]
    if len(updated) == len(tracks):
        return data, False
    data[uid]["tracks"] = updated
    return data, True


def filter_blacklisted_urls(tracks: list[str], blacklist_data: dict, user_id: int | str) -> list[str]:
    """Filter plain track URLs using blacklist storage for a user."""
    user_tracks = get_user_tracks(blacklist_data, user_id)
    if not user_tracks:
        return list(tracks)
    blocked = {track["url"] for track in user_tracks}
    return [track for track in tracks if track not in blocked]


def filter_track_entries_by_blacklist(entries: list[dict], blacklist_data: dict, user_id: int | str) -> list[dict]:
    """Filter track entry dicts using blacklist storage for a user."""
    blocked = {track["url"] for track in get_user_tracks(blacklist_data, user_id)}
    return [entry for entry in entries if entry.get("url") not in blocked]
