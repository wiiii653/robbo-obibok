"""Typed runtime state and persistence helpers for the bot."""

from __future__ import annotations

import json
import os
import time
from types import MappingProxyType
from typing import Iterable, Mapping

from bot_persistence import (
    list_named_playlists,
    load_json_collection,
    load_named_playlist,
    save_json_collection,
    save_named_playlist,
)
from runtime_support import ensure_directory, sanitize_playlist_name


class PlaylistState:
    def __init__(self, default_collection_mode: str = "asma"):
        self.tracks: list[str] = []
        self.queue: list[str] = []
        self.index: int = -1
        self.loop: bool = True
        self.collection_mode: str = default_collection_mode
        self.loaded_collection: str = ""
        self.guild_id: int | None = None
        self.ctx = None
        self.vc = None
        self.current_track_path: str | None = None
        self.crawling: bool = False
        self.pre_downloaded: str | None = None
        self.pre_downloaded_url: str | None = None
        self.pre_download_task = None
        self.search_results: list[str] = []
        self.monitor_task = None
        self.subsong_current: int = -1
        self.subsong_total: int = 0
        self.subsong_path: str | None = None
        self.subsong_wavs: list[str] = []

    def bind_voice_context(self, *, guild_id: int, ctx, vc) -> None:
        self.guild_id = guild_id
        self.ctx = ctx
        self.vc = vc

    def set_guild_id(self, guild_id: int | None) -> None:
        self.guild_id = guild_id

    def set_collection_mode(self, mode: str) -> None:
        self.collection_mode = mode

    def set_tracks(self, tracks: list[str] | None) -> None:
        self.tracks = list(tracks or [])

    def set_loaded_collection(self, mode: str, tracks: list[str]) -> None:
        self.collection_mode = mode
        self.loaded_collection = mode
        self.set_tracks(tracks)

    def set_loaded_collection_name(self, mode: str) -> None:
        self.loaded_collection = mode

    def clear_loaded_collection(self) -> None:
        self.loaded_collection = ""

    def set_queue_state(self, queue: list[str], index: int, *, loop: bool | None = None) -> None:
        self.queue = list(queue)
        self.index = index
        if loop is not None:
            self.loop = loop

    def set_loop_enabled(self, enabled: bool) -> None:
        self.loop = enabled

    def advance_queue_index(self) -> int:
        self.index += 1
        return self.index

    def clear_queue_state(self) -> None:
        self.queue = []
        self.index = -1

    def queue_length(self) -> int:
        return len(self.queue)

    def set_search_results(self, results: list[str]) -> None:
        self.search_results = list(results)

    def set_context(self, ctx) -> None:
        self.ctx = ctx

    def set_current_path(self, path: str | None) -> None:
        self.current_track_path = path

    def set_monitor_task(self, task) -> None:
        self.monitor_task = task

    def set_voice_client(self, vc) -> None:
        self.vc = vc

    def clear_voice_client(self) -> None:
        self.vc = None

    def set_predownload(self, filepath: str, url: str) -> None:
        self.pre_downloaded = filepath
        self.pre_downloaded_url = url

    def has_predownload_for(self, url: str) -> bool:
        return self.pre_downloaded is not None and self.pre_downloaded_url == url

    def current_queue_url(self) -> str | None:
        if 0 <= self.index < len(self.queue):
            return self.queue[self.index]
        return None

    def has_current_queue_item(self) -> bool:
        return self.current_queue_url() is not None

    def current_queue_position(self) -> tuple[int, int] | None:
        if not self.has_current_queue_item():
            return None
        return self.index + 1, self.queue_length()

    def remaining_queue_count(self) -> int:
        position = self.current_queue_position()
        if position is None:
            return self.queue_length()
        return position[1] - position[0]

    def contains_queue_index(self, index: int) -> bool:
        return 0 <= index < self.queue_length()

    def next_queue_url(self) -> str | None:
        next_index = self.index + 1
        if self.contains_queue_index(next_index):
            return self.queue[next_index]
        if self.loop and self.queue:
            return self.queue[0]
        return None

    def upcoming_queue(self, limit: int = 10) -> list[str]:
        if not self.has_current_queue_item():
            return []
        return self.queue[self.index + 1 : self.index + 1 + limit]

    def played_queue(self, limit: int = 10) -> list[str]:
        if self.index <= 0:
            return []
        start = max(0, self.index - limit)
        return self.queue[start:self.index]

    def set_predownload_task(self, task) -> None:
        self.pre_download_task = task

    def clear_predownload(self) -> None:
        self.pre_downloaded = None
        self.pre_downloaded_url = None
        self.pre_download_task = None

    def set_subsong_state(self, *, path: str, total: int, current: int = 0) -> None:
        self.subsong_path = path
        self.subsong_total = total
        self.subsong_current = current

    def set_current_subsong(self, subsong: int) -> None:
        self.subsong_current = subsong

    def ensure_subsong_slot(self, subsong: int) -> None:
        while len(self.subsong_wavs) <= subsong:
            self.subsong_wavs.append("")

    def set_subsong_wav(self, subsong: int, wav_path: str) -> None:
        self.ensure_subsong_slot(subsong)
        self.subsong_wavs[subsong] = wav_path

    def reset_subsong_state(self) -> None:
        self.subsong_wavs.clear()
        self.subsong_total = 0
        self.subsong_current = -1
        self.subsong_path = None


