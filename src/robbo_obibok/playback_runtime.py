"""Playback supervision and watchdog policy."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Protocol, TypeVar, cast

from domain_state import PlaylistState
from playback_monitor_policy import (
    MonitorPolicyDependencies,
    disconnect_for_empty_channel,
    handle_idle_state,
    handle_playing_state,
)

if TYPE_CHECKING:
    import discord
    from discord.ext import commands
    from stream_runtime import MonitorAudioSource


T = TypeVar("T")


class RunSyncProtocol(Protocol):
    def __call__(self, func: Callable[..., T], *args: object) -> Awaitable[T]: ...


@dataclass(slots=True)
class MonitorDependencies:
    ACTIVE_STREAMS: dict[int, "MonitorAudioSource"]
    AUTO_EMPTY_TIMEOUT: int
    SINK_NAME: str
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    compute_timeout_seconds: Callable[..., int]
    get_state: Callable[[int], PlaylistState]
    is_gme_format_path: Callable[[str | None], bool]
    is_playing: Callable[[], bool]
    pre_download_next: Callable[[PlaylistState], Coroutine[Any, Any, None]]
    save_queue: Callable[[PlaylistState], None]
    should_advance_after_stop: Callable[..., tuple[bool, float | None]]
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]]
    should_disconnect_for_empty_channel: Callable[..., tuple[bool, float | None]]
    should_force_timeout_stop: Callable[[int, int], bool]
    should_start_predownload: Callable[..., bool]
    shutdown_flag: asyncio.Event
    skip_to_next: Callable[[object], Awaitable[None]]
    stop_all_players: Callable[[], None]
    get_output_length: Callable[[], int]
    get_song_length: Callable[[], int]
    logger: logging.Logger
    run_sync: RunSyncProtocol
    task_manager: Any | None = None  # TaskManager (runtime_task_manager)
    release_lease: Callable[[], None] | None = None


@dataclass(slots=True)
class WatchdogDependencies:
    SINK_NAME: str
    ensure_audacious: Callable[[], None]
    setup_virtual_sink: Callable[[], None]
    logger: logging.Logger
    run_sync: RunSyncProtocol


async def monitor_playback(
    ctx: object,
    vc: object,
    guild_id: int,
    deps: MonitorDependencies,
) -> None:
    ctx = cast("commands.Context[commands.Bot]", ctx)
    vc = cast("discord.VoiceClient", vc)
    empty_since = None
    not_playing_since = None
    drop_confirmed_since = None
    grace_seconds = 3
    poll_interval = 2
    last_output_len = -1
    cached_song_length = -1
    cached_sap_path: str | None = "__init__"
    policy_deps = MonitorPolicyDependencies(
        ACTIVE_STREAMS=deps.ACTIVE_STREAMS,
        AUTO_EMPTY_TIMEOUT=deps.AUTO_EMPTY_TIMEOUT,
        audacious_song=deps.audacious_song,
        audacious_stop=deps.audacious_stop,
        compute_timeout_seconds=deps.compute_timeout_seconds,
        get_output_length=deps.get_output_length,
        get_song_length=deps.get_song_length,
        get_state=deps.get_state,
        is_gme_format_path=deps.is_gme_format_path,
        logger=deps.logger,
        run_sync=deps.run_sync,
        should_advance_after_stop=deps.should_advance_after_stop,
        should_confirm_output_drop=deps.should_confirm_output_drop,
        should_force_timeout_stop=deps.should_force_timeout_stop,
        skip_to_next=deps.skip_to_next,
        stop_all_players=deps.stop_all_players,
        release_lease=deps.release_lease,
    )
    while vc.is_connected() and not deps.shutdown_flag.is_set():
        try:
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            break
        state = deps.get_state(guild_id)
        now = time.time()

        if vc.channel and len(vc.channel.members) <= 1:
            should_disconnect, empty_since = deps.should_disconnect_for_empty_channel(
                len(vc.channel.members), empty_since, now, deps.AUTO_EMPTY_TIMEOUT
            )
            if should_disconnect:
                await disconnect_for_empty_channel(ctx, vc, guild_id, policy_deps)
                break
        else:
            empty_since = None

        playing = await deps.run_sync(deps.is_playing)
        if playing and state.current_track_path:
            not_playing_since = None
            handled, cached_sap_path, cached_song_length, last_output_len, drop_confirmed_since = (
                await handle_playing_state(
                    ctx,
                    vc,
                    guild_id,
                    state,
                    now,
                    policy_deps,
                    grace_seconds=grace_seconds,
                    cached_sap_path=cached_sap_path,
                    cached_song_length=cached_song_length,
                    last_output_len=last_output_len,
                    drop_confirmed_since=drop_confirmed_since,
                )
            )
            if handled:
                if vc.is_connected() and not deps.shutdown_flag.is_set():
                    continue
                break

        if playing:
            not_playing_since = None
            next_url = None
            if state.queue and (state.index + 1 < len(state.queue) or state.loop):
                next_url = state.queue[(state.index + 1) % len(state.queue)]
            if deps.should_start_predownload(
                len(state.queue),
                state.index,
                loop_enabled=state.loop,
                predownload_ready=state.pre_downloaded is not None,
                predownload_inflight=state.pre_download_task is not None,
                next_url=next_url,
            ):
                if deps.task_manager is not None:
                    task = deps.task_manager.create("predownload", deps.pre_download_next(state))
                else:
                    task = asyncio.create_task(deps.pre_download_next(state))
                state.set_predownload_task(task)
        else:
            handled, not_playing_since = await handle_idle_state(
                ctx, vc, guild_id, now, policy_deps, not_playing_since=not_playing_since
            )
            if handled:
                if vc.is_connected() and not deps.shutdown_flag.is_set():
                    continue
                break

    stream = deps.ACTIVE_STREAMS.pop(guild_id, None)
    if stream:
        stream.cleanup()


async def health_watchdog(bot: "commands.Bot", deps: WatchdogDependencies) -> None:
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(30)
        try:
            process_result = await deps.run_sync(
                lambda: subprocess.run(["pgrep", "-x", "audacious"], capture_output=True)
            )
            if process_result.returncode != 0:
                deps.logger.warning("Audacious not running, restarting...")
                await deps.run_sync(deps.ensure_audacious)
            sink_result = await deps.run_sync(
                lambda: subprocess.run(["pactl", "list", "sinks", "short"], capture_output=True, text=True)
            )
            if deps.SINK_NAME not in sink_result.stdout:
                deps.logger.warning("Virtual sink missing, recreating...")
                await deps.run_sync(deps.setup_virtual_sink)
        except Exception as exc:
            deps.logger.error("Watchdog error: %s", exc)
