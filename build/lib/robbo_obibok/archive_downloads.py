"""Archive-specific download helpers."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

import aiohttp
from download_safety import read_response_limited, safe_download_path

MAX_RSN_DOWNLOAD_BYTES = 128 * 1024 * 1024
MAX_MODULE_DOWNLOAD_BYTES = 64 * 1024 * 1024


async def download_spc_rsn(rsn_url: str, spc_now: str, game_name: str, *, snes_spc_dir: str, get_shared_session, logger) -> str | None:
    game_dir = os.path.join(snes_spc_dir, re.sub(r"[^a-zA-Z0-9_-]", "_", spc_now))
    os.makedirs(game_dir, exist_ok=True)

    existing = [name for name in os.listdir(game_dir) if name.endswith(".spc")]
    if existing:
        logger.info("SNES: using cached SPCs for %s (%d files)", game_name, len(existing))
        return game_dir

    rsn_path = os.path.join(game_dir, f"{spc_now}.rsn")
    try:
        session = await get_shared_session()
        async with session.get(rsn_url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
            resp.raise_for_status()
            data = await read_response_limited(resp, max_bytes=MAX_RSN_DOWNLOAD_BYTES)
        await asyncio.to_thread(Path(rsn_path).write_bytes, data)
    except Exception as exc:
        logger.error("SNES: RSN download failed for %s: %s", game_name, exc)
        return None

    try:
        proc = await asyncio.create_subprocess_exec(
            "unrar",
            "e",
            "-y",
            rsn_path,
            game_dir + "/",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        os.remove(rsn_path)
        extracted = [name for name in os.listdir(game_dir) if name.endswith(".spc")]
        logger.info("SNES: extracted %d SPC files for %s", len(extracted), game_name)
        return game_dir
    except Exception as exc:
        logger.error("SNES: RSN extraction failed for %s: %s", game_name, exc)
        return None


async def download_modarchive_module(url: str, *, temp_dir: str, build_temp_path, get_shared_session, logger, retries: int = 2) -> str:
    last_err: BaseException | None = None

    # Persistent cache: archiwum/modarchive/cache/
    cache_dir = os.path.join(os.path.dirname(os.path.normpath(temp_dir)), "archiwum", "modarchive", "cache")
    mod_id_match = re.search(r"moduleid=(\d+)", url)
    if mod_id_match:
        mod_id = mod_id_match.group(1)
        # Check cache first
        os.makedirs(cache_dir, exist_ok=True)
        for cached in os.listdir(cache_dir):
            if cached.startswith(f"{mod_id}_") or cached == mod_id:
                cached_path = os.path.join(cache_dir, cached)
                logger.info("ModArchive cache hit: %s", cached_path)
                return cached_path

    session = await get_shared_session()
    for attempt in range(retries + 1):
        try:
            filepath = build_temp_path(url)
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BorutaBot)"}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                data = await read_response_limited(resp, max_bytes=MAX_MODULE_DOWNLOAD_BYTES)
                content_disposition = resp.headers.get("Content-Disposition", "")
                match = re.search(r"filename=([^;]+)", content_disposition)
                if match:
                    fname = match.group(1).strip('" ')
                    if fname:
                        filepath = safe_download_path(temp_dir, fname, source=url)
            await asyncio.to_thread(Path(filepath).write_bytes, data)

            # Save to persistent cache
            if mod_id_match:
                mod_id = mod_id_match.group(1)
                cache_path = os.path.join(cache_dir, f"{mod_id}_{os.path.basename(filepath)}")
                try:
                    os.makedirs(cache_dir, exist_ok=True)
                    await asyncio.to_thread(lambda: Path(cache_path).write_bytes(data))
                    logger.info("ModArchive cached: %s", cache_path)
                except Exception as exc:
                    logger.warning("ModArchive cache write failed: %s", exc)

            return filepath
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_err = exc
            if attempt < retries:
                await asyncio.sleep(2)
    logger.error("ModArchive download failed after retries: %s", last_err)
    if last_err is None:
        raise RuntimeError(f"ModArchive download failed without an exception: {url}")
    raise last_err