class AppRuntimeState:
    def __init__(
        self,
        *,
        queue_dir: str,
        default_collection_mode: str,
        json_writer,
        message_track_map_max: int = 50,
    ):
        self._queue_dir = queue_dir
        self._default_collection_mode = default_collection_mode
        self._json_writer = json_writer
        self.guilds: dict[int, PlaylistState] = {}
        self.message_track_map: dict[int, dict[str, object]] = {}
        self._message_track_map_max = message_track_map_max

    def get_state(self, guild_id: int) -> PlaylistState:
        if guild_id not in self.guilds:
            self.guilds[guild_id] = PlaylistState(self._default_collection_mode)
        return self.guilds[guild_id]

    def register_now_playing_message(self, msg_id: int, url: str, name: str, author: str) -> None:
        self.message_track_map[msg_id] = {
            "url": url,
            "name": name,
            "author": author,
            "timestamp": time.time(),
        }
        self._prune_message_track_map()

    def iter_guild_states(self) -> Iterable[PlaylistState]:
        return self.guilds.values()

    def get_message_track(self, msg_id: int) -> dict[str, object] | None:
        return self.message_track_map.get(msg_id)

    def register_guild_state(self, guild_id: int, state: PlaylistState) -> None:
        self.guilds[guild_id] = state

    def replace_guilds(self, guilds: dict[int, PlaylistState]) -> None:
        self.guilds.clear()
        self.guilds.update(guilds)

    def replace_message_track_map(self, entries: dict[int, dict[str, object]]) -> None:
        self.message_track_map.clear()
        self.message_track_map.update(entries)

    @property
    def guilds_view(self) -> Mapping[int, PlaylistState]:
        return MappingProxyType(self.guilds)

    @property
    def message_track_map_view(self) -> Mapping[int, dict[str, object]]:
        return MappingProxyType(self.message_track_map)

    def save_queue(self, state: PlaylistState) -> None:
        if not state.guild_id:
            return
        os.makedirs(self._queue_dir, exist_ok=True)
        path = os.path.join(self._queue_dir, f"{state.guild_id}.json")
        self._json_writer(
            path,
            {
                "queue": state.queue,
                "index": state.index,
                "loop": state.loop,
                "collection_mode": state.collection_mode,
            },
        )

    def load_queue(self, guild_id: int) -> dict | None:
        path = os.path.join(self._queue_dir, f"{guild_id}.json")
        try:
            if not os.path.exists(path):
                return None
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return None

    def _prune_message_track_map(self) -> None:
        if len(self.message_track_map) <= self._message_track_map_max:
            return
        sorted_ids = sorted(
            self.message_track_map.items(),
            key=lambda item: item[1].get("timestamp", 0),
            reverse=True,
        )
        self.message_track_map.clear()
        self.message_track_map.update(dict(sorted_ids[: self._message_track_map_max]))


class CachedJsonStore:
    def __init__(self, path: str, *, json_writer):
        self._path = path
        self._json_writer = json_writer
        self._cache_state: dict[str, object] = {"data": None, "mtime": None}

    def load(self) -> dict:
        return load_json_collection(self._path, self._cache_state)

    def save(self, data: dict) -> None:
        save_json_collection(
            self._path,
            data,
            self._cache_state,
            writer=self._json_writer,
        )


class PlaylistLibraryStore:
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
