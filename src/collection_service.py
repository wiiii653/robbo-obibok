"""Collection switching and cache status helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Awaitable, Callable, Protocol, cast

from domain_state import PlaylistState
from collection_specs import CollectionSpec

if TYPE_CHECKING:
    from archive_catalog import CollectionInfo
    from discord.ext import commands


class CollectionArchiveProtocol(Protocol):
    def get_collection_info(self, mode: str) -> "CollectionInfo": ...

    async def load_tracks_for_mode(self, mode: str) -> list[str] | None: ...


@dataclass(slots=True)
class CollectionService:
    archives: CollectionArchiveProtocol
    collections: dict[str, CollectionSpec]
    root_dir: str
    status_count_cache: dict[str, tuple[float, int | str]]
    flip_sequence_formatter: Callable[[list[str], str], str]
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]]
    save_last_collection: Callable[[str], None]
    set_volume_for_collection: Callable[[str], None]
    auto_play_after_switch: Callable[[object, PlaylistState], Awaitable[None]]
    get_state: Callable[[int], PlaylistState]
    stop_all_players: Callable[[], None]
    stop_state_streams: Callable[[PlaylistState], Awaitable[None]]
    log: logging.Logger

    def get_collection_info(self, mode: str) -> "CollectionInfo":
        return self.archives.get_collection_info(mode)

    async def load_tracks_for_mode(self, mode: str) -> list[str] | None:
        return await self.archives.load_tracks_for_mode(mode)

    async def ensure_tracks(self, state: PlaylistState) -> bool:
        if state.tracks and state.loaded_collection == state.collection_mode:
            return True
        tracks = await self.load_tracks_for_mode(state.collection_mode)
        state.set_tracks(tracks)
        if state.tracks:
            state.set_loaded_collection_name(state.collection_mode)
        return bool(state.tracks)

    async def switch_collection(
        self,
        ctx: object,
        mode: str,
        *,
        flip_seq: list[str] | None = None,
    ) -> bool:
        ctx = cast("commands.Context[commands.Bot]", ctx)
        assert ctx.guild is not None
        state = self.get_state(ctx.guild.id)
        cfg = self.collections[mode]

        if not flip_seq and cfg.already_msg and state.collection_mode == mode and state.tracks:
            await ctx.send(cfg.already_msg)
            return False
        if not flip_seq and cfg.load_msg:
            await ctx.send(cfg.load_msg)

        self.stop_all_players()
        await self.stop_state_streams(state)

        tracks = cfg.load_func()
        if not tracks and cfg.fallback_func:
            if flip_seq:
                seq = self.flip_sequence_formatter(flip_seq, cfg.flip_tag)
                await ctx.send((cfg.flip_load_msg or "") + f"\n{seq}")
            tracks = cfg.fallback_func()

        if not tracks:
            if cfg.allow_empty:
                state_update = self.build_collection_state_update(mode, [])
                state.set_collection_mode(str(state_update["collection_mode"]))
                state.set_loaded_collection_name(str(state_update["loaded_collection"]))
                self.save_last_collection(mode)
                self.set_volume_for_collection(mode)
                state.set_tracks(list(cast(list[str], state_update["tracks"])))
                state.set_queue_state(
                    list(cast(list[str], state_update["queue"])),
                    int(cast(int, state_update["index"])),
                )
                if flip_seq:
                    seq = self.flip_sequence_formatter(flip_seq, cfg.flip_tag)
                    await ctx.send((cfg.flip_ready_empty_msg or "") + f"\n{seq}")
                else:
                    await ctx.send(cfg.ready_empty_msg or "")
                self.log.info(cfg.log_msg)
                await self.auto_play_after_switch(ctx, state)
                return True
            if flip_seq:
                seq = self.flip_sequence_formatter(flip_seq, cfg.flip_tag)
                prev_cfg = self.collections.get(state.collection_mode)
                prev_label = prev_cfg.label if prev_cfg else "?"
                await ctx.send((cfg.flip_fail_msg or "").format(prev=prev_label) + f"\n{seq}")
            else:
                await ctx.send(cfg.error_msg or "❌ Failed to load collection.")
            return False

        state_update = self.build_collection_state_update(mode, tracks)
        state.set_loaded_collection(
            str(state_update["loaded_collection"]),
            list(cast(list[str], state_update["tracks"])),
        )
        self.save_last_collection(mode)
        self.set_volume_for_collection(mode)
        state.set_queue_state(
            list(cast(list[str], state_update["queue"])),
            int(cast(int, state_update["index"])),
        )

        if flip_seq:
            seq = self.flip_sequence_formatter(flip_seq, cfg.flip_tag)
            await ctx.send((cfg.flip_ready_msg or "").format(count=len(state.tracks)) + f"\n{seq}")
        else:
            await ctx.send((cfg.ready_msg or "").format(count=len(state.tracks)))

        if cfg.log_args:
            self.log.info(cfg.log_msg, len(state.tracks))
        else:
            self.log.info(cfg.log_msg)

        if cfg.after_hook:
            await cfg.after_hook(ctx, state.tracks)

        await self.auto_play_after_switch(ctx, state)
        return True

    def get_cache_count(self, fname: str) -> int | str:
        fpath = os.path.join(self.root_dir, fname)
        try:
            mtime = os.path.getmtime(fpath)
        except OSError:
            return "⚠️"
        cached = self.status_count_cache.get(fname)
        if cached and cached[0] == mtime:
            return cached[1]
        try:
            with open(fpath) as handle:
                data = json.load(handle)
            if isinstance(data, list):
                count: int | str = len(data)
            elif isinstance(data, dict):
                raw_count = data.get("total_sets")
                if isinstance(raw_count, int):
                    count = raw_count
                else:
                    tracks = data.get("tracks", data.get("count", []))
                    count = len(tracks) if isinstance(tracks, (list, dict, str)) else "?"
            else:
                count = "?"
        except Exception:
            count = "⚠️"
        self.status_count_cache[fname] = (mtime, count)
        return count

    def get_all_cache_counts(self, cache_map: dict) -> dict:
        result = {}
        for fname, (icon, label) in cache_map.items():
            result[label] = (icon, self.get_cache_count(fname))
        return result
