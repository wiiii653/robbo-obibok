"""Playback and collection command registration."""

from __future__ import annotations

import asyncio
import random
import re
import subprocess
from typing import TYPE_CHECKING, Protocol, cast

import aiohttp
import discord
from discord.ext import commands

from bot_dependencies import PlaybackCommandDependencies


if TYPE_CHECKING:
    class PlaybackContext(commands.Context[commands.Bot]):
        guild: discord.Guild
        author: discord.Member
        voice_client: discord.VoiceClient | None
else:
    class PlaybackContext(Protocol):
        guild: discord.Guild
        author: discord.Member
        voice_client: discord.VoiceClient | None

        async def send(self, *args: object, **kwargs: object) -> discord.Message: ...


def _collection_color(color_name: str) -> discord.Color:
    if color_name.startswith("#"):
        return discord.Color.from_str(color_name)
    return getattr(discord.Color, color_name)()


def register_playback_commands(bot: commands.Bot, deps: PlaybackCommandDependencies) -> None:
    async def persist_queue(ctx: PlaybackContext, state) -> bool:
        try:
            await asyncio.to_thread(deps.save_queue, state)
            return True
        except OSError as exc:
            deps.log.error("Queue persistence failed: %s", exc)
            await ctx.send("❌ Queue state could not be saved. Check bot storage permissions.")
            return False

    @bot.command(aliases=["radio", "start", "pl"])
    async def play(ctx: PlaybackContext, *, query: str = ""):
        if not ctx.author.voice:
            return await ctx.send("Join a voice channel first!")

        state = deps.get_state(ctx.guild.id)

        if query.isdigit():
            idx = int(query) - 1
            if not state.search_results or idx < 0 or idx >= len(state.search_results):
                return await ctx.send("Invalid number. Use !search first.")
            if not state.tracks:
                await deps.ensure_tracks(state)
            await deps.start_targeted_playback_session(ctx, state, state.search_results[idx])
            return

        if query:
            if not state.tracks:
                await deps.ensure_tracks(state)
            query_lower = query.lower()
            matches = [
                u for u in state.tracks
                if query_lower in u.split("/")[-1].rsplit(".", 1)[0].replace("_", " ").lower()
            ]
            if matches:
                await deps.start_targeted_playback_session(ctx, state, matches[0])
                return
            return await ctx.send(f"No tracks matching `{query}`. Try !search.")

        if ctx.voice_client:
            await ctx.voice_client.disconnect()

        assert ctx.author.voice is not None
        assert ctx.author.voice.channel is not None
        vc: discord.VoiceClient = cast(discord.VoiceClient, await ctx.author.voice.channel.connect())
        state = deps.get_state(ctx.guild.id)
        state.bind_voice_context(guild_id=ctx.guild.id, ctx=ctx, vc=vc)
        state.set_loop_enabled(deps.PLAYBACK_LOOP)
        deps.clear_predownload_state(state)

        info = deps.get_collection_info(state.collection_mode)
        await ctx.send(f"🎛️ **{info.station} starting...**")

        if not state.tracks:
            await deps.ensure_tracks(state)

        track_count = len(state.tracks) if state.tracks else 0
        await ctx.send(f"📀 Ready with **{track_count}** tracks!")

        saved_queue = await asyncio.to_thread(deps.load_queue, ctx.guild.id)
        queue_state = deps.prepare_playback_queue(
            state.tracks,
            saved_queue,
            state.collection_mode,
            deps.PLAYBACK_LOOP,
            shuffle_enabled=deps.PLAYBACK_SHUFFLE,
            track_filter=lambda tracks: deps.filter_blacklisted(tracks, ctx.author.id),
        )
        if deps.apply_queue_state(state, queue_state):
            await ctx.send("📋 Restored previous queue.")

        if await deps.play_current_track(ctx):
            await persist_queue(ctx, state)
            if state.monitor_task and not state.monitor_task.done():
                state.monitor_task.cancel()
            state.set_monitor_task(bot.loop.create_task(deps.monitor_playback(ctx, vc, ctx.guild.id)))

    @bot.command(aliases=["st"])
    @deps.mod_only()
    async def stop(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        await deps.stop_state_streams(state)
        await asyncio.get_event_loop().run_in_executor(None, deps.stop_all_players)
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        state.clear_voice_client()
        state.clear_queue_state()
        await persist_queue(ctx, state)
        await ctx.send("⏹️ Stopped.")

    @bot.command(aliases=["next", "nt"])
    async def skip(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send("Nothing playing.")
        await deps.skip_to_next(ctx)

    @bot.command()
    async def np(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        if not await asyncio.to_thread(deps.is_playing):
            return await ctx.send("Nothing playing right now.")
        track = await asyncio.get_event_loop().run_in_executor(None, deps.audacious_song)
        position = state.current_queue_position()
        meta = {}
        if state.current_track_path:
            if state.current_track_path.lower().endswith(".sid"):
                try:
                    with open(state.current_track_path, "rb") as handle:
                        meta = deps.parse_sid_header(handle.read(0x76))
                except Exception:
                    meta = {}
            else:
                meta = deps.parse_sap_header(state.current_track_path)
        name = meta.get("name", meta.get("NAME", track))
        author = meta.get("author", "") or meta.get("AUTHOR", "")
        copyright_info = meta.get("copyright", "")
        info = deps.get_collection_info(state.collection_mode)
        embed = discord.Embed(title=f"Now Playing: {name}", color=_collection_color(info.color))
        if author:
            embed.add_field(name="Composer", value=author, inline=True)
        if copyright_info:
            embed.add_field(name="Copyright", value=copyright_info, inline=True)
        if position is not None:
            embed.add_field(name="Position", value=f"{position[0]}/{position[1]}", inline=True)
        elapsed_r = await asyncio.get_event_loop().run_in_executor(
            None, lambda: subprocess.run(["audtool", "current-song-output-length-seconds"], capture_output=True, text=True)
        )
        total_r = await asyncio.get_event_loop().run_in_executor(
            None, lambda: subprocess.run(["audtool", "current-song-length-seconds"], capture_output=True, text=True)
        )
        try:
            elapsed = int(elapsed_r.stdout.strip())
            total_s = int(total_r.stdout.strip())
            if total_s > 0:
                elapsed_m, elapsed_s = divmod(elapsed, 60)
                total_m, total_ss = divmod(total_s, 60)
                embed.add_field(name="Duration", value=f"{elapsed_m}:{elapsed_s:02d} / {total_m}:{total_ss:02d}", inline=True)
        except (ValueError, OSError):
            pass
        embed.set_footer(text=info.footer)
        np_msg = await ctx.send(embed=embed)
        deps.register_np_message(
            np_msg.id,
            state.current_queue_url() or "unknown",
            name,
            author,
        )

    @bot.command()
    async def volume(ctx: PlaybackContext, *, level: str = ""):
        if not level:
            sink = deps.SINK_NAME
            r = await asyncio.get_event_loop().run_in_executor(
                None, lambda: subprocess.run(["pactl", "get-sink-volume", sink], capture_output=True, text=True)
            )
            m = re.search(r"(\d+)%", r.stdout)
            if m:
                await ctx.send(embed=discord.Embed(title=f"🔊 Current volume: **{m.group(1)}%**", color=discord.Color.green()))
            else:
                await ctx.send("Could not read volume.")
            return
        try:
            vol = int(level)
            if vol < 0 or vol > 200:
                await ctx.send("Volume must be between 0 and 200.")
                return
            sink = deps.SINK_NAME
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: subprocess.run(["pactl", "set-sink-volume", sink, f"{vol}%"], capture_output=True)
            )
            await ctx.send(embed=discord.Embed(title=f"🔊 Volume set to **{vol}%**", color=discord.Color.green()))
        except ValueError:
            await ctx.send("Usage: `!volume <0-200>` or `!volume` to show current.")

    @bot.command(aliases=["q"])
    async def queue(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send("Queue is empty. Use !play to start.")
        position = state.current_queue_position()
        if position is None:
            return await ctx.send("Nothing currently playing.")
        upcoming = state.upcoming_queue(10)
        if not upcoming:
            return await ctx.send("No upcoming tracks — this is the last one.")
        info = deps.get_collection_info(state.collection_mode)
        lines = [f"📜 **Upcoming tracks ({len(upcoming)}/{state.remaining_queue_count()} remaining)**"]
        for i, url in enumerate(upcoming, 1):
            name = url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
            if len(name) > 60:
                name = name[:57] + "..."
            lines.append(f"`{i}.` {name}")
        embed = discord.Embed(title="🎵 Queue", description="\n".join(lines), color=discord.Color.blue())
        embed.set_footer(text=info.footer)
        await ctx.send(embed=embed)

    @bot.command()
    async def sleep(ctx: PlaybackContext, *, minutes: str = ""):
        if not minutes:
            return await ctx.send("Usage: `!sleep <minutes>` — stops playback after N minutes.")
        try:
            mins = float(minutes.replace(",", "."))
            if mins <= 0:
                return await ctx.send("Time must be positive.")
            if mins > 360:
                return await ctx.send("Max 360 minutes (6 hours).")
            secs = int(mins * 60)
            embed = discord.Embed(
                title="⏰ Sleep timer set",
                description=f"Playback will stop in **{mins:.0f} minute{'s' if mins != 1 else ''}**.",
                color=discord.Color.dark_blue(),
            )
            await ctx.send(embed=embed)
            await asyncio.sleep(secs)
            state = deps.get_state(ctx.guild.id)
            if ctx.voice_client and ctx.voice_client.is_connected():
                await deps.stop_state_streams(state)
                await asyncio.get_event_loop().run_in_executor(None, deps.stop_all_players)
                await ctx.voice_client.disconnect()
                state.clear_voice_client()
                await ctx.send("🌙 **Sleep timer expired.** Radio stopped.")
        except ValueError:
            await ctx.send("Usage: `!sleep <minutes>` — e.g. `!sleep 30`")

    @bot.command(aliases=["repeat"])
    async def loop(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        state.set_loop_enabled(not state.loop)
        await persist_queue(ctx, state)
        status = "🔁 On" if state.loop else "➡️ Off"
        await ctx.send(embed=discord.Embed(title=f"Loop {status}", color=discord.Color.blue()))

    @bot.command()
    async def history(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send("Nothing has been played yet.")
        played = state.played_queue(10)
        if not played:
            return await ctx.send("Nothing has been played yet.")
        lines = [f"📜 **Last {len(played)} tracks**"]
        for i, url in enumerate(reversed(played), 1):
            name = url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
            if len(name) > 55:
                name = name[:52] + "..."
            lines.append(f"`{i}.` {name}")
        await ctx.send("\n".join(lines))

    @bot.command()
    async def jump(ctx: PlaybackContext, *, position: str = ""):
        if not position:
            return await ctx.send("Usage: `!jump <number>` — jump to track position in queue.")
        state = deps.get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send("Queue is empty.")
        try:
            idx = int(position) - 1
            if not state.contains_queue_index(idx):
                return await ctx.send(f"Position must be between 1 and {state.queue_length()}.")
            await asyncio.get_event_loop().run_in_executor(None, deps.audacious_stop)
            state.set_queue_state(state.queue, idx, loop=state.loop)
            if await deps.play_current_track(ctx):
                await persist_queue(ctx, state)
        except ValueError:
            await ctx.send("Usage: `!jump <number>` — e.g. `!jump 5`")

    @bot.command()
    @deps.mod_only()
    async def clear(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        state.clear_queue_state()
        await persist_queue(ctx, state)
        if ctx.voice_client and ctx.voice_client.is_connected():
            await deps.stop_state_streams(state)
            await asyncio.get_event_loop().run_in_executor(None, deps.stop_all_players)
            await ctx.voice_client.disconnect()
            state.clear_voice_client()
        await ctx.send("🗑️ Queue cleared.")

    @bot.command()
    async def ocko(ctx: PlaybackContext):
        owls = [
            "🦉 **OCKO**\n      ___  \n     / _ \\ \n  _ | |_| |\n / | | __ |\n|  | | |_| |\n \\  \\|  _  |\n  \\   \\_/  |\n   |       |\n   |   |   |\n   |___|___|",
            "🦉 **OCKO**\n    .---.\n   / .-._)\n .´:  _  `.\n |  (_)  |\n :       ;\n  `.___.´",
            "🦉 **OCKO**\n  ,___,\n  {o,o}\n  |)__)\n  -\"--\"-\n  m   m",
            "🦉 **OCKO**\n    ___  \n   (o o) \n  (  V  )\n  --m-m---",
            "🦉 **OCKO**\n  .------.\n  |O  O  |\n  |  V   |\n  `------´\n    ww ww",
        ]
        await ctx.send(f"```\n{random.choice(owls)}\n```")

    @bot.command(name="help")
    async def help_command(ctx: PlaybackContext):
        embed = discord.Embed(
            title="🤖 Robbo Obibok — Help",
            description="Seven collections, one bot — **the biggest chiptune radio on Discord.**\nJoin a voice channel and `!play`!",
            color=discord.Color.from_str("#2ECC71"),
        )
        embed.add_field(name="🎮 Playback", value=(
            "`!play` / `!radio` / `!start` / `!pl` — start shuffled radio\n"
            "`!stop` / `!st` — stop & disconnect\n"
            "`!skip` / `!next` / `!nt` — next track\n"
            "`!jump <n>` — jump to track N\n"
            "`!np` — now playing\n"
            "`!queue` / `!q` — show queue\n"
            "`!history` — last 10 tracks\n"
            "`!sleep <min>` — stop after N minutes\n"
            "`!loop` / `!repeat` — toggle loop\n"
            "`!volume <0-200>` — set volume\n"
            "`!clear` — clear queue"
        ), inline=False)
        embed.add_field(name="🎵 Collections", value=(
            "`!asma`  — 🟢 Atari SAP (~6 300)\n"
            "`!hvsc` / `!c64` / `!sid` — 🟣 C64 SID (~60 500)\n"
            "`!mod` / `!modarchive` / `!tracker` / `!modules` — 🟠 Tracker Modules (~175 000)\n"
            "`!ay` / `!zx` / `!zxspectrum` / `!spectrum` — 🔵 ZX Spectrum AY (~4 500)\n"
            "`!ym` / `!atarist` / `!ym2149` — 🎹 **Atari ST YM (~7 200)**\n"
            "`!tiny` / `!tm` / `!demoscene` — 🎵 Demoscene Modules (~418)\n"
            "`!snes` / `!spc` / `!supernintendo` / `!nintendo` — 🔴 SNES SPC (~60 000)"
        ), inline=False)
        embed.add_field(name="🔄 Navigation", value=(
            "`!flip` / `!switch` / `!toggle` / `!fl` — cycle through all collections\n"
            "`!status` / `!mode` / `!collection` / `!all` — show all collections & current mode\n"
            "`!search <query>` — search across current collection\n"
            "`!snes search <term>` — search SNES by game/composer"
        ), inline=False)
        embed.add_field(name="❤️ Favorites & Blacklist", value=(
            "React to any **Now Playing** embed to save/remove favorites\n"
            "`!favplay` / `!fp` — play favorites\n"
            "`!favsave` / `!pls` — save favorites as playlist\n"
            "`!favload` / `!fpl` — load & play a playlist\n"
            "`!favorites` / `!favs` — list favorites\n"
            "`!playlists` / `!plist` / `!list-playlists` / `!playlist-dir` — list saved playlists\n"
            "`!blk` — blacklist current track\n"
            "`!blks` / `!blklist` — show blacklist\n"
            "`!blkrm <n>` — remove track from blacklist"
        ), inline=False)
        embed.add_field(name="🔧 Tools & Info", value=(
            "`!stats` — radio stats (tracks, queue, playing)\n"
            "`!export` — export queue as text\n"
            "`!ocko` — 🦉 random ASCII owl\n"
            "`!refresh` — re-crawl ASMA archive *(mod only)*\n"
            "`!reindex` — re-fetch metadata *(mod only)*"
        ), inline=False)
        embed.set_footer(text="Made with 🔥 by the forest spirit")
        await ctx.send(embed=embed)

    @bot.command()
    async def export(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send("Queue is empty.")
        total = state.queue_length()
        pos = max(0, state.index)
        lines = [f"🎵 Robbo Queue Export ({total} tracks)"]
        for i, url in enumerate(state.queue):
            name = url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
            marker = "→ " if i == pos else "  "
            if len(name) > 60:
                name = name[:57] + "..."
            lines.append(f"{marker}{i+1}. {name}")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + f"\n... and {len(text) - 1900} more chars"
        await ctx.send(f"```\n{text}\n```")

    @bot.command()
    @deps.mod_only()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    async def refresh(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        state.clear_loaded_collection()
        tracks = await deps.load_tracks_for_mode("asma")
        if tracks:
            state.set_tracks(tracks)
            await ctx.send(f"✅ Reloaded! Found **{len(tracks)}** local ASMA tracks.")
        else:
            await ctx.send("❌ ASMA local cache not found. Run `python build_asma_index.py` first.")

    @bot.command()
    @deps.mod_only()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    async def reindex(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        if not state.tracks:
            return await ctx.send("No tracks loaded. Use !play first.")
        missing = [url for url in state.tracks if deps.get_metadata_entry(url) is None]
        if not missing:
            return await ctx.send(f"✅ Metadata index complete: **{deps.metadata_index_size()}** tracks.")
        await ctx.send(f"🔍 Indexing metadata for **{len(missing)}** tracks... this may take a few minutes.")
        connector = aiohttp.TCPConnector(limit=5, limit_per_host=3)
        async with aiohttp.ClientSession(connector=connector) as session:
            await deps.fetch_metadata_batch(session, missing)
        await ctx.send(f"✅ Metadata indexed: **{deps.metadata_index_size()}** tracks total.")

    @bot.command()
    async def stats(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        total = len(state.tracks)
        queue_len = state.queue_length()
        playing = "🎵 Yes" if await asyncio.to_thread(deps.is_playing) else "⏸️ No"
        loop_status = "🔁 On" if state.loop else "➡️ Off"
        await ctx.send(
            f"📊 **ASMA Radio Stats**\n"
            f"• Total tracks in archive: **{total}**\n"
            f"• Queue remaining: **{state.remaining_queue_count()}/{queue_len}**\n"
            f"• Playing: {playing}\n"
            f"• Loop: {loop_status}"
        )

    @bot.command()
    async def search(ctx: PlaybackContext, *, query: str):
        state = deps.get_state(ctx.guild.id)
        if not state.tracks:
            return await ctx.send("No tracks loaded. Use !play first.")
        matches = deps.search_tracks(query, state.tracks, limit=10)
        if not matches:
            return await ctx.send(f"No tracks matching `{query}`.")
        state.set_search_results(matches)
        lines = [f"🔍 **Results for `{query}`**"]
        for i, url in enumerate(matches, 1):
            if url.startswith("https://api.modarchive.org/") or "modarchive" in url:
                filename = (deps.get_modarchive_track_name(url) or url.split("=")[-1]).replace("_", " ")
                lines.append(f"`{i}.` {filename}")
            elif deps.ASMA_BASE in url:
                filename = url.split("/")[-1].replace(".sap", "").replace("_", " ")
                path_parts = url.replace(deps.ASMA_BASE, "").replace(".sap", "").split("/")
                if len(path_parts) > 1:
                    lines.append(f"`{i}.` {filename} *({path_parts[-2].replace('_', ' ')})*")
                else:
                    lines.append(f"`{i}.` {filename}")
            else:
                filename = url.split("/")[-1]
                for ext in [".sap", ".sid", ".mod", ".xm", ".s3m", ".it"]:
                    filename = filename.replace(ext, "")
                lines.append(f"`{i}.` {filename.replace('_', ' ')}")
        lines += ["", "Type `!play <number>` to play a track"]
        await ctx.send("\n".join(lines))

    @bot.command(aliases=["c64", "sid"])
    async def hvsc(ctx: PlaybackContext):
        await deps.switch_collection(ctx, "hvsc")

    @bot.command()
    async def asma(ctx: PlaybackContext):
        await deps.switch_collection(ctx, "asma")

    @bot.command(aliases=["modarchive", "tracker", "modules"])
    async def mod(ctx: PlaybackContext):
        await deps.switch_collection(ctx, "modarchive")

    @bot.command(aliases=["zx", "zxspectrum", "spectrum"])
    async def ay(ctx: PlaybackContext):
        await deps.switch_collection(ctx, "ay")

    @bot.command(aliases=["atarist", "ym2149"])
    async def ym(ctx: PlaybackContext):
        await deps.switch_collection(ctx, "ym")

    @bot.command(aliases=["tm", "demoscene"])
    async def tiny(ctx: PlaybackContext):
        await deps.switch_collection(ctx, "tiny")

    @bot.command(aliases=["snes", "spc", "supernintendo", "nintendo"])
    async def snes_cmd(ctx: PlaybackContext, *, query: str | None = None):
        state = deps.get_state(ctx.guild.id)
        if query:
            query_lower = query.strip().lower()
            if not deps.has_snes_metadata():
                await asyncio.get_event_loop().run_in_executor(None, deps.load_snes_cache)
            if not deps.has_snes_metadata():
                return await ctx.send("❌ SNES SPC cache not found. Run `build_snes_index.py` first!")
            results = []
            for url, entry in deps.iter_snes_metadata():
                name = cast(str, entry.get("name", ""))
                composers = cast(list[str], entry.get("composers", []))
                haystack = (name + " " + ", ".join(composers)).lower()
                if all(word in haystack for word in query_lower.split()):
                    results.append(entry)
                    if len(results) >= 10:
                        break
            if not results:
                return await ctx.send(f"🔍 **No SNES games matching `{query}`.**")
            lines = [f"🔍 **SNES results for `{query}`**"]
            for i, game in enumerate(results, 1):
                composer_text = ", ".join(cast(list[str], game.get("composers", []))) or "Unknown"
                lines.append(f"`{i}.` **{game.get('name', '?')}** — {composer_text} ({game.get('tracks', '?')}t)")
            lines += ["", "Use `!play <number>` to play, or `!snes` to switch to SPC collection."]
            state.set_search_results([cast(str, game["rsn_url"]) for game in results])
            return await ctx.send("\n".join(lines))
        await deps.switch_collection(ctx, "spc")

    @bot.command(aliases=["mode", "collection", "all"])
    async def status(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        cache_map = {
            "asma_cache_local.json": ("🟢", "Atari SAP (ASMA)"),
            "hvsc_cache_local.json": ("🟣", "C64 SID (HVSC)"),
            "modarchive_cache.json": ("🟠", "Tracker Modules (ModArchive)"),
            "ay_cache.json": ("🔵", "ZX Spectrum AY"),
            "ym_cache.json": ("🎹", "Atari ST YM"),
            "tiny_cache.json": ("🎵", "Tiny Music (Demoscene)"),
            "snes_cache.json": ("🔴", "SNES SPC"),
        }
        cache_counts = await asyncio.get_event_loop().run_in_executor(None, deps.get_all_cache_counts, cache_map)
        mode_icons = {"hvsc": "🟣", "asma": "🟢", "modarchive": "🟠", "ay": "🔵", "ym": "🎹", "tiny": "🎵", "spc": "🔴"}
        mode_labels = {"hvsc": "HVSC", "asma": "ASMA", "modarchive": "ModArchive", "ay": "AY", "ym": "Atari ST YM", "tiny": "Tiny", "spc": "SNES"}
        current_icon = mode_icons.get(state.collection_mode, "⚪")
        current_label = mode_labels.get(state.collection_mode, "Unknown")
        total = len(state.tracks) if state.tracks else 0
        qlen = state.queue_length()
        playing = "🎵 Yes" if await asyncio.to_thread(deps.is_playing) else "⏸️ No"
        lines = ["🌲 **Robbo — wszystkie kolekcje**", ""]
        for label, (icon, count) in cache_counts.items():
            hl = "◀" if label == current_label else ""
            lines.append(f"{icon} **{label}**: `{count:,}` {hl}".replace(",", " "))
        lines += [
            "",
            "━━━━━━━━━━━━━━━━━",
            f"{current_icon} **Teraz: {current_label}** — {total} tracków",
            f"• Kolejka: **{state.remaining_queue_count()}/{qlen}** | Odtwarzanie: {playing} | Pętla: {'🔁 On' if state.loop else '➡️ Off'}",
        ]
        await ctx.send("\n".join(lines))

    @bot.command(aliases=["switch", "toggle", "fl"])
    async def flip(ctx: PlaybackContext):
        state = deps.get_state(ctx.guild.id)
        try:
            idx = deps.FLIP_ORDER.index(state.collection_mode)
        except ValueError:
            idx = -1
        next_mode = deps.FLIP_ORDER[(idx + 1) % len(deps.FLIP_ORDER)]
        await deps.switch_collection(ctx, next_mode, flip_seq=deps.FLIP_SEQ)
