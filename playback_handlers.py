"""Collection-specific playback handlers."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import discord

from bot_dependencies import PlaybackHandlerDependencies
from download_safety import read_response_limited


MAX_SID_DOWNLOAD_BYTES = 16 * 1024 * 1024


def build_playback_handlers(deps: PlaybackHandlerDependencies):
    async def play_current_sid_track(ctx, state, url):
        if "://" not in url:
            sid_path = os.path.join(deps.HVSC_DIR, url)
            if not os.path.exists(sid_path):
                await ctx.send(f"❌ File not found: `{url}`")
                return False
            data = await asyncio.to_thread(Path(sid_path).read_bytes)
        else:
            local_path = deps.resolve_local_path(url)
            if local_path:
                sid_path = local_path
                data = await asyncio.to_thread(Path(sid_path).read_bytes)
            else:
                sid_path = deps.build_temp_path(url)
                try:
                    session = await deps.get_shared_session()
                    async with session.get(url) as resp:
                        resp.raise_for_status()
                        data = await read_response_limited(resp, max_bytes=MAX_SID_DOWNLOAD_BYTES)
                    await asyncio.to_thread(Path(sid_path).write_bytes, data)
                except Exception as exc:
                    deps.log.error("SID download failed: %s", exc)
                    await ctx.send(f"❌ Download failed: {exc}")
                    return False

        meta = deps.parse_sid_header(data)
        name = meta.get("name") or url.split("/")[-1].replace(".sid", "")
        author = meta.get("author", "")
        copyright_info = meta.get("copyright", "")

        await deps.play_via_audacious(state, sid_path, current_path=sid_path)
        await deps.send_now_playing_embed(
            ctx,
            state,
            url,
            title=name,
            color=discord.Color.purple(),
            footer="C64 SID Radio",
            author=author,
            extra_fields=[("Copyright", copyright_info)],
        )
        deps.log.info("SID now playing: %s — %s", name, author)
        return True

    async def play_current_modarchive_track(ctx, state, url):
        try:
            filepath = await deps.download_modarchive_module(url)
        except Exception as exc:
            deps.log.error("ModArchive download failed: %s", exc)
            await ctx.send(f"❌ Download failed: {exc}")
            return False

        fname = os.path.basename(filepath) if filepath else url.split("moduleid=")[-1]
        display_name = fname.rsplit(".", 1)[0] if "." in fname else fname
        display_name = display_name.replace("_", " ").strip()
        fmt = fname.rsplit(".", 1)[-1].upper() if "." in fname else "MODULE"

        await deps.play_via_audacious(state, filepath, current_path=filepath)
        await deps.send_now_playing_embed(
            ctx,
            state,
            url,
            title=display_name,
            color=discord.Color.from_str("#E67E22"),
            footer="ModArchive Radio — FastTracker / MOD / XM / S3M / IT",
            extra_fields=[("Format", fmt)],
        )
        deps.log.info("ModArchive now playing: %s (%s)", display_name, fmt)
        return True

    async def play_current_asma_track(ctx, state, url):
        if "://" not in url:
            filepath = os.path.join(deps.ASMA_DIR, url)
            if not os.path.exists(filepath):
                await ctx.send(f"❌ File not found: `{url}`")
                return False
            deps.clear_predownload_state(state)
        else:
            local_path = deps.resolve_local_path(url)
            if local_path:
                filepath = local_path
                deps.clear_predownload_state(state)
            elif state.has_predownload_for(url) and state.pre_downloaded and os.path.exists(state.pre_downloaded):
                filepath = state.pre_downloaded
                deps.clear_predownload_state(state, keep_file=True)
            else:
                deps.clear_predownload_state(state)
                filepath = await deps.download_sap(url)

        await deps.play_via_audacious(state, filepath, current_path=filepath)
        track = await asyncio.get_event_loop().run_in_executor(None, deps.audacious_song)
        meta = deps.parse_sap_header(filepath)
        name = meta.get("NAME", track or url.split("/")[-1])
        author = meta.get("AUTHOR", "")
        songs = meta.get("SONGS", "")
        await deps.send_now_playing_embed(
            ctx,
            state,
            url,
            title=name,
            color=discord.Color.green(),
            footer="ASMA Radio",
            author=author,
            extra_fields=[("Songs", songs)],
        )
        return True

    async def play_current_ay_track(ctx, state, filepath):
        full_path = os.path.join(deps.AY_DIR, filepath)
        if not os.path.exists(full_path):
            await ctx.send(f"❌ File not found: `{filepath}`")
            return False

        await deps.play_via_audacious(state, full_path)
        track = await asyncio.get_event_loop().run_in_executor(None, deps.audacious_song)
        name = track or filepath.split("/")[-1].replace(".ay", "")
        await deps.send_now_playing_embed(
            ctx,
            state,
            filepath,
            title=name,
            color=discord.Color.blue(),
            footer="ZX Spectrum AY — via libgme",
        )
        deps.log.info("AY now playing: %s", name)
        return True

    async def play_current_ym_track(ctx, state, filepath):
        full_path = os.path.join(deps.YM_DIR, filepath)
        if not os.path.exists(full_path):
            await ctx.send(f"❌ File not found: `{filepath}`")
            return False

        await asyncio.get_event_loop().run_in_executor(None, deps.ym_cleanup)
        try:
            wav_path = await asyncio.get_event_loop().run_in_executor(None, deps.ym_to_wav, full_path)
        except Exception as exc:
            deps.log.error("YM→WAV conversion failed: %s", exc)
            await ctx.send(f"❌ Failed to decode YM file: `{filepath}`")
            return False

        deps.set_ym_last_wav_path(wav_path)
        await deps.play_via_audacious(state, wav_path, current_path=full_path)

        name = filepath.split("/")[-1].replace(".ym", "").replace(".YM", "")
        await deps.send_now_playing_embed(
            ctx,
            state,
            filepath,
            title=name,
            color=discord.Color.from_str("#F1C40F"),
            footer="Atari ST YM2149 — decoded via ST-Sound + Audacious",
        )
        deps.log.info("YM now playing: %s", name)
        return True

    async def play_current_tiny_track(ctx, state, filepath):
        full_path = os.path.join(deps.TINY_DIR, filepath)
        if not os.path.exists(full_path):
            await ctx.send(f"❌ File not found: `{filepath}`")
            return False

        deps.cleanup_subsong_temp_wavs(state)
        subsongs = deps.get_subsongs(full_path)
        has_multi = len(subsongs) > 1
        if has_multi:
            state.set_subsong_state(path=full_path, total=len(subsongs), current=0)
            deps.log.info(
                "Subsong: %s has %d sub-songs (main=%.1fs, extra=%d)",
                os.path.basename(full_path),
                len(subsongs),
                subsongs[0],
                len(subsongs) - 1,
            )
        else:
            deps.cleanup_subsong_temp_wavs(state)

        await deps.play_via_audacious(state, full_path, current_path=full_path)

        track = await asyncio.get_event_loop().run_in_executor(None, deps.audacious_song)
        name = (
            track
            or filepath.split("/")[-1]
            .replace(".mod", "")
            .replace(".xm", "")
            .replace(".it", "")
            .replace(".s3m", "")
            .replace(".med", "")
            .replace(".dmf", "")
            .replace(".mo3", "")
            .replace(".mptm", "")
        )
        footer = (
            f"Tiny Music — curated demoscene modules · {len(subsongs)} parts"
            if has_multi
            else "Tiny Music — curated demoscene modules"
        )
        await deps.send_now_playing_embed(
            ctx,
            state,
            filepath,
            title=name,
            color=discord.Color.purple(),
            footer=footer,
        )
        deps.log.info("Tiny now playing: %s", name)
        return True

    async def play_current_spc_track(ctx, state, game_entry: dict):
        spc_now = game_entry["spc_now"]
        game_name = game_entry.get("name", "Unknown")
        composers = game_entry.get("composers", [])

        game_dir = await deps.download_spc_rsn(game_entry["rsn_url"], spc_now, game_name)
        if not game_dir:
            await ctx.send(f"❌ Failed to download/extract `{game_name}`")
            return False

        spc_files = sorted([fname for fname in os.listdir(game_dir) if fname.endswith(".spc")])
        if not spc_files:
            await ctx.send(f"❌ No SPC files found for `{game_name}`")
            return False

        first_spc = os.path.join(game_dir, spc_files[0])
        await asyncio.get_event_loop().run_in_executor(None, deps.audacious_stop)
        await asyncio.get_event_loop().run_in_executor(None, deps.audacious_play, first_spc)

        state.set_current_path(first_spc)
        deps.setup_monitor_source(state)

        pos, total = deps.queue_position(state)
        embed = discord.Embed(title=game_name[:256], color=discord.Color.from_str("#E74C3C"))
        if composers:
            embed.add_field(name="Composer(s)", value=", ".join(composers[:5]), inline=True)
        embed.add_field(name="Position", value=f"{pos}/{total}", inline=True)
        embed.add_field(name="Tracks", value=str(len(spc_files)), inline=True)
        embed.set_footer(text="SNES Radio — Super Nintendo SPC")

        np_msg = await ctx.send(embed=embed)
        deps.register_np_message(
            np_msg.id,
            game_entry["rsn_url"],
            game_name,
            ", ".join(composers) if composers else "Unknown",
        )
        deps.log.info("SNES now playing: %s — %s", game_name, ", ".join(composers) if composers else "?")
        return True

    return {
        "asma": play_current_asma_track,
        "ay": play_current_ay_track,
        "hvsc": play_current_sid_track,
        "modarchive": play_current_modarchive_track,
        "spc": play_current_spc_track,
        "tiny": play_current_tiny_track,
        "ym": play_current_ym_track,
    }
