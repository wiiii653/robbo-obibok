"""Archive/cache/download helpers extracted from the bot entrypoint."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable
from urllib.parse import urljoin

import aiohttp

from .archive_downloads import download_modarchive_module as archive_download_modarchive_module
from .archive_downloads import download_spc_rsn as archive_download_spc_rsn
from .domain_archive_config import ArchiveRuntimeConfig

if TYPE_CHECKING:
    from .archive_catalog import ArchiveCatalog

SAP_LINE_RE = re.compile(rb"^([A-Z]+)\s+(.+)")
SAP_RE = re.compile(r'href="([^"]+\.sap)"', re.IGNORECASE)
DIR_RE = re.compile(r'href="([^"]+)/"')


@dataclass(slots=True)
class ArchiveRuntime:
    archives: "ArchiveCatalog"
    logger: logging.Logger
    snes_spc_dir: str
    temp_dir: str
    build_temp_path: Callable[[str], str]
    get_shared_session: Callable[[], Awaitable[aiohttp.ClientSession]]
    config: ArchiveRuntimeConfig
    _crawl_semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self._crawl_semaphore = asyncio.Semaphore(self.config.crawl_concurrency)

    def _sync_archive_paths(self) -> None:
        paths = self.archives.paths
        paths.asma_base = self.config.asma_base
        paths.asma_dir = self.config.asma_dir
        paths.asma_local_cache = self.config.asma_local_cache
        paths.ay_cache = self.config.ay_cache
        paths.hvsc_base = self.config.hvsc_base
        paths.hvsc_cache_file = self.config.hvsc_cache_file
        paths.hvsc_cache_ttl_hours = self.config.hvsc_cache_ttl_hours
        paths.hvsc_local_cache = self.config.hvsc_local_cache
        paths.hvsc_songlengths_url = self.config.hvsc_songlengths_url
        paths.metadata_cache = self.config.metadata_cache
        paths.modarchive_cache_file = self.config.modarchive_cache_file
        paths.snes_cache_file = self.config.snes_cache_file
        paths.tiny_cache = self.config.tiny_cache
        paths.ym_cache = self.config.ym_cache

    def parse_sap_header(self, filepath: str) -> dict[str, str]:
        try:
            with open(filepath, "rb") as handle:
                return self.parse_sap_metadata_bytes(handle.read(4096))
        except OSError:
            return {}

    def parse_sap_metadata_bytes(self, data: bytes) -> dict[str, str]:
        meta: dict[str, str] = {}
        for raw_line in data.split(b"\n"):
            line = raw_line.strip()
            if not line or line == b"SAP":
                continue
            if line.startswith(b";"):
                line = line[1:].strip()
            match = SAP_LINE_RE.match(line)
            if not match:
                continue
            key = match.group(1).decode("ascii", errors="replace").strip().upper()
            val_raw = match.group(2).decode("ascii", errors="replace").strip()
            meta[key] = val_raw.strip("\"'")
        return meta

    def parse_songlengths_to_tracks(self, data: str) -> list[str]:
        self._sync_archive_paths()
        return self.archives.parse_songlengths_to_tracks(data)

    def download_hvsc_index(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.download_hvsc_index()

    def load_cached_hvsc(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_cached_hvsc()

    def load_modarchive_cache(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_modarchive_cache()

    def load_ay_cache(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_ay_cache()

    def load_ym_cache(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_ym_cache()

    def load_tiny_cache(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_tiny_cache()

    def load_asma_local_cache(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_asma_local_cache()

    def load_hvsc_local_cache(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_hvsc_local_cache()

    def load_snes_cache(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_snes_cache()

    def load_kgen_cache(self) -> list[str] | None:
        self._sync_archive_paths()
        return self.archives.load_kgen_cache()

    def load_metadata_cache(self) -> dict[str, dict[str, str]]:
        self._sync_archive_paths()
        return self.archives.load_metadata_cache()

    def save_metadata_cache(self, index: dict[str, dict[str, str]]) -> None:
        self._sync_archive_paths()
        self.archives.save_metadata_cache(index)

    async def fetch_single_metadata(self, session: aiohttp.ClientSession, url: str) -> dict[str, str]:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return {}
                return self.parse_sap_metadata_bytes(await resp.content.read(4096))
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return {}

    async def fetch_metadata_batch(
        self,
        session: aiohttp.ClientSession,
        urls: list[str],
        *,
        batch_size: int = 20,
    ) -> dict[str, dict[str, str]]:
        self._sync_archive_paths()
        return await self.archives.fetch_metadata_batch(
            session,
            urls,
            self.fetch_single_metadata,
            batch_size=batch_size,
        )

    def search_tracks(self, query: str, tracks: list[str], *, limit: int = 10) -> list[str]:
        self._sync_archive_paths()
        return self.archives.search_tracks(query, tracks, limit=limit)

    async def crawl_directory(self, session: aiohttp.ClientSession, url: str, depth: int = 0) -> list[str]:
        if depth > 10:
            return []

        async with self._crawl_semaphore:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.config.crawl_timeout)) as resp:
                    if resp.status != 200:
                        self.logger.warning("HTTP %d for %s", resp.status, url)
                        return []
                    html = await resp.text()
            except asyncio.TimeoutError:
                self.logger.warning("TIMEOUT %s", url)
                return []
            except (aiohttp.ClientError, OSError) as exc:
                self.logger.error("ERROR %s: %s", url, exc)
                return []

        tracks = [urljoin(url, match.group(1)) for match in SAP_RE.finditer(html)]
        seen_dirs: set[str] = set()
        sub_tasks = []
        for match in DIR_RE.finditer(html):
            subdir = match.group(1)
            if subdir in ("..", ".") or subdir.startswith("/") or "?" in subdir or subdir in seen_dirs:
                continue
            seen_dirs.add(subdir)
            sub_tasks.append(self.crawl_directory(session, urljoin(url, subdir + "/"), depth + 1))

        if sub_tasks:
            results = await asyncio.gather(*sub_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    tracks.extend(result)
        return tracks

    async def refresh_tracklist(self) -> list[str]:
        cached = await asyncio.to_thread(self.load_cached_tracklist)
        if cached:
            self.logger.info("ASMA: loaded %d tracks from cache", len(cached))
            return cached
        self.logger.info("ASMA: cache stale or missing, crawling...")
        all_tracks: list[str] = []
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        async with aiohttp.ClientSession(connector=connector) as session:
            for index, top_dir in enumerate(self.config.top_level_dirs or []):
                url = urljoin(self.config.asma_base, top_dir)
                self.logger.info("[%d/%d] Crawling %s...", index + 1, len(self.config.top_level_dirs or []), top_dir)
                tracks = await self.crawl_directory(session, url)
                self.logger.info("  -> %d tracks found in %s", len(tracks), top_dir)
                all_tracks.extend(tracks)
        cache_data = {"tracks": all_tracks, "count": len(all_tracks)}

        def save_cache() -> None:
            try:
                with open(self.config.cache_file, "w") as handle:
                    json.dump(cache_data, handle, indent=2)
            except (OSError, TypeError, ValueError) as exc:
                self.logger.warning("ASMA cache write failed: %s", exc)

        await asyncio.to_thread(save_cache)
        return all_tracks

    def load_cached_tracklist(self) -> list[str] | None:
        try:
            if not os.path.exists(self.config.cache_file):
                return None
            age = time.time() - os.path.getmtime(self.config.cache_file)
            if age > self.config.cache_ttl_hours * 3600:
                return None
            with open(self.config.cache_file) as handle:
                data = json.load(handle)
            return data.get("tracks", [])
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, AttributeError):
            return None

    async def download_spc_rsn(self, rsn_url: str, spc_now: str, game_name: str) -> str | None:
        return await archive_download_spc_rsn(
            rsn_url,
            spc_now,
            game_name,
            snes_spc_dir=self.snes_spc_dir,
            get_shared_session=self.get_shared_session,
            logger=self.logger,
        )

    async def download_modarchive_module(self, url: str, retries: int = 2) -> str:
        return await archive_download_modarchive_module(
            url,
            temp_dir=self.temp_dir,
            build_temp_path=self.build_temp_path,
            get_shared_session=self.get_shared_session,
            logger=self.logger,
            retries=retries,
        )

    def parse_sid_header(self, data: bytes) -> dict[str, str]:
        meta = {"name": "", "author": "", "copyright": ""}
        if len(data) < 0x76:
            return meta
        magic = data[0:4]
        if magic not in (b"PSID", b"RSID"):
            return meta
        meta["name"] = data[0x16:0x16 + 32].rstrip(b"\x00").decode("ascii", errors="replace").strip()
        meta["author"] = data[0x36:0x36 + 32].rstrip(b"\x00").decode("ascii", errors="replace").strip()
        meta["copyright"] = data[0x56:0x56 + 32].rstrip(b"\x00").decode("ascii", errors="replace").strip()
        return meta

    def cleanup_orphan_players(self) -> None:
        user = os.environ.get("USER", "") or os.environ.get("LOGNAME", "")
        subprocess.run(["pkill", "-u", user, "-x", "audacious"], capture_output=True)
