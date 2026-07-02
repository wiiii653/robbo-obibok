"""Favorites, playlists, and blacklist command registration."""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from typing import cast

import discord
from discord.ext import commands

from .bot_dependencies import LibraryCommandDependencies


def register_library_commands(bot, deps: LibraryCommandDependencies) -> None:
    favorites_lock = asyncio.Lock()
    blacklist_lock = asyncio.Lock()

    async def persist(ctx, label, operation, *args):
        try:
            return True, await asyncio.to_thread(operation, *args)
        except OSError as exc:
            deps.log.error("%s persistence failed: %s", label, exc)
            if ctx is not None:
                await ctx.send(f"❌ {label} could not be saved. Check bot storage permissions.")
            return False, None

    @bot.event
    async def on_raw_reaction_add(payload):
        track = deps.get_message_track(payload.message_id)
        if track is None:
            return
        async with favorites_lock:
            favs = await asyncio.to_thread(deps.load_favorites)
            url = track["url"]
            if not isinstance(url, str):
                return
            entry = {
                "url": url,
                "name": track.get("name", url.split("/")[-1].replace(".sap", "")),
                "author": track.get("author", ""),
                "added_at": time.time(),
                "emoji": str(payload.emoji),
            }
            favs, added = deps.toggle_user_track_entry(favs, payload.user_id, entry)
            saved, _ = await persist(None, "Favorites", deps.save_favorites, favs)
        if not saved:
            return
        if not added:
            deps.log.info("❤️ Removed from favorites: %s", url)
        else:
            deps.log.info("❤️ Added to favorites: %s — %s", track.get("name", "?"), url)

    @bot.event
    async def on_raw_reaction_remove(payload):
        track = deps.get_message_track(payload.message_id)
        if track is None:
            return
        url = track["url"]
        if not isinstance(url, str):
            return
        async with favorites_lock:
            favs = await asyncio.to_thread(deps.load_favorites)
            favs, removed = deps.remove_user_track(favs, payload.user_id, url)
            if not removed:
                return
            saved, _ = await persist(None, "Favorites", deps.save_favorites, favs)
        if not saved:
            return
        deps.log.info("❤️ Removed from favorites via reaction removal: %s", url)

    async def _play_track_list(ctx, tracks: list[dict], label: str) -> bool:
        assert ctx.guild is not None
        author = cast(discord.Member, ctx.author)
        assert author.voice is not None
        assert author.voice.channel is not None
        state = deps.get_state(ctx.guild.id)
        first_url = tracks[0]["url"]
        if "asma.atari.org" in first_url or first_url.endswith(".sap"):
            state.set_collection_mode("asma")
        elif "hvsc.c64.org" in first_url or first_url.endswith(".sid"):
            state.set_collection_mode("hvsc")
        elif "modarchive" in first_url:
            state.set_collection_mode("modarchive")
        if not state.tracks:
            await deps.ensure_tracks(state)
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        vc: discord.VoiceClient = cast(discord.VoiceClient, await author.voice.channel.connect())
        state.bind_voice_context(guild_id=ctx.guild.id, ctx=ctx, vc=vc)
        state.set_loop_enabled(True)
        deps.clear_predownload_state(state)
        state.set_queue_state([track["url"] for track in tracks], 0)
        await ctx.send(f"🎵 **Playing {len(tracks)} {label}!**")
        if await deps.play_current_track(ctx):
            await persist(ctx, "Queue", deps.save_queue, state)
            if state.monitor_task and not state.monitor_task.done():
                state.monitor_task.cancel()
            if deps.task_manager is not None:
                task = deps.task_manager.create(f"monitor_{ctx.guild.id}", deps.monitor_playback(ctx, vc, ctx.guild.id))
            else:
                task = asyncio.create_task(deps.monitor_playback(ctx, vc, ctx.guild.id))
            state.set_monitor_task(task)
        return True

    @bot.command(aliases=["favs", "playlist"])
    async def favorites(ctx: commands.Context):
        favorites_data = await asyncio.to_thread(deps.load_favorites)
        user_favs = deps.load_user_tracks(favorites_data, ctx.author.id)
        if not user_favs:
            return await ctx.send("📭 **No favorites yet.** React to a Now Playing embed with any emoji to save tracks here!")
        lines = [f"🎵 **Your Favorites ({len(user_favs)} tracks)**"]
        for i, track in enumerate(user_favs, 1):
            author_s = f" — {track['author']}" if track.get("author") else ""
            lines.append(f"`{i}.` {track.get('name', 'Unknown')}{author_s}")
        for chunk_start in range(0, len(lines), 15):
            await ctx.send("\n".join(lines[chunk_start:chunk_start + 15]))

    @bot.command(aliases=["fp"])
    async def favplay(ctx: commands.Context, *, number: str = ""):
        if number:
            favorites_data = await asyncio.to_thread(deps.load_favorites)
            blacklist = None
        else:
            favorites_data, blacklist = await asyncio.to_thread(
                lambda: (deps.load_favorites(), deps.load_blacklist())
            )
        user_favs = deps.load_user_tracks(favorites_data, ctx.author.id)
        if not user_favs:
            return await ctx.send("📭 **No favorites yet.** React to any Now Playing embed with an emoji to save tracks!")
        author = cast(discord.Member, ctx.author)
        if not author.voice:
            return await ctx.send("Join a voice channel first!")
        if number:
            try:
                idx = int(number) - 1
                if idx < 0 or idx >= len(user_favs):
                    return await ctx.send(f"Number must be between 1 and {len(user_favs)}.")
                tracks_to_play = [user_favs[idx]]
            except ValueError:
                return await ctx.send("Usage: `!favplay <number>` or `!favplay` to play all.")
        else:
            assert blacklist is not None
            tracks_to_play = deps.filter_blacklisted_track_entries(list(user_favs), blacklist, ctx.author.id)
            random.shuffle(tracks_to_play)
        if not tracks_to_play:
            return await ctx.send("⛔ All your favorites are blacklisted. Nothing to play!")
        await _play_track_list(ctx, tracks_to_play, "favorites")

    @bot.command(aliases=["pls"])
    async def favsave(ctx: commands.Context, *, name: str):
        favorites_data = await asyncio.to_thread(deps.load_favorites)
        user_favs = deps.load_user_tracks(favorites_data, ctx.author.id)
        if not user_favs:
            return await ctx.send("📭 **No favorites to save.** React to a Now Playing embed with any emoji to add tracks first!")
        saved, safe_name = await persist(
            ctx,
            "Playlist",
            deps.save_playlist,
            name.strip(),
            user_favs,
            ctx.author.id,
            str(ctx.author),
        )
        if not saved:
            return
        await ctx.send(f"💾 **Saved!** `{safe_name}` — {len(user_favs)} tracks from your favorites.")

    @bot.command(aliases=["fpl"])
    async def favload(ctx: commands.Context, *, name: str):
        if name.strip().lower() == "list":
            playlists = await asyncio.to_thread(deps.list_playlists)
            if not playlists:
                return await ctx.send("📂 **No playlists saved yet.** Use `!favsave <name>` to create one!")
            lines = ["📂 **Saved Playlists**"]
            for playlist in playlists:
                author_s = f" by {playlist['author']}" if playlist["author"] != "?" else ""
                lines.append(f"`{playlist['name']}` — {playlist['tracks']} tracks{author_s}")
            return await ctx.send("\n".join(lines))
        author = cast(discord.Member, ctx.author)
        if not author.voice:
            return await ctx.send("Join a voice channel first!")
        loaded_playlist = await asyncio.to_thread(deps.load_playlist, name.strip())
        if not loaded_playlist:
            return await ctx.send(f"❌ Playlist `{name.strip()}` not found. Use `!favload list` to see saved playlists.")
        tracks = loaded_playlist.get("tracks", [])
        if not tracks:
            return await ctx.send(f"📭 Playlist `{loaded_playlist['name']}` is empty!")
        await _play_track_list(ctx, tracks, f"playlist \"{loaded_playlist['name']}\"")

    @bot.command(aliases=["plist", "list-playlists", "playlist-dir"])
    async def playlists(ctx: commands.Context):
        await asyncio.to_thread(deps.ensure_playlist_dir)
        files = await asyncio.to_thread(lambda: sorted(os.listdir(deps.PLAYLIST_DIR)))
        json_files = [fname for fname in files if fname.endswith(".json")]
        if not json_files:
            return await ctx.send("📂 **No playlists saved yet.** Use `!favsave <name>` to create one!")
        lines = ["📂 **Playlists Directory**"]
        for fname in json_files:
            path = os.path.join(deps.PLAYLIST_DIR, fname)
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
                created = data.get("created", 0) or os.path.getmtime(path)
                author = data.get("author", "?")
                author_s = f" by {author}" if author and author != "?" else ""
                lines.append(
                    f"`{data.get('name', fname[:-5])}` — {len(data.get('tracks', []))} tracks{author_s} ({time.strftime('%Y-%m-%d', time.localtime(created))})"
                )
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, AttributeError) as exc:
                deps.log.warning("Playlist metadata unreadable for %s: %s", path, exc)
                try:
                    size = os.path.getsize(path)
                    modified = time.strftime(
                        "%Y-%m-%d", time.localtime(os.path.getmtime(path))
                    )
                except OSError:
                    size = "?"
                    modified = "unknown"
                lines.append(
                    f"`{fname}` — {size} bytes ({modified}) — ⚠️ parse error"
                )
        message = "\n".join(lines)
        if len(message) <= 2000:
            await ctx.send(message)
        else:
            for i in range(0, len(lines), 10):
                await ctx.send("\n".join(lines[i:i + 10]))

    @bot.command(aliases=["blk"])
    async def blacklist_track(ctx: commands.Context, *, number: str = ""):
        assert ctx.guild is not None
        state = deps.get_state(ctx.guild.id)
        if number:
            try:
                idx = int(number) - 1
                if idx < 0 or idx >= len(state.queue):
                    return await ctx.send(f"Number must be between 1 and {len(state.queue)}.")
                url = state.queue[idx]
                name = url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
            except ValueError:
                return await ctx.send("Usage: `!blk <number>` to blacklist a track from the queue, or `!blk` for the current track.")
        else:
            if not state.queue or state.index < 0 or state.index >= len(state.queue):
                return await ctx.send("Nothing is playing right now.")
            url = state.queue[state.index]
            name = (await asyncio.get_running_loop().run_in_executor(None, deps.audacious_song)) or url.split("/")[-1].rsplit(".", 1)[0].replace("_", " ")
        async with blacklist_lock:
            blk = await asyncio.to_thread(deps.load_blacklist)
            blk, added = deps.toggle_user_track_entry(blk, ctx.author.id, {"url": url, "name": name, "added_at": time.time()})
            saved, _ = await persist(ctx, "Blacklist", deps.save_blacklist, blk)
        if not saved:
            return
        if not added:
            await ctx.send(f"✅ **Un-blacklisted** — `{name}`")
            deps.log.info("⛔ Removed from blacklist by %s: %s", ctx.author, url)
        else:
            await ctx.send(f"⛔ **Blacklisted** — `{name}`\n*This track will be skipped when you use !play*")
            deps.log.info("⛔ Added to blacklist by %s: %s — %s", ctx.author, name, url)
        if added and state.queue and 0 <= state.index < len(state.queue) and url == state.queue[state.index]:
            voice_client = cast(discord.VoiceClient | None, ctx.voice_client)
            if voice_client and voice_client.is_connected():
                await ctx.send("⏭️ Skipping blacklisted track...")
                await deps.skip_to_next(ctx)

    @bot.command(aliases=["blks", "blklist"])
    async def blacklist_list(ctx: commands.Context):
        blacklist = await asyncio.to_thread(deps.load_blacklist)
        user_blk = deps.load_user_tracks(blacklist, ctx.author.id)
        if not user_blk:
            return await ctx.send("📭 **No blacklisted tracks.** Use `!blk` on a playing track to add it here.")
        lines = [f"⛔ **Your Blacklist ({len(user_blk)} tracks)**"]
        for i, track in enumerate(user_blk, 1):
            lines.append(f"`{i}.` {track.get('name', 'Unknown')}")
        for chunk_start in range(0, len(lines), 15):
            await ctx.send("\n".join(lines[chunk_start:chunk_start + 15]))

    @bot.command(aliases=["blkrm"])
    async def blacklist_remove(ctx: commands.Context, *, number: str):
        async with blacklist_lock:
            blk = await asyncio.to_thread(deps.load_blacklist)
            uid = str(ctx.author.id)
            user_blk = deps.load_user_tracks(blk, uid)
            if not user_blk:
                return await ctx.send("📭 Your blacklist is empty.")
            try:
                idx = int(number) - 1
                if idx < 0 or idx >= len(user_blk):
                    return await ctx.send(f"Number must be between 1 and {len(user_blk)}.")
            except ValueError:
                return await ctx.send("Usage: `!blkrm <number>`")
            removed = user_blk.pop(idx)
            blk[uid]["tracks"] = user_blk
            saved, _ = await persist(ctx, "Blacklist", deps.save_blacklist, blk)
        if not saved:
            return
        await ctx.send(f"✅ **Removed from blacklist** — `{removed.get('name', 'Unknown')}`")
