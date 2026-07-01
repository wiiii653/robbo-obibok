"""Persistence helpers for favorites, playlists, and blacklist state."""

from __future__ import annotations

import os
import time
from typing import Callable

from runtime_support import (
    build_playlist_record,
    ensure_directory,
    filter_blacklisted_urls,
    filter_track_entries_by_blacklist,
    get_user_tracks,
    load_cached_json_file,
    load_playlist_record,
    normalize_queue_record,
    sanitize_playlist_name,
    save_cached_json_file,
    summarize_playlists,
    toggle_user_track,
)


def load_json_collection(path: str, cache_state: dict[str, object]) -> dict:
    """Load a cached JSON mapping collection."""
    return load_cached_json_file(path, cache_state)


def save_json_collection(
    path: str,
    data: dict,
    cache_state: dict[str, object],
    *,
    writer: Callable[[str, dict], None],
) -> None:
    """Persist a cached JSON mapping collection."""
    save_cached_json_file(path, data, cache_state, writer=writer)


def save_named_playlist(
    playlists_dir: str,
    name: str,
    tracks: list[dict],
    author_id: int,
    author_name: str,
    *,
    created: float,
    writer: Callable[[str, dict], None],
) -> str:
    """Persist a named playlist and return its safe filename stem."""
    ensure_directory(playlists_dir)
    safe_name = sanitize_playlist_name(name)
    path = os.path.join(playlists_dir, f"{safe_name}.json")
    record = build_playlist_record(name, tracks, author_id, author_name, created=created)
    writer(path, record)
    return safe_name


def load_named_playlist(playlists_dir: str, name: str) -> dict | None:
    """Load a named playlist record from disk."""
    return load_playlist_record(playlists_dir, name)


def list_named_playlists(playlists_dir: str) -> list[dict]:
    """List summarized playlist records from disk."""
    return summarize_playlists(playlists_dir)


def load_user_tracks(collection: dict, user_id: int | str) -> list[dict]:
    """Load user track entries from a collection."""
    return get_user_tracks(collection, user_id)


def toggle_user_track_entry(collection: dict, user_id: int | str, entry: dict) -> tuple[dict, bool]:
    """Toggle a user track entry inside a collection."""
    return toggle_user_track(collection, user_id, entry)


def filter_blacklisted_track_urls(tracks: list[str], blacklist: dict, user_id: int | str) -> list[str]:
    """Filter plain URLs using user blacklist data."""
    return filter_blacklisted_urls(tracks, blacklist, user_id)


def filter_blacklisted_track_entries(entries: list[dict], blacklist: dict, user_id: int | str) -> list[dict]:
    """Filter track entry dicts using user blacklist data."""
    return filter_track_entries_by_blacklist(entries, blacklist, user_id)


# ── Queue persistence (moved from AppRuntimeState) ─────────────────────────


def save_queue_to_disk(state, queue_dir: str, json_writer) -> None:
    """Persist a guild queue to disk."""
    if not state.guild_id:
        return
    os.makedirs(queue_dir, exist_ok=True)
    path = os.path.join(queue_dir, f"{state.guild_id}.json")
    json_writer(
        path,
        {
            "queue": state.queue,
            "index": state.index,
            "loop": state.loop,
            "collection_mode": state.collection_mode,
        },
    )


def load_queue_from_disk(guild_id: int, queue_dir: str) -> dict | None:
    """Load a persisted guild queue from disk."""
    path = os.path.join(queue_dir, f"{guild_id}.json")
    try:
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as handle:
            import json
            return normalize_queue_record(json.load(handle))
    except Exception:
        return None


class CachedJsonStore:
    """Thread-safe cached JSON file store for favorites/blacklist data."""

    def __init__(self, path: str, *, json_writer):
        self._path = path
        self._json_writer = json_writer
        self._cache_state: dict[str, object] = {"data": None, "mtime": None}

    def load(self) -> dict:
        return load_cached_json_file(self._path, self._cache_state)

    def save(self, data: dict) -> None:
        save_cached_json_file(
            self._path,
            data,
            self._cache_state,
            writer=self._json_writer,
        )


class PlaylistLibraryStore:
    """Store for named playlists backed by individual JSON files."""

    def __init__(self, playlists_dir: str, *, json_writer, logger):
        self.playlists_dir = playlists_dir
        self._json_writer = json_writer
        self._logger = logger

    def ensure_playlist_dir(self) -> None:
        try:
            ensure_directory(self.playlists_dir)
        except Exception as exc:
            self._logger.error("Failed to create playlists dir: %s", exc)

    def save_playlist(self, name: str, tracks: list[dict], author_id: int, author_name: str) -> str:
        return save_named_playlist(
            self.playlists_dir,
            name,
            tracks,
            author_id,
            author_name,
            created=time.time(),
            writer=self._json_writer,
        )

    def load_playlist(self, name: str) -> dict | None:
        playlist = load_named_playlist(self.playlists_dir, name)
        if playlist is None:
            safe_path = os.path.join(self.playlists_dir, f"{sanitize_playlist_name(name)}.json")
            if os.path.exists(safe_path):
                self._logger.error("Failed to load playlist '%s'", name)
        return playlist

    def list_playlists(self) -> list[dict]:
        return list_named_playlists(self.playlists_dir)
