"""Derived application configuration and filesystem paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from domain_archive_config import ArchiveRuntimeConfig


@dataclass(slots=True)
class PlaybackConfig:
    bot_token: str
    sink_name: str
    command_prefix: str
    playback_loop: bool
    playback_shuffle: bool
    crossfade_secs: int
    auto_start_channel: str
    auto_empty_timeout: int
    guild_id: int | None


@dataclass(slots=True)
class PathConfig:
    root_dir: str
    temp_dir: str
    queue_dir: str
    ay_dir: str
    ay_cache: str
    ym_dir: str
    ym_cache: str
    ym_temp_dir: str
    tiny_dir: str
    tiny_cache: str
    asma_dir: str
    hvsc_dir: str
    asma_local_cache: str
    hvsc_local_cache: str
    favorites_file: str
    playlist_dir: str
    blacklist_file: str
    last_collection_file: str
    snes_cache_file: str
    snes_spc_dir: str
    hvsc_cache_file: str
    modarchive_cache_file: str
    metadata_cache: str


@dataclass(slots=True)
class ArchiveConfig:
    asma_base: str
    crawl_timeout: int
    cache_ttl: int
    cache_file: str
    top_level_dirs: list[str]
    snes_base: str
    hvsc_base: str
    hvsc_songlengths_url: str
    hvsc_cache_ttl: int
    default_collection_mode: str
    modarchive_base: str
    modarchive_download: str
    archive_runtime_config: ArchiveRuntimeConfig


@dataclass(slots=True)
class AppConfig:
    config: dict[str, Any]
    playback: PlaybackConfig
    paths: PathConfig
    archive: ArchiveConfig

    @property
    def root_dir(self) -> str: return self.paths.root_dir
    @property
    def bot_token(self) -> str: return self.playback.bot_token
    @property
    def sink_name(self) -> str: return self.playback.sink_name
    @property
    def temp_dir(self) -> str: return self.paths.temp_dir
    @property
    def asma_base(self) -> str: return self.archive.asma_base
    @property
    def crawl_timeout(self) -> int: return self.archive.crawl_timeout
    @property
    def cache_ttl(self) -> int: return self.archive.cache_ttl
    @property
    def cache_file(self) -> str: return self.archive.cache_file
    @property
    def top_level_dirs(self) -> list[str]: return self.archive.top_level_dirs
    @property
    def queue_dir(self) -> str: return self.paths.queue_dir
    @property
    def command_prefix(self) -> str: return self.playback.command_prefix
    @property
    def playback_loop(self) -> bool: return self.playback.playback_loop
    @property
    def playback_shuffle(self) -> bool: return self.playback.playback_shuffle
    @property
    def ay_dir(self) -> str: return self.paths.ay_dir
    @property
    def ay_cache(self) -> str: return self.paths.ay_cache
    @property
    def ym_dir(self) -> str: return self.paths.ym_dir
    @property
    def ym_cache(self) -> str: return self.paths.ym_cache
    @property
    def ym_temp_dir(self) -> str: return self.paths.ym_temp_dir
    @property
    def tiny_dir(self) -> str: return self.paths.tiny_dir
    @property
    def tiny_cache(self) -> str: return self.paths.tiny_cache
    @property
    def asma_dir(self) -> str: return self.paths.asma_dir
    @property
    def hvsc_dir(self) -> str: return self.paths.hvsc_dir
    @property
    def asma_local_cache(self) -> str: return self.paths.asma_local_cache
    @property
    def hvsc_local_cache(self) -> str: return self.paths.hvsc_local_cache
    @property
    def favorites_file(self) -> str: return self.paths.favorites_file
    @property
    def playlist_dir(self) -> str: return self.paths.playlist_dir
    @property
    def blacklist_file(self) -> str: return self.paths.blacklist_file
    @property
    def last_collection_file(self) -> str: return self.paths.last_collection_file
    @property
    def snes_base(self) -> str: return self.archive.snes_base
    @property
    def snes_cache_file(self) -> str: return self.paths.snes_cache_file
    @property
    def snes_spc_dir(self) -> str: return self.paths.snes_spc_dir
    @property
    def hvsc_base(self) -> str: return self.archive.hvsc_base
    @property
    def hvsc_songlengths_url(self) -> str: return self.archive.hvsc_songlengths_url
    @property
    def hvsc_cache_ttl(self) -> int: return self.archive.hvsc_cache_ttl
    @property
    def hvsc_cache_file(self) -> str: return self.paths.hvsc_cache_file
    @property
    def default_collection_mode(self) -> str: return self.archive.default_collection_mode
    @property
    def modarchive_base(self) -> str: return self.archive.modarchive_base
    @property
    def modarchive_download(self) -> str: return self.archive.modarchive_download
    @property
    def modarchive_cache_file(self) -> str: return self.paths.modarchive_cache_file
    @property
    def metadata_cache(self) -> str: return self.paths.metadata_cache
    @property
    def crossfade_secs(self) -> int: return self.playback.crossfade_secs
    @property
    def auto_start_channel(self) -> str: return self.playback.auto_start_channel
    @property
    def auto_empty_timeout(self) -> int: return self.playback.auto_empty_timeout
    @property
    def guild_id(self) -> int | None: return self.playback.guild_id
    @property
    def archive_runtime_config(self) -> ArchiveRuntimeConfig: return self.archive.archive_runtime_config


def derive_app_config(root_dir: str, config: dict[str, Any]) -> AppConfig:
    bot_token = os.getenv("DISCORD_BOT_TOKEN", config.get("token", ""))
    sink_name = config["audio"]["sink_name"]
    temp_dir = os.path.join(root_dir, "tmp")
    asma_base = config["asma"]["base_url"]
    crawl_timeout = config["asma"]["crawl_timeout"]
    cache_ttl = config["asma"]["cache_ttl"]
    cache_file = os.path.join(root_dir, "asma_cache.json")
    top_level_dirs = list(config["asma"]["top_dirs"])
    queue_dir = os.path.join(root_dir, "queues")
    command_prefix = config["command_prefix"]
    playback_loop = config["playback"]["loop"]
    playback_shuffle = config["playback"]["shuffle"]

    ay_dir = os.path.join(root_dir, "archiwum", "ay")
    ay_cache = os.path.join(root_dir, "ay_cache.json")
    ym_dir = os.path.join(root_dir, "archiwum", "ym")
    ym_cache = os.path.join(root_dir, "ym_cache.json")
    ym_temp_dir = os.path.join(ym_dir, "tmp_wav")
    tiny_dir = os.path.join(root_dir, "archiwum", "tiny")
    tiny_cache = os.path.join(root_dir, "tiny_cache.json")
    asma_dir = os.path.join(root_dir, "archiwum", "asma")
    hvsc_dir = os.path.join(root_dir, "archiwum", "hvsc", "C64Music")
    asma_local_cache = os.path.join(root_dir, "asma_cache_local.json")
    hvsc_local_cache = os.path.join(root_dir, "hvsc_cache_local.json")
    favorites_file = os.path.join(root_dir, "favorites.json")
    playlist_dir = os.path.join(root_dir, "playlists")
    blacklist_file = os.path.join(root_dir, "blacklist.json")
    last_collection_file = os.path.join(root_dir, "last_collection.txt")

    snes_base = "https://snesmusic.org/v2/"
    snes_cache_file = os.path.join(root_dir, "snes_cache.json")
    snes_spc_dir = os.path.join(root_dir, "archiwum", "spc")
    hvsc_base = config.get("hvsc", {}).get("base_url", "https://www.hvsc.c64.org/download/C64Music/")
    hvsc_songlengths_url = config.get("hvsc", {}).get("songlengths_url", "")
    hvsc_cache_ttl = config.get("hvsc", {}).get("cache_ttl", 168)
    hvsc_cache_file = os.path.join(root_dir, "hvsc_cache.json")
    default_collection_mode = "hvsc" if config.get("hvsc", {}).get("enabled", False) else "asma"

    modarchive_base = config.get("modarchive", {}).get("base_url", "https://modarchive.org/index.php")
    modarchive_download = config.get("modarchive", {}).get("download_url", "https://api.modarchive.org/downloads.php")
    modarchive_cache_file = os.path.join(
        root_dir,
        config.get("modarchive", {}).get("cache_file", "modarchive_cache.json"),
    )
    metadata_cache = os.path.join(root_dir, "metadata_cache.json")

    archive_runtime_config = ArchiveRuntimeConfig(
        asma_base=asma_base,
        asma_dir=asma_dir,
        asma_local_cache=asma_local_cache,
        ay_cache=ay_cache,
        hvsc_base=hvsc_base,
        hvsc_cache_file=hvsc_cache_file,
        hvsc_cache_ttl_hours=hvsc_cache_ttl,
        hvsc_local_cache=hvsc_local_cache,
        hvsc_songlengths_url=hvsc_songlengths_url,
        metadata_cache=metadata_cache,
        modarchive_cache_file=modarchive_cache_file,
        snes_cache_file=snes_cache_file,
        tiny_cache=tiny_cache,
        ym_cache=ym_cache,
        crawl_timeout=crawl_timeout,
        cache_ttl_hours=cache_ttl,
        cache_file=cache_file,
        top_level_dirs=top_level_dirs,
        crawl_concurrency=config["asma"].get("crawl_concurrency", 5),
    )

    playback = PlaybackConfig(
        bot_token=bot_token,
        sink_name=sink_name,
        command_prefix=command_prefix,
        playback_loop=playback_loop,
        playback_shuffle=playback_shuffle,
        crossfade_secs=config["playback"].get("crossfade", 0),
        auto_start_channel=config["auto"].get("start_channel", ""),
        auto_empty_timeout=config["auto"].get("empty_timeout", 60),
        guild_id=config.get("guild_id"),
    )
    paths = PathConfig(
        root_dir=root_dir,
        temp_dir=temp_dir,
        queue_dir=queue_dir,
        ay_dir=ay_dir,
        ay_cache=ay_cache,
        ym_dir=ym_dir,
        ym_cache=ym_cache,
        ym_temp_dir=ym_temp_dir,
        tiny_dir=tiny_dir,
        tiny_cache=tiny_cache,
        asma_dir=asma_dir,
        hvsc_dir=hvsc_dir,
        asma_local_cache=asma_local_cache,
        hvsc_local_cache=hvsc_local_cache,
        favorites_file=favorites_file,
        playlist_dir=playlist_dir,
        blacklist_file=blacklist_file,
        last_collection_file=last_collection_file,
        snes_cache_file=snes_cache_file,
        snes_spc_dir=snes_spc_dir,
        hvsc_cache_file=hvsc_cache_file,
        modarchive_cache_file=modarchive_cache_file,
        metadata_cache=metadata_cache,
    )
    archive = ArchiveConfig(
        asma_base=asma_base,
        crawl_timeout=crawl_timeout,
        cache_ttl=cache_ttl,
        cache_file=cache_file,
        top_level_dirs=top_level_dirs,
        snes_base=snes_base,
        hvsc_base=hvsc_base,
        hvsc_songlengths_url=hvsc_songlengths_url,
        hvsc_cache_ttl=hvsc_cache_ttl,
        default_collection_mode=default_collection_mode,
        modarchive_base=modarchive_base,
        modarchive_download=modarchive_download,
        archive_runtime_config=archive_runtime_config,
    )

    return AppConfig(
        config=config,
        playback=playback,
        paths=paths,
        archive=archive,
    )
