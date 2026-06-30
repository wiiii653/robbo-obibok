"""Queue/session orchestration helpers."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Protocol, cast

from archive_catalog import CollectionInfo
from app_state import PlaylistState

if TYPE_CHECKING:
    import discord
    from discord.ext import commands

    class PlaybackSessionContext(commands.Context[commands.Bot]):
        guild: discord.Guild
        author: discord.Member
        voice_client: discord.VoiceClient | None
else:
    class PlaybackSessionContext(Protocol):
        guild: object
        author: object
        voice_client: object | None


class EmbedFactoryProtocol(Protocol):
    def __call__(self, **kwargs: Any) -> "discord.Embed": ...


@dataclass(slots=True)
class PlaybackSessionDependencies:
    PLAYBACK_LOOP: bool
    PLAYBACK_SHUFFLE: bool
    bot: "commands.Bot"
    embed_factory: EmbedFactoryProtocol
    classify_track_route: Callable[..., dict[str, str]]
    clear_predownload_state: Callable[..., None]
    download_sap: Callable[..., Awaitable[str]]
    ensure_tracks: Callable[[PlaylistState], Awaitable[bool]]
    filter_blacklisted: Callable[[list[str], int], list[str]]
    get_collection_info: Callable[[str], CollectionInfo]
    get_state: Callable[[int], PlaylistState]
    get_snes_game: Callable[[str], dict[str, object] | None]
    has_snes_game: Callable[[str], bool]
    load_asma_local_cache: Callable[[], list[str] | None]
    load_queue: Callable[[int], dict[str, object] | None]
    log: logging.Logger
    monitor_playback: Callable[..., Coroutine[Any, Any, None]]
    parse_sap_header: Callable[[str], dict[str, str]]
    playback_handlers: dict[str, Callable[..., Awaitable[bool]]]
    prepare_playback_queue: Callable[..., dict[str, object]]
    register_np_message: Callable[[int, str, str, str], None]
    save_queue: Callable[[PlaylistState], None]
    apply_queue_state: Callable[[PlaylistState, dict[str, object]], bool]
    place_track_in_queue: Callable[[list[str], str], tuple[list[str], int]]


@dataclass(slots=True)
class MetadataSessionDependencies:
    asma_dir: str
    has_metadata_entry: Callable[[str], bool]
    load_asma_local_cache: Callable[[], list[str] | None]
    log: logging.Logger
    metadata_index_size: Callable[[], int]
    parse_sap_header: Callable[[str], dict[str, str]]
    save_metadata_cache: Callable[[dict[str, dict[str, str]]], None]
    snapshot_metadata_index: Callable[[], dict[str, dict[str, str]]]
    store_metadata_entry: Callable[[str, dict[str, str]], None]


async def pre_download_next(state: PlaylistState, deps: PlaybackSessionDependencies) -> None:
    url = state.next_queue_url()
    if url is None:
        return
    if "://" not in url:
        return
    try:
        filepath = await deps.download_sap(url, retries=1)
        state.set_predownload(filepath, url)
    except asyncio.CancelledError:
        raise
    except Exception:
        deps.clear_predownload_state(state)
    finally:
        state.set_predownload_task(None)


async def start_targeted_playback_session(
    ctx: object,
    state: PlaylistState,
    url: str,
    deps: PlaybackSessionDependencies,
) -> bool:
    ctx = cast(PlaybackSessionContext, ctx)
    assert ctx.guild is not None
    author = cast("discord.Member", ctx.author)
    assert author.voice is not None
    assert author.voice.channel is not None
    if ctx.voice_client:
        await cast("discord.VoiceClient", ctx.voice_client).disconnect()
    vc: discord.VoiceClient = cast("discord.VoiceClient", await author.voice.channel.connect())
    state.bind_voice_context(guild_id=ctx.guild.id, ctx=ctx, vc=vc)
    state.set_loop_enabled(deps.PLAYBACK_LOOP)
    deps.clear_predownload_state(state)

    base_queue = deps.filter_blacklisted(list(state.tracks), author.id)
    if deps.PLAYBACK_SHUFFLE:
        random.shuffle(base_queue)
    queue, index = deps.place_track_in_queue(base_queue, url)
    state.set_queue_state(queue, index)

    if await play_current_track(ctx, deps):
        deps.save_queue(state)
        if state.monitor_task and not state.monitor_task.done():
            state.monitor_task.cancel()
        state.set_monitor_task(deps.bot.loop.create_task(deps.monitor_playback(ctx, vc, ctx.guild.id)))
        return True
    return False


async def play_current_track(ctx: object, deps: PlaybackSessionDependencies) -> bool:
    ctx = cast(PlaybackSessionContext, ctx)
    assert ctx.guild is not None
    state = deps.get_state(ctx.guild.id)
    url = state.current_queue_url()
    if url is None:
        await ctx.send("Queue empty. Use !play to rebuild.")
        return False

    deps.log.info("play_current_track: url=%s, index=%d", str(url)[:80], state.index)
    route = deps.classify_track_route(url, state.collection_mode, snes_known=deps.has_snes_game(url))

    if route["handler"] == "spc":
        game_entry = deps.get_snes_game(url)
        if not game_entry:
            await ctx.send("❌ Unknown SNES track")
            return False
        return await deps.playback_handlers["spc"](ctx, state, game_entry)

    await ctx.send(f"Loading... `{url.split('/')[-1]}`")
    try:
        if state.collection_mode != route["mode"]:
            state.set_collection_mode(route["mode"])
            await deps.ensure_tracks(state)
        return await deps.playback_handlers[route["handler"]](ctx, state, url)
    except Exception as exc:
        await ctx.send(f"Error playing `{url}`: {exc}")
        return False


async def skip_to_next(
    ctx: object,
    deps: PlaybackSessionDependencies,
    play_subsong: Callable[[object, PlaylistState, int], Awaitable[bool]],
    cleanup_subsong_temp_wavs: Callable[[PlaylistState], None],
) -> None:
    ctx = cast(PlaybackSessionContext, ctx)
    assert ctx.guild is not None
    state = deps.get_state(ctx.guild.id)
    if not state.queue:
        await ctx.send("No tracks in queue. Use !play.")
        return

    if state.subsong_total > 0 and state.subsong_path:
        next_sub = state.subsong_current + 1
        if next_sub < state.subsong_total:
            deps.log.info(
                "Subsong: advancing to part %d/%d of %s",
                next_sub + 1,
                state.subsong_total,
                os.path.basename(state.subsong_path),
            )
            ok = await play_subsong(ctx, state, next_sub)
            if ok:
                name = os.path.basename(state.subsong_path).rsplit(".", 1)[0]
                position = state.current_queue_position()
                embed = deps.embed_factory(title=f"{name} (part {next_sub + 1}/{state.subsong_total})")
                if position is not None:
                    embed.add_field(name="Position", value=f"{position[0]}/{position[1]}", inline=True)
                embed.set_footer(text=f"Tiny Music — curated demoscene modules · {state.subsong_total} parts")
                np_msg = await ctx.send(embed=embed)
                deps.register_np_message(np_msg.id, state.subsong_path, name, "")
                return
            deps.log.error("Subsong %d conversion failed, skipping to next queue item", next_sub)
            cleanup_subsong_temp_wavs(state)
        else:
            cleanup_subsong_temp_wavs(state)

    state.advance_queue_index()
    if not state.contains_queue_index(state.index):
        if state.loop:
            random.shuffle(state.queue)
            state.set_queue_state(state.queue, 0, loop=state.loop)
            await ctx.send("🔁 Loop: reshuffling playlist...")
        else:
            await ctx.send("Playlist ended.")
            if state.vc and state.vc.is_connected():
                await cast("discord.VoiceClient", state.vc).disconnect()
            return

    deps.save_queue(state)
    await play_current_track(state.ctx or ctx, deps)


async def auto_play_after_switch(
    ctx: object,
    state: PlaylistState,
    deps: PlaybackSessionDependencies,
) -> None:
    ctx = cast(PlaybackSessionContext, ctx)
    assert ctx.guild is not None
    author = cast("discord.Member", ctx.author)
    if not author.voice or not state.tracks:
        return
    deps.log.info("auto_play_after_switch: queue_len=%d, index=%d", state.queue_length(), state.index)
    queue = deps.filter_blacklisted(list(state.tracks), author.id)
    if deps.PLAYBACK_SHUFFLE:
        random.shuffle(queue)
    state.set_queue_state(queue, 0, loop=deps.PLAYBACK_LOOP)

    if not state.vc or not state.vc.is_connected():
        try:
            assert author.voice.channel is not None
            vc: discord.VoiceClient = cast("discord.VoiceClient", await author.voice.channel.connect())
            state.bind_voice_context(guild_id=ctx.guild.id, ctx=ctx, vc=vc)
        except Exception as exc:
            await ctx.send(f"❌ Could not connect: {exc}")
            return
    else:
        state.bind_voice_context(guild_id=ctx.guild.id, ctx=ctx, vc=state.vc)
    result = await play_current_track(ctx, deps)
    deps.log.info("auto_play_after_switch: play_current_track returned %s", result)
    if result:
        deps.save_queue(state)
        if state.monitor_task and not state.monitor_task.done():
            state.monitor_task.cancel()
        state.set_monitor_task(deps.bot.loop.create_task(deps.monitor_playback(ctx, state.vc, ctx.guild.id)))


async def fetch_metadata_background(bot: "commands.Bot", deps: MetadataSessionDependencies) -> None:
    await bot.wait_until_ready()
    await asyncio.sleep(30)
    cached = deps.load_asma_local_cache()
    if not cached:
        return
    missing = [path for path in cached if not deps.has_metadata_entry(path)]
    if not missing:
        deps.log.info("Metadata index complete: %d tracks", deps.metadata_index_size())
        return
    deps.log.info("Fetching metadata for %d local ASMA tracks...", len(missing))
    fetched = 0
    for path in missing:
        if deps.has_metadata_entry(path):
            continue
        full = os.path.join(deps.asma_dir, path)
        if not os.path.exists(full):
            continue
        meta = deps.parse_sap_header(full)
        if meta:
            deps.store_metadata_entry(path, meta)
            fetched += 1
        if fetched > 0 and fetched % 100 == 0:
            deps.log.info("Metadata: %d/%d", fetched, len(missing))
            deps.save_metadata_cache(deps.snapshot_metadata_index())
    deps.save_metadata_cache(deps.snapshot_metadata_index())
    deps.log.info("Metadata index: %d tracks total", deps.metadata_index_size())
