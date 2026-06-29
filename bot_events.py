"""Discord event registration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class CoreEventDependencies:
    AUTO_START_CHANNEL: str
    PLAYBACK_LOOP: bool
    PLAYBACK_SHUFFLE: bool
    apply_queue_state: Callable[[Any, dict[str, object]], bool]
    ensure_tracks: Callable[[Any], Awaitable[bool]]
    get_collection_info: Callable[[str], Any]
    get_state: Callable[[int], Any]
    load_queue: Callable[[int], dict | None]
    log: Any
    log_preloaded_cache: Callable[[str, list[str] | None], None]
    load_asma_local_cache: Callable[[], list[str] | None]
    load_hvsc_local_cache: Callable[[], list[str] | None]
    monitor_playback: Callable[..., Awaitable[None]]
    play_current_track: Callable[[Any], Awaitable[bool]]
    prepare_playback_queue: Callable[..., dict[str, object]]
    run_startup_steps: Callable[[list[tuple[str, Callable[[], Any]]]], Awaitable[None]]
    save_queue: Callable[[Any], None]
    schedule_background_tasks: Callable[[list[Callable[[], Awaitable[None]]]], None]


def register_core_events(bot, deps: CoreEventDependencies, *, health_watchdog, fetch_metadata_background):
    @bot.event
    async def on_ready():
        deps.log.info("Ready: %s", bot.user)
        await deps.run_startup_steps()
        deps.log_preloaded_cache("ASMA", deps.load_asma_local_cache())
        deps.log_preloaded_cache("HVSC", deps.load_hvsc_local_cache())
        deps.schedule_background_tasks([health_watchdog, fetch_metadata_background])

    @bot.event
    async def on_voice_state_update(member, before, after):
        if not deps.AUTO_START_CHANNEL or member.bot:
            return
        if before.channel == after.channel:
            return
        if after.channel is None:
            return
        if after.channel.name != deps.AUTO_START_CHANNEL:
            return
        if member.guild.voice_client:
            return

        deps.log.info("Auto-start: %s joined %s", member.display_name, after.channel.name)
        try:
            vc = await after.channel.connect()
            state = deps.get_state(member.guild.id)
            state.bind_voice_context(guild_id=member.guild.id, ctx=None, vc=vc)
            state.set_loop_enabled(deps.PLAYBACK_LOOP)

            if not state.tracks:
                await deps.ensure_tracks(state)
            if not state.tracks:
                deps.log.warning("Auto-start: no tracks available")
                await vc.disconnect()
                return

            saved = deps.load_queue(member.guild.id)
            queue_state = deps.prepare_playback_queue(
                state.tracks,
                saved,
                state.collection_mode,
                deps.PLAYBACK_LOOP,
                shuffle_enabled=deps.PLAYBACK_SHUFFLE,
                min_queue_length=10,
            )
            deps.apply_queue_state(state, queue_state)
            info = deps.get_collection_info(state.collection_mode)
            ctx = await bot.get_context(await after.channel.send(f"📻 **Auto-starting {info.station}...**"))
            state.bind_voice_context(guild_id=member.guild.id, ctx=ctx, vc=vc)

            if await deps.play_current_track(ctx):
                deps.save_queue(state)
                if state.monitor_task and not state.monitor_task.done():
                    state.monitor_task.cancel()
                state.set_monitor_task(bot.loop.create_task(deps.monitor_playback(ctx, vc, member.guild.id)))
        except Exception as exc:
            deps.log.error("Auto-start failed: %s", exc)

    return on_ready, on_voice_state_update
