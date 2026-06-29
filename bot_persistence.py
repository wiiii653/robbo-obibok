"""Persistence helpers for favorites, playlists, and blacklist state."""

from __future__ import annotations

import os
from typing import Callable

from runtime_support import (
    build_playlist_record,
    ensure_directory,
    filter_blacklisted_urls,
    filter_track_entries_by_blacklist,
    get_user_tracks,
    load_cached_json_file,
    load_playlist_record,
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
