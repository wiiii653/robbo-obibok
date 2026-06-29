"""Archive-specific download helpers."""

from __future__ import annotations

import asyncio
import os
import re
from hashlib import sha1

import aiohttp


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
            data = await resp.read()
        with open(rsn_path, "wb") as handle:
            handle.write(data)
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
    last_err = None
    session = await get_shared_session()
    for attempt in range(retries + 1):
        try:
            filepath = build_temp_path(url)
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BorutaBot)"}) as resp:
                resp.raise_for_status()
                data = await resp.read()
                content_disposition = resp.headers.get("Content-Disposition", "")
                match = re.search(r"filename=([^;]+)", content_disposition)
                if match:
                    fname = match.group(1).strip('" ')
                    if fname:
                        digest = sha1(url.encode("utf-8")).hexdigest()[:12]
                        filepath = os.path.join(temp_dir, f"{digest}_{fname}")
            with open(filepath, "wb") as handle:
                handle.write(data)
            return filepath
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            last_err = exc
            if attempt < retries:
                await asyncio.sleep(2)
    logger.error("ModArchive download failed after retries: %s", last_err)
    raise last_err
