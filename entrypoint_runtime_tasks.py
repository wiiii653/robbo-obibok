"""Entrypoint-facing runtime task helpers."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine

from app_config import AppConfig
from app_state import PlaylistState
from entrypoint_bridge import EntrypointComponentAccess
from entrypoint_state_protocols import EntrypointRuntimeStateProtocol
from entrypoint_tasks import health_watchdog_entry, monitor_playback_entry

if TYPE_CHECKING:
    from discord.ext import commands


@dataclass(slots=True)
class EntrypointRuntimeTasks:
    bot: "commands.Bot"
    state: EntrypointRuntimeStateProtocol
    logger: logging.Logger
    app_cfg_getter: Callable[[], AppConfig]
    components: EntrypointComponentAccess
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    compute_timeout_seconds: Callable[..., int]
    is_gme_format_path: Callable[[str | None], bool]
    is_playing: Callable[[], bool]
    pre_download_next: Callable[[PlaylistState], Coroutine[Any, Any, None]]
    should_advance_after_stop: Callable[..., tuple[bool, float | None]]
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]]
    should_disconnect_for_empty_channel: Callable[..., tuple[bool, float | None]]
    should_force_timeout_stop: Callable[[int, int], bool]
    should_start_predownload: Callable[..., bool]
    skip_to_next: Callable[[object], Awaitable[None]]
    stop_all_players: Callable[[], None]
    ensure_audacious: Callable[[], None]
    setup_virtual_sink: Callable[[], None]

    async def monitor_playback(self, ctx: object, vc: object, guild_id: int) -> None:
        component_bundle = self.components.require()
        assert self.state.shutdown_flag is not None
        await monitor_playback_entry(
            ctx,
            vc,
            guild_id,
            active_streams=component_bundle.active_streams,
            auto_empty_timeout=self.app_cfg_getter().auto_empty_timeout,
            sink_name=self.app_cfg_getter().sink_name,
            audacious_song=self.audacious_song,
            audacious_stop=self.audacious_stop,
            compute_timeout_seconds=self.compute_timeout_seconds,
            get_state=component_bundle.app_services.get_state,
            is_gme_format_path=self.is_gme_format_path,
            is_playing=self.is_playing,
            pre_download_next=self.pre_download_next,
            save_queue=component_bundle.app_services.save_queue,
            should_advance_after_stop=self.should_advance_after_stop,
            should_confirm_output_drop=self.should_confirm_output_drop,
            should_disconnect_for_empty_channel=self.should_disconnect_for_empty_channel,
            should_force_timeout_stop=self.should_force_timeout_stop,
            should_start_predownload=self.should_start_predownload,
            shutdown_flag=self.state.shutdown_flag,
            skip_to_next=self.skip_to_next,
            stop_all_players=self.stop_all_players,
            logger=self.logger,
        )

    async def fetch_metadata_background(self) -> None:
        playback_service = self.components.require().playback_service
        assert playback_service is not None
        await playback_service.fetch_metadata_background()

    async def health_watchdog(self) -> None:
        await health_watchdog_entry(
            self.bot,
            sink_name=self.app_cfg_getter().sink_name,
            ensure_audacious=self.ensure_audacious,
            setup_virtual_sink=self.setup_virtual_sink,
            logger=self.logger,
        )
