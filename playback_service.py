"""Playback and session service adapters for the bot runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

from app_state import PlaylistState
from session_runtime import (
    auto_play_after_switch,
    fetch_metadata_background,
    play_current_track,
    pre_download_next,
    skip_to_next,
)

if TYPE_CHECKING:
    from bot_runtime import BotRuntime
    from discord.ext import commands


@dataclass(slots=True)
class PlaybackService:
    runtime: "BotRuntime"
    bot: "commands.Bot"
    play_subsong: Callable[[object, PlaylistState, int], Awaitable[bool]]
    cleanup_subsong_temp_wavs: Callable[[PlaylistState], None]

    async def pre_download_next(self, state: PlaylistState) -> None:
        await pre_download_next(state, self.runtime.build_playback_session_deps())

    async def start_targeted_playback_session(self, ctx: object, state: PlaylistState, url: str) -> bool:
        return await self.runtime.start_targeted_playback_session(ctx, state, url)

    async def play_current_track(self, ctx: object) -> bool:
        return await play_current_track(ctx, self.runtime.build_playback_session_deps())

    async def skip_to_next(self, ctx: object) -> None:
        await skip_to_next(
            ctx,
            self.runtime.build_playback_session_deps(),
            self.play_subsong,
            self.cleanup_subsong_temp_wavs,
        )

    async def auto_play_after_switch(self, ctx: object, state: PlaylistState) -> None:
        await auto_play_after_switch(ctx, state, self.runtime.build_playback_session_deps())

    async def fetch_metadata_background(self) -> None:
        await fetch_metadata_background(self.bot, self.runtime.build_metadata_session_deps())
