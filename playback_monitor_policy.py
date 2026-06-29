"""Playback monitor transition helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from app_state import PlaylistState

if TYPE_CHECKING:
    from stream_runtime import MonitorAudioSource

@dataclass(slots=True)
class MonitorPolicyDependencies:
    ACTIVE_STREAMS: dict[int, "MonitorAudioSource"]
    AUTO_EMPTY_TIMEOUT: int
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    compute_timeout_seconds: Callable[..., int]
    get_output_length: Callable[[], int]
    get_song_length: Callable[[], int]
    get_state: Callable[[int], PlaylistState]
    is_gme_format_path: Callable[[str], bool]
    logger: logging.Logger
    run_sync: Callable[..., Awaitable[object]]
    should_advance_after_stop: Callable[..., tuple[bool, float | None]]
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]]
    should_force_timeout_stop: Callable[[int, int], bool]
    skip_to_next: Callable[[object], Awaitable[None]]
    stop_all_players: Callable[[], None]


async def disconnect_for_empty_channel(ctx, vc, guild_id: int, deps: MonitorPolicyDependencies) -> bool:
    deps.logger.info("Channel empty for %ds, disconnecting", deps.AUTO_EMPTY_TIMEOUT)
    stream = deps.ACTIVE_STREAMS.pop(guild_id, None)
    if stream:
        stream.cleanup()
    await deps.run_sync(deps.stop_all_players)
    await vc.disconnect()
    await ctx.send("🌙 No one listening. Stopping Radio.")
    return True


async def finish_playlist(ctx, vc, guild_id: int, deps: MonitorPolicyDependencies) -> bool:
    stream = deps.ACTIVE_STREAMS.pop(guild_id, None)
    if stream:
        stream.cleanup()
    if vc.is_connected():
        await vc.disconnect()
    await ctx.send("Playlist ended. Use !play to restart.")
    return True


async def handle_playing_state(
    ctx,
    vc,
    guild_id: int,
    state: PlaylistState,
    now: float,
    deps: MonitorPolicyDependencies,
    *,
    grace_seconds: int,
    cached_sap_path: str | None,
    cached_song_length: int,
    last_output_len: int,
    drop_confirmed_since: float | None,
) -> tuple[bool, str | None, int, int, float | None]:
    if state.current_sap_path != cached_sap_path:
        cached_sap_path = state.current_sap_path
        cached_song_length = -1
        last_output_len = -1
        drop_confirmed_since = None
    secs = await deps.run_sync(deps.get_output_length)
    if cached_song_length < 0:
        cached_song_length = await deps.run_sync(deps.get_song_length)
    try:
        is_gme_format = deps.is_gme_format_path(state.current_sap_path)
        output_drop_confirmed, drop_confirmed_since = deps.should_confirm_output_drop(
            last_output_len, secs, drop_confirmed_since, now, grace_seconds, is_gme_format=is_gme_format
        )
        if output_drop_confirmed:
            deps.logger.info(
                "Output length drop confirmed (%ds): %d→%d — forcing skip",
                grace_seconds,
                last_output_len,
                secs,
            )
            await deps.run_sync(deps.audacious_stop)
            if state.loop or state.index < len(state.queue) - 1:
                await deps.skip_to_next(ctx)
                return True, cached_sap_path, cached_song_length, last_output_len, drop_confirmed_since
            finished = await finish_playlist(ctx, vc, guild_id, deps)
            return finished, cached_sap_path, cached_song_length, last_output_len, drop_confirmed_since
        last_output_len = secs
        timeout_secs = deps.compute_timeout_seconds(cached_song_length, is_gme_format=is_gme_format)
        if deps.should_force_timeout_stop(secs, timeout_secs):
            deps.logger.info("Track exceeded %ds fallback (%ds), force-stopping", timeout_secs, secs)
            await deps.run_sync(deps.audacious_stop)
            if state.loop or state.index < len(state.queue) - 1:
                deps.logger.info("monitor_playback: skip_to_next (timeout_exceeded)")
                await deps.skip_to_next(ctx)
                return True, cached_sap_path, cached_song_length, last_output_len, drop_confirmed_since
            finished = await finish_playlist(ctx, vc, guild_id, deps)
            return finished, cached_sap_path, cached_song_length, last_output_len, drop_confirmed_since
    except (ValueError, OSError):
        pass
    return False, cached_sap_path, cached_song_length, last_output_len, drop_confirmed_since


async def handle_idle_state(
    ctx,
    vc,
    guild_id: int,
    now: float,
    deps: MonitorPolicyDependencies,
    *,
    not_playing_since,
):
    still_loaded = await deps.run_sync(lambda: bool(deps.audacious_song()))
    should_advance, not_playing_since = deps.should_advance_after_stop(
        not_playing_since, now, 3, still_loaded=still_loaded
    )
    if not should_advance:
        return False, not_playing_since
    state = deps.get_state(guild_id)
    if state.loop or state.index < len(state.queue) - 1:
        await deps.skip_to_next(ctx)
        return True, not_playing_since
    finished = await finish_playlist(ctx, vc, guild_id, deps)
    return finished, not_playing_since
