"""Entrypoint helpers for long-running playback and watchdog tasks."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from app_state import PlaylistState
from playback_process import audtool_output_length, audtool_song_length

if TYPE_CHECKING:
    from discord.ext import commands
    from stream_runtime import MonitorAudioSource


async def monitor_playback_entry(
    ctx: object,
    vc: object,
    guild_id: int,
    *,
    active_streams: dict[int, "MonitorAudioSource"],
    auto_empty_timeout: int,
    sink_name: str,
    audacious_song: Callable[[], str],
    audacious_stop: Callable[[], None],
    compute_timeout_seconds: Callable[..., int],
    get_state: Callable[[int], PlaylistState],
    is_gme_format_path: Callable[[str | None], bool],
    is_playing: Callable[[], bool],
    pre_download_next: Callable[[PlaylistState], Awaitable[None]],
    save_queue: Callable[[PlaylistState], None],
    should_advance_after_stop: Callable[..., tuple[bool, float | None]],
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]],
    should_disconnect_for_empty_channel: Callable[..., tuple[bool, float | None]],
    should_force_timeout_stop: Callable[..., bool],
    should_start_predownload: Callable[..., bool],
    shutdown_flag: asyncio.Event,
    skip_to_next: Callable[[object], Awaitable[None]],
    stop_all_players: Callable[[], None],
    logger: logging.Logger,
) -> None:
    from playback_runtime import MonitorDependencies, monitor_playback as runtime_monitor_playback

    async def _run_sync(func, *args):
        return await asyncio.to_thread(func, *args)

    deps = MonitorDependencies(
        ACTIVE_STREAMS=active_streams,
        AUTO_EMPTY_TIMEOUT=auto_empty_timeout,
        SINK_NAME=sink_name,
        audacious_song=audacious_song,
        audacious_stop=audacious_stop,
        compute_timeout_seconds=compute_timeout_seconds,
        get_state=get_state,
        is_gme_format_path=is_gme_format_path,
        is_playing=is_playing,
        pre_download_next=pre_download_next,
        save_queue=save_queue,
        should_advance_after_stop=should_advance_after_stop,
        should_confirm_output_drop=should_confirm_output_drop,
        should_disconnect_for_empty_channel=should_disconnect_for_empty_channel,
        should_force_timeout_stop=should_force_timeout_stop,
        should_start_predownload=should_start_predownload,
        shutdown_flag=shutdown_flag,
        skip_to_next=skip_to_next,
        stop_all_players=stop_all_players,
        get_output_length=audtool_output_length,
        get_song_length=audtool_song_length,
        logger=logger,
        run_sync=_run_sync,
    )
    await runtime_monitor_playback(ctx, vc, guild_id, deps)


async def health_watchdog_entry(
    bot: "commands.Bot",
    *,
    sink_name: str,
    ensure_audacious: Callable[[], None],
    setup_virtual_sink: Callable[[], None],
    logger: logging.Logger,
) -> None:
    from playback_runtime import WatchdogDependencies, health_watchdog as runtime_health_watchdog

    async def _run_sync(func, *args):
        return await asyncio.to_thread(func, *args)

    deps = WatchdogDependencies(
        SINK_NAME=sink_name,
        ensure_audacious=ensure_audacious,
        setup_virtual_sink=setup_virtual_sink,
        logger=logger,
        run_sync=_run_sync,
    )
    await runtime_health_watchdog(bot, deps)
