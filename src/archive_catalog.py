"""Archive and cache loading helpers."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Awaitable, Callable, Iterable, Mapping, TypeVar

from archive_runtime import ArchiveRuntimeConfig

ArchivePaths = ArchiveRuntimeConfig

TrackLoadResult = list[str] | None | Awaitable[list[str] | None]
TrackLoader = Callable[[], TrackLoadResult]
SessionT = TypeVar("SessionT")


@dataclass(slots=True)
class CollectionInfo:
    icon: str
    name: str
    station: str
    footer: str
    color: str
    load_tracks: TrackLoader
    fallback_load: TrackLoader | None = None


@dataclass(slots=True)
class ArchiveCatalog:
    paths: ArchiveRuntimeConfig
    logger: logging.Logger
    metadata_index: dict[str, dict[str, str]] = field(default_factory=dict)
    modarchive_name_map: dict[str, str] = field(default_factory=dict)
    sid_durations: dict[str, int] = field(default_factory=dict)
    snes_metadata: dict[str, dict[str, object]] = field(default_factory=dict)

    @property
    def metadata_index_view(self) -> Mapping[str, dict[str, str]]:
        return MappingProxyType(self.metadata_index)

    @property
    def modarchive_name_map_view(self) -> Mapping[str, str]:
        return MappingProxyType(self.modarchive_name_map)

    @property
    def sid_durations_view(self) -> Mapping[str, int]:
        return MappingProxyType(self.sid_durations)

    @property
    def snes_metadata_view(self) -> Mapping[str, dict[str, object]]:
        return MappingProxyType(self.snes_metadata)

    def metadata_entry(self, url: str) -> dict[str, str] | None:
        return self.metadata_index.get(url)

    def modarchive_track_name(self, url: str) -> str | None:
        return self.modarchive_name_map.get(url)

    def snes_game_entry(self, url: str) -> dict[str, object] | None:
        return self.snes_metadata.get(url)

    def has_snes_metadata(self) -> bool:
        return bool(self.snes_metadata)

    def iter_snes_games(self) -> Iterable[tuple[str, dict[str, object]]]:
        return self.snes_metadata.items()

    def store_metadata_entries(self, entries: Mapping[str, dict[str, str]]) -> None:
        self.metadata_index.update(entries)

    def replace_modarchive_name_map(self, entries: Mapping[str, str]) -> None:
        self.modarchive_name_map.clear()
        self.modarchive_name_map.update(entries)

    def replace_snes_metadata(self, entries: Mapping[str, dict[str, object]]) -> None:
        self.snes_metadata.clear()
        self.snes_metadata.update(entries)

    def _parse_duration(self, dur_str: str) -> int:
        dur_str = dur_str.strip().split()[0].split("(")[0].strip()
        if ":" not in dur_str:
            return 0
        try:
            mins, secs = dur_str.split(":")
            return int(mins) * 60 + int(secs)
        except (ValueError, IndexError):
            return 0

    def parse_songlengths_to_tracks(self, data: str) -> list[str]:
        urls: list[str] = []
        pending_path: str | None = None

        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("; /"):
                rest = line[2:].strip()
                if " = " in rest:
                    path_part, dur_part = rest.split(" = ", 1)
                else:
                    path_part, dur_part = rest, None
                    pending_path = path_part

                full_url = self.paths.hvsc_base.rstrip("/") + path_part
                urls.append(full_url)
                if dur_part:
                    sec = self._parse_duration(dur_part)
                    if sec:
                        self.sid_durations[full_url] = sec
            elif "=" in line and pending_path is not None:
                dur_part = line.split("=", 1)[1]
                full_url = self.paths.hvsc_base.rstrip("/") + pending_path
                sec = self._parse_duration(dur_part)
                if sec:
                    self.sid_durations[full_url] = sec
                pending_path = None

        return urls

    def load_metadata_cache(self) -> dict[str, dict[str, str]]:
        try:
            if os.path.exists(self.paths.metadata_cache):
                with open(self.paths.metadata_cache) as handle:
                    return json.load(handle)
        except Exception:
            pass
        return {}

    def save_metadata_cache(self, index: dict[str, dict[str, str]]) -> None:
        try:
            with open(self.paths.metadata_cache, "w") as handle:
                json.dump(index, handle, indent=2)
        except Exception:
            pass

    async def fetch_metadata_batch(
        self,
        session: SessionT,
        urls: list[str],
        fetch_single: Callable[[SessionT, str], Awaitable[dict[str, str]]],
        batch_size: int = 20,
    ) -> dict[str, dict[str, str]]:
        results: dict[str, dict[str, str]] = {}
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_urls = []
            tasks = []
            for url in batch:
                if url in self.metadata_index:
                    continue
                batch_urls.append(url)
                tasks.append(fetch_single(session, url))
            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for url, result in zip(batch_urls, batch_results):
                    if isinstance(result, dict) and result:
                        results[url] = result
            if results:
                self.store_metadata_entries(results)
        if self.metadata_index:
            await asyncio.to_thread(self.save_metadata_cache, self.metadata_index)
        return results

    def search_tracks(self, query: str, tracks: list[str], limit: int = 10) -> list[str]:
        query_lower = query.lower()
        results = []
        for url in tracks:
            if url.startswith("https://api.modarchive.org/") or "modarchive" in url:
                filename = (self.modarchive_track_name(url) or "").replace("_", " ")
            else:
                filename = url.split("/")[-1]
                for ext in [".sap", ".sid", ".mod", ".xm", ".s3m", ".it"]:
                    filename = filename.replace(ext, "")
                filename = filename.replace("_", " ")
            if query_lower in filename.lower():
                results.append(url)
                if len(results) >= limit:
                    break
                continue
            searchable = url.replace(self.paths.asma_base, "").replace(self.paths.hvsc_base, "").lower()
            searchable = searchable.replace("_", " ").replace("/", " ")
            if query_lower in searchable:
                results.append(url)
                if len(results) >= limit:
                    break
                continue
            meta = self.metadata_entry(url) or {}
            name = meta.get("NAME", meta.get("name", ""))
            author = meta.get("AUTHOR", meta.get("author", ""))
            if query_lower in name.lower() or query_lower in author.lower():
                results.append(url)
                if len(results) >= limit:
                    break
        return results

    def download_hvsc_index(self) -> list[str] | None:
        if not self.paths.hvsc_songlengths_url:
            self.logger.error("HVSC: no songlengths_url configured")
            return None
        try:
            result = subprocess.run(
                ["curl", "-sL", "--max-time", "120", self.paths.hvsc_songlengths_url],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode != 0 or not result.stdout:
                self.logger.error("HVSC index download failed (exit %d)", result.returncode)
                return None
            tracks = self.parse_songlengths_to_tracks(result.stdout)
            try:
                with open(self.paths.hvsc_cache_file, "w") as handle:
                    json.dump(
                        {"tracks": tracks, "durations": self.sid_durations, "downloaded": time.time()},
                        handle,
                    )
            except Exception as exc:
                self.logger.warning("HVSC: cache write failed: %s", exc)
            self.logger.info("HVSC: loaded %d SID tracks", len(tracks))
            return tracks
        except Exception as exc:
            self.logger.error("HVSC index error: %s", exc)
            return None

    def load_cached_hvsc(self) -> list[str] | None:
        try:
            if not os.path.exists(self.paths.hvsc_cache_file):
                return None
            with open(self.paths.hvsc_cache_file) as handle:
                data = json.load(handle)
            age = time.time() - data.get("downloaded", 0)
            if age > self.paths.hvsc_cache_ttl_hours * 3600:
                self.logger.info("HVSC cache expired (%.1f hours old)", age / 3600)
                return None
            tracks = data.get("tracks", [])
            cached_durs = data.get("durations", {})
            if cached_durs:
                self.sid_durations.clear()
                for key, value in cached_durs.items():
                    self.sid_durations[key] = int(value) if not isinstance(value, int) else value
                self.logger.info("HVSC: restored %d durations from cache", len(cached_durs))
            self.logger.info("HVSC: loaded %d tracks from cache", len(tracks))
            return tracks
        except Exception as exc:
            self.logger.warning("HVSC cache load error: %s", exc)
            return None

    def _load_json_cache(self, cache_path: str) -> dict | list | None:
        try:
            if not os.path.exists(cache_path):
                return None
            with open(cache_path) as handle:
                return json.load(handle)
        except Exception as exc:
            self.logger.warning("Cache load error (%s): %s", os.path.basename(cache_path), exc)
            return None

    def _load_path_cache(self, cache_path: str, label: str) -> list[str] | None:
        data = self._load_json_cache(cache_path)
        if not isinstance(data, dict):
            return None
        tracks = [track["path"] for track in data.get("tracks", [])]
        self.logger.info("%s: loaded %d tracks from cache", label, len(tracks))
        return tracks

    def load_ay_cache(self) -> list[str] | None:
        return self._load_path_cache(self.paths.ay_cache, "AY")

    def load_ym_cache(self) -> list[str] | None:
        return self._load_path_cache(self.paths.ym_cache, "YM")

    def load_tiny_cache(self) -> list[str] | None:
        return self._load_path_cache(self.paths.tiny_cache, "Tiny")

    def load_asma_local_cache(self) -> list[str] | None:
        return self._load_path_cache(self.paths.asma_local_cache, "ASMA")

    def load_hvsc_local_cache(self) -> list[str] | None:
        return self._load_path_cache(self.paths.hvsc_local_cache, "HVSC")

    def load_modarchive_cache(self) -> list[str] | None:
        try:
            if not os.path.exists(self.paths.modarchive_cache_file):
                return None
            with open(self.paths.modarchive_cache_file) as handle:
                modules = json.load(handle)
            if not isinstance(modules, list) or len(modules) < 10:
                self.logger.warning("ModArchive cache too small (%d entries), rebuilding needed", len(modules))
                return None
            modarchive_name_map: dict[str, str] = {}
            tracks = []
            for module in modules:
                if isinstance(module, dict) and "url" in module:
                    tracks.append(module["url"])
                    modarchive_name_map[module["url"]] = module.get("name", module["url"].split("=")[-1])
            self.replace_modarchive_name_map(modarchive_name_map)
            self.logger.info("ModArchive: loaded %d tracks from cache (%d raw entries)", len(tracks), len(modules))
            return tracks
        except Exception as exc:
            self.logger.warning("ModArchive cache load error: %s", exc)
            return None

    def load_snes_cache(self) -> list[str] | None:
        try:
            if not os.path.exists(self.paths.snes_cache_file):
                return None
            with open(self.paths.snes_cache_file) as handle:
                data = json.load(handle)
            game_sets = data.get("tracks", [])
            urls = []
            snes_metadata: dict[str, dict[str, object]] = {}
            for game in game_sets:
                url = game.get("rsn_url", "")
                if url:
                    urls.append(url)
                    snes_metadata[url] = game
            self.replace_snes_metadata(snes_metadata)
            self.logger.info("SNES: loaded %d game sets from cache", len(urls))
            return urls
        except Exception as exc:
            self.logger.warning("SNES cache load error: %s", exc)
            return None

    def get_collection_info(self, mode: str) -> CollectionInfo:
        collection_info = {
            "asma": CollectionInfo("🟢", "Atari SAP (ASMA)", "ASMA Radio", "ASMA Radio", "green", self.load_asma_local_cache),
            "hvsc": CollectionInfo("🟣", "C64 SID (HVSC)", "C64 SID Radio", "C64 SID Radio", "purple", self.load_hvsc_local_cache),
            "modarchive": CollectionInfo(
                "🟠",
                "Tracker Modules (ModArchive)",
                "ModArchive Radio",
                "ModArchive Radio — FastTracker / MOD / XM / S3M / IT",
                "#E67E22",
                self.load_modarchive_cache,
            ),
            "ay": CollectionInfo("🔵", "ZX Spectrum AY (Local Archive)", "ZX Spectrum Radio", "ZX Spectrum Radio — AY chiptunes", "blue", self.load_ay_cache),
            "ym": CollectionInfo("🎹", "Atari ST YM (Local Archive)", "Atari ST YM Radio", "Atari ST YM Radio — YM2149 chiptunes", "#F1C40F", self.load_ym_cache),
            "tiny": CollectionInfo("🎵", "Tiny Music (Demoscene Modules)", "Tiny Music Radio", "Tiny Music — curated demoscene modules", "purple", self.load_tiny_cache),
            "spc": CollectionInfo("🔴", "SNES SPC (SNESmusic.org)", "SNES Radio", "SNES Radio — Super Nintendo SPC chiptunes", "#E74C3C", self.load_snes_cache),
        }
        return collection_info.get(mode, collection_info["asma"])

    async def load_tracks_for_mode(self, mode: str) -> list[str] | None:
        info = self.get_collection_info(mode)
        result = await asyncio.to_thread(info.load_tracks)
        tracks = await result if isinstance(result, Awaitable) else result
        if not tracks and mode == "hvsc" and info.fallback_load:
            self.logger.info("HVSC: cache empty, downloading index...")
            fallback = await asyncio.to_thread(info.fallback_load)
            tracks = await fallback if isinstance(fallback, Awaitable) else fallback
        return tracks
