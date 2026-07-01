"""Glue helpers for entrypoint-local runtime callbacks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from hashlib import sha1
from typing import TYPE_CHECKING, Any, Callable, cast

from discord.ext import commands

from domain_state import PlaylistState
from playback_helpers import play_via_audacious, queue_position, send_now_playing_embed

if TYPE_CHECKING:
    from discord import Colour

    from entrypoint_app import EntrypointComponentAccess
    from entrypoint_bootstrap import EntrypointResources
    from entrypoint_state import EntrypointGlueStateProtocol


def clear_predownload_state(state: Any, *, keep_file: bool = False) -> None:
    """Reset pre-download bookkeeping and cancel in-flight work when needed."""
    task = state.pre_download_task
    state.set_predownload_task(None)
    if task and not task.done():
        task.cancel()
    if not keep_file and state.pre_downloaded and os.path.exists(state.pre_downloaded):
        try:
            os.remove(state.pre_downloaded)
        except OSError:
            pass
    state.clear_predownload()


def place_track_in_queue(queue: list[str], url: str) -> tuple[list[str], int]:
    """Return queue/index with the target track selected, inserting if needed."""
    positioned_queue = list(queue)
    try:
        index = positioned_queue.index(url)
    except ValueError:
        positioned_queue.insert(0, url)
        index = 0
    return positioned_queue, index


def build_temp_path(temp_dir: str, url: str) -> str:
    """Create a collision-resistant temp path for a downloaded track."""
    filename = url.split("/")[-1] or "track.bin"
    digest = sha1(url.encode("utf-8")).hexdigest()[:12]
    return os.path.join(temp_dir, f"{digest}_{filename}")


@dataclass(slots=True)
class EntrypointGlue:
    state: EntrypointGlueStateProtocol
    resources: EntrypointResources
    components: EntrypointComponentAccess

    def apply_queue_state(self, state: PlaylistState, queue_state: dict[str, object]) -> bool:
        state.set_queue_state(
            list(cast(list[str], queue_state["queue"])),
            int(cast(int, queue_state["index"])),
            loop=bool(queue_state["loop"]),
        )
        return bool(queue_state.get("restored"))

    def place_track_in_queue(self, queue: list[str], url: str) -> tuple[list[str], int]:
        return place_track_in_queue(queue, url)

    def queue_position(self, state: PlaylistState) -> tuple[int, int]:
        return queue_position(state)

    def build_temp_path(self, url: str) -> str:
        return build_temp_path(self.resources.app_cfg().temp_dir, url)

    def after_stream_end(self, guild_id: int | None, error: Exception | None, source_id: int = 0) -> None:
        self.components.require().stream_runtime.after_stream_end(guild_id, error, source_id)

    async def cancel_monitor(self, state: PlaylistState) -> None:
        await self.components.require().stream_runtime.cancel_monitor(state)

    async def pre_download_next(self, state: PlaylistState) -> None:
        playback_service = self.components.require().playback_service
        assert playback_service is not None
        await playback_service.pre_download_next(state)

    async def start_targeted_playback_session(
        self,
        ctx: object,
        state: PlaylistState,
        url: str,
    ) -> bool:
        playback_service = self.components.require().playback_service
        assert playback_service is not None
        return await playback_service.start_targeted_playback_session(ctx, state, url)

    async def play_via_audacious(
        self,
        state: PlaylistState,
        playback_path: str,
        *,
        current_path: str | None = None,
    ) -> None:
        now_playing_deps = self.components.require().now_playing_deps
        await play_via_audacious(
            state,
            playback_path,
            now_playing_deps,
            current_path=current_path,
        )

    async def send_now_playing_embed(
        self,
        ctx: object,
        state: PlaylistState,
        url: str,
        *,
        title: str,
        color: Colour,
        footer: str,
        author: str = "",
        extra_fields: list[tuple[str, str]] | None = None,
    ) -> None:
        now_playing_deps = self.components.require().now_playing_deps
        await send_now_playing_embed(
            ctx,
            state,
            url,
            now_playing_deps,
            title=title,
            color=color,
            footer=footer,
            author=author,
            extra_fields=extra_fields,
        )


def build_single_guild_check(*, guild_id_getter: Callable[[], int | None]):
    active_guild_id: int | None = None

    def single_guild_check(ctx: commands.Context) -> bool:
        """Keep the process-global audio backend scoped to one guild."""
        nonlocal active_guild_id
        if ctx.guild is None:
            return False
        configured_guild_id = guild_id_getter()
        if configured_guild_id is not None:
            return ctx.guild.id == configured_guild_id
        if active_guild_id is None:
            active_guild_id = ctx.guild.id
        return ctx.guild.id == active_guild_id

    return single_guild_check


def mod_only():
    """Check if user has Manage Channels permission or is bot owner."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author == ctx.bot.owner:
            return True
        if hasattr(ctx.author, "guild_permissions") and ctx.author.guild_permissions.manage_channels:
            return True
        raise commands.MissingPermissions(["manage_channels"])

    return commands.check(predicate)
