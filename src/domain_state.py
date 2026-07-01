"""Typed runtime state and persistence helpers for the bot.

PlaylistState is a composite container that delegates to three sub-states:
  - PlaybackQueueState — queue management, subsong playback state
  - CollectionState — collection browsing state
  - GuildSession — Discord guild session state

New code should access sub-states directly (state.queue_state.queue).
Backward-compatible properties and method delegations preserve all existing code.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from bot_persistence import CachedJsonStore, PlaylistLibraryStore  # noqa: F401 — re-exported

# ── Sub-states ──────────────────────────────────────────────────────────────


@dataclass
class PlaybackQueueState:
    """Queue and subsong playback state."""

    queue: list[str] = field(default_factory=list)
    index: int = -1
    loop: bool = True
    subsong_current: int = -1
    subsong_total: int = 0
    subsong_path: str | None = None
    subsong_wavs: list[str] = field(default_factory=list)

    def set_queue_state(
        self, queue: list[str], index: int, *, loop: bool | None = None
    ) -> None:
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

    def set_subsong_state(
        self, *, path: str, total: int, current: int = 0
    ) -> None:
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


@dataclass
class CollectionState:
    """Collection browsing state."""

    tracks: list[str] = field(default_factory=list)
    collection_mode: str = "asma"
    loaded_collection: str = ""
    search_results: list[str] = field(default_factory=list)
    crawling: bool = False

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

    def set_search_results(self, results: list[str]) -> None:
        self.search_results = list(results)


@dataclass
class GuildSession:
    """Discord guild session state."""

    guild_id: int | None = None
    ctx: Any = None
    vc: Any = None
    current_track_path: str | None = None
    pre_downloaded: str | None = None
    pre_downloaded_url: str | None = None
    pre_download_task: Any = None
    monitor_task: Any = None

    def bind_voice_context(
        self, *, guild_id: int, ctx, vc
    ) -> None:
        self.guild_id = guild_id
        self.ctx = ctx
        self.vc = vc

    def set_guild_id(self, guild_id: int | None) -> None:
        self.guild_id = guild_id

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

    def set_predownload_task(self, task) -> None:
        self.pre_download_task = task

    def clear_predownload(self) -> None:
        self.pre_downloaded = None
        self.pre_downloaded_url = None
        self.pre_download_task = None


# ── Composite (backward compatible) ─────────────────────────────────────────


class PlaylistState:
    """Composite state container with backward-compatible attribute access.

    All direct attribute access (``state.queue``, ``state.loop``, etc.) still works
    via properties that delegate to the appropriate sub-state.

    New code should access sub-states directly:
    - ``state.queue_state.queue`` instead of ``state.queue``
    - ``state.collection.tracks`` instead of ``state.tracks``
    - ``state.session.guild_id`` instead of ``state.guild_id``
    """

    def __init__(self, default_collection_mode: str = "asma"):
        self.queue_state = PlaybackQueueState()
        self.collection = CollectionState(collection_mode=default_collection_mode)
        self.session = GuildSession()

    # ── Backward-compatible property delegations ──
    # PlaybackQueueState

    @property
    def queue(self) -> list[str]:
        return self.queue_state.queue

    @queue.setter
    def queue(self, value: list[str]) -> None:
        self.queue_state.queue = value

    @property
    def index(self) -> int:
        return self.queue_state.index

    @index.setter
    def index(self, value: int) -> None:
        self.queue_state.index = value

    @property
    def loop(self) -> bool:
        return self.queue_state.loop

    @loop.setter
    def loop(self, value: bool) -> None:
        self.queue_state.loop = value

    @property
    def subsong_current(self) -> int:
        return self.queue_state.subsong_current

    @subsong_current.setter
    def subsong_current(self, value: int) -> None:
        self.queue_state.subsong_current = value

    @property
    def subsong_total(self) -> int:
        return self.queue_state.subsong_total

    @subsong_total.setter
    def subsong_total(self, value: int) -> None:
        self.queue_state.subsong_total = value

    @property
    def subsong_path(self) -> str | None:
        return self.queue_state.subsong_path

    @subsong_path.setter
    def subsong_path(self, value: str | None) -> None:
        self.queue_state.subsong_path = value

    @property
    def subsong_wavs(self) -> list[str]:
        return self.queue_state.subsong_wavs

    @subsong_wavs.setter
    def subsong_wavs(self, value: list[str]) -> None:
        self.queue_state.subsong_wavs = value

    # CollectionState

    @property
    def tracks(self) -> list[str]:
        return self.collection.tracks

    @tracks.setter
    def tracks(self, value: list[str]) -> None:
        self.collection.tracks = value

    @property
    def collection_mode(self) -> str:
        return self.collection.collection_mode

    @collection_mode.setter
    def collection_mode(self, value: str) -> None:
        self.collection.collection_mode = value

    @property
    def loaded_collection(self) -> str:
        return self.collection.loaded_collection

    @loaded_collection.setter
    def loaded_collection(self, value: str) -> None:
        self.collection.loaded_collection = value

    @property
    def search_results(self) -> list[str]:
        return self.collection.search_results

    @search_results.setter
    def search_results(self, value: list[str]) -> None:
        self.collection.search_results = value

    @property
    def crawling(self) -> bool:
        return self.collection.crawling

    @crawling.setter
    def crawling(self, value: bool) -> None:
        self.collection.crawling = value

    # GuildSession

    @property
    def guild_id(self) -> int | None:
        return self.session.guild_id

    @guild_id.setter
    def guild_id(self, value: int | None) -> None:
        self.session.guild_id = value

    @property
    def ctx(self):
        return self.session.ctx

    @ctx.setter
    def ctx(self, value):
        self.session.ctx = value

    @property
    def vc(self):
        return self.session.vc

    @vc.setter
    def vc(self, value):
        self.session.vc = value

    @property
    def current_track_path(self) -> str | None:
        return self.session.current_track_path

    @current_track_path.setter
    def current_track_path(self, value: str | None) -> None:
        self.session.current_track_path = value

    @property
    def pre_downloaded(self) -> str | None:
        return self.session.pre_downloaded

    @pre_downloaded.setter
    def pre_downloaded(self, value: str | None) -> None:
        self.session.pre_downloaded = value

    @property
    def pre_downloaded_url(self) -> str | None:
        return self.session.pre_downloaded_url

    @pre_downloaded_url.setter
    def pre_downloaded_url(self, value: str | None) -> None:
        self.session.pre_downloaded_url = value

    @property
    def pre_download_task(self):
        return self.session.pre_download_task

    @pre_download_task.setter
    def pre_download_task(self, value):
        self.session.pre_download_task = value

    @property
    def monitor_task(self):
        return self.session.monitor_task

    @monitor_task.setter
    def monitor_task(self, value):
        self.session.monitor_task = value

    # ── Backward-compatible method delegations ──
    # PlaybackQueueState

    def set_queue_state(
        self, queue, index, *, loop=None
    ) -> None:
        self.queue_state.set_queue_state(queue, index, loop=loop)

    def set_loop_enabled(self, enabled: bool) -> None:
        self.queue_state.set_loop_enabled(enabled)

    def advance_queue_index(self) -> int:
        return self.queue_state.advance_queue_index()

    def clear_queue_state(self) -> None:
        self.queue_state.clear_queue_state()

    def queue_length(self) -> int:
        return self.queue_state.queue_length()

    def current_queue_url(self) -> str | None:
        return self.queue_state.current_queue_url()

    def has_current_queue_item(self) -> bool:
        return self.queue_state.has_current_queue_item()

    def current_queue_position(self) -> tuple[int, int] | None:
        return self.queue_state.current_queue_position()

    def remaining_queue_count(self) -> int:
        return self.queue_state.remaining_queue_count()

    def contains_queue_index(self, index: int) -> bool:
        return self.queue_state.contains_queue_index(index)

    def next_queue_url(self) -> str | None:
        return self.queue_state.next_queue_url()

    def upcoming_queue(self, limit: int = 10) -> list[str]:
        return self.queue_state.upcoming_queue(limit)

    def played_queue(self, limit: int = 10) -> list[str]:
        return self.queue_state.played_queue(limit)

    def set_subsong_state(
        self, *, path, total, current=0
    ) -> None:
        self.queue_state.set_subsong_state(path=path, total=total, current=current)

    def set_current_subsong(self, subsong: int) -> None:
        self.queue_state.set_current_subsong(subsong)

    def ensure_subsong_slot(self, subsong: int) -> None:
        self.queue_state.ensure_subsong_slot(subsong)

    def set_subsong_wav(self, subsong: int, wav_path: str) -> None:
        self.queue_state.set_subsong_wav(subsong, wav_path)

    def reset_subsong_state(self) -> None:
        self.queue_state.reset_subsong_state()

    # CollectionState

    def set_collection_mode(self, mode: str) -> None:
        self.collection.set_collection_mode(mode)

    def set_tracks(self, tracks: list[str] | None) -> None:
        self.collection.set_tracks(tracks)

    def set_loaded_collection(self, mode: str, tracks: list[str]) -> None:
        self.collection.set_loaded_collection(mode, tracks)

    def set_loaded_collection_name(self, mode: str) -> None:
        self.collection.set_loaded_collection_name(mode)

    def clear_loaded_collection(self) -> None:
        self.collection.clear_loaded_collection()

    def set_search_results(self, results: list[str]) -> None:
        self.collection.set_search_results(results)

    # GuildSession

    def bind_voice_context(self, *, guild_id: int, ctx, vc) -> None:
        self.session.bind_voice_context(guild_id=guild_id, ctx=ctx, vc=vc)

    def set_guild_id(self, guild_id: int | None) -> None:
        self.session.set_guild_id(guild_id)

    def set_context(self, ctx) -> None:
        self.session.set_context(ctx)

    def set_current_path(self, path: str | None) -> None:
        self.session.set_current_path(path)

    def set_monitor_task(self, task) -> None:
        self.session.set_monitor_task(task)

    def set_voice_client(self, vc) -> None:
        self.session.set_voice_client(vc)

    def clear_voice_client(self) -> None:
        self.session.clear_voice_client()

    def set_predownload(self, filepath: str, url: str) -> None:
        self.session.set_predownload(filepath, url)

    def has_predownload_for(self, url: str) -> bool:
        return self.session.has_predownload_for(url)

    def set_predownload_task(self, task) -> None:
        self.session.set_predownload_task(task)

    def clear_predownload(self) -> None:
        self.session.clear_predownload()


# ── AppRuntimeState ─────────────────────────────────────────────────────────


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

    def register_now_playing_message(
        self, msg_id: int, url: str, name: str, author: str
    ) -> None:
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

    def register_guild_state(
        self, guild_id: int, state: PlaylistState
    ) -> None:
        self.guilds[guild_id] = state

    def replace_guilds(self, guilds: dict[int, PlaylistState]) -> None:
        self.guilds.clear()
        self.guilds.update(guilds)

    def replace_message_track_map(
        self, entries: dict[int, dict[str, object]]
    ) -> None:
        self.message_track_map.clear()
        self.message_track_map.update(entries)

    @property
    def guilds_view(self) -> Mapping[int, PlaylistState]:
        return MappingProxyType(self.guilds)

    @property
    def message_track_map_view(self) -> Mapping[int, dict[str, object]]:
        return MappingProxyType(self.message_track_map)

    def _prune_message_track_map(self) -> None:
        if len(self.message_track_map) <= self._message_track_map_max:
            return

        def message_timestamp(
            item: tuple[int, dict[str, object]],
        ) -> float:
            value = item[1].get("timestamp", 0)
            return float(value) if isinstance(value, (int, float)) else 0.0

        sorted_ids = sorted(
            self.message_track_map.items(),
            key=message_timestamp,
            reverse=True,
        )
        self.message_track_map.clear()
        self.message_track_map.update(
            dict(sorted_ids[: self._message_track_map_max])
        )

    # ── Temporary delegation methods for backward compatibility ────────────

    def save_queue(self, state: PlaylistState) -> None:
        """Delegate to queue persistence.

        .. deprecated::
            Use ``save_queue_to_disk`` from :mod:`bot_persistence` directly.
        """
        from bot_persistence import save_queue_to_disk

        save_queue_to_disk(state, self._queue_dir, self._json_writer)

    def load_queue(self, guild_id: int) -> dict | None:
        """Delegate to queue persistence.

        .. deprecated::
            Use ``load_queue_from_disk`` from :mod:`bot_persistence` directly.
        """
        from bot_persistence import load_queue_from_disk

        return load_queue_from_disk(guild_id, self._queue_dir)
