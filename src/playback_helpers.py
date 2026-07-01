"""Shared playback helper functions used by collection-specific handlers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from domain_state import PlaylistState


@dataclass(slots=True)
class NowPlayingDependencies:
    audacious_play: Callable[[str], None]
    audacious_stop: Callable[[], None]
    embed_factory: Callable[..., Any]
    register_np_message: Callable[[int, str, str, str], None]
    setup_monitor_source: Callable[[Any], None]


def queue_position(state: PlaylistState) -> tuple[int, int]:
    """Return current queue position and total track count."""
    return state.index + 1, len(state.queue)


async def play_via_audacious(
    state: PlaylistState,
    playback_path: str,
    deps: NowPlayingDependencies,
    *,
    current_path: str | None = None,
) -> None:
    """Stop current playback, play a new path via Audacious, and refresh the monitor source."""
    await asyncio.to_thread(deps.audacious_stop)
    started = await asyncio.to_thread(deps.audacious_play, playback_path)
    if not started:
        return
    if current_path is not None:
        state.set_current_path(current_path)
    deps.setup_monitor_source(state)


async def send_now_playing_embed(
    ctx: Any,
    state: PlaylistState,
    url: str,
    deps: NowPlayingDependencies,
    *,
    title: str,
    color: Any,
    footer: str,
    author: str = "",
    extra_fields: list[tuple[str, str]] | None = None,
) -> None:
    """Send a standardized now-playing embed and register it for reactions."""
    pos, total = queue_position(state)
    embed = deps.embed_factory(title=title[:256], color=color)
    if author:
        embed.add_field(name="Composer", value=author, inline=True)
    for field_name, field_value in extra_fields or []:
        if field_value:
            embed.add_field(name=field_name, value=field_value, inline=True)
    embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
    embed.set_footer(text=footer)
    np_msg = await ctx.send(embed=embed)
    deps.register_np_message(np_msg.id, url, title, author)
