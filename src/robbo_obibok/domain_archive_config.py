"""Archive runtime configuration — pure domain model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ArchiveRuntimeConfig:
    asma_base: str = ""
    asma_dir: str = ""
    asma_local_cache: str = ""
    ay_cache: str = ""
    hvsc_base: str = ""
    hvsc_cache_file: str = ""
    hvsc_cache_ttl_hours: int = 0
    hvsc_local_cache: str = ""
    hvsc_songlengths_url: str = ""
    metadata_cache: str = ""
    modarchive_cache_file: str = ""
    snes_cache_file: str = ""
    tiny_cache: str = ""
    ym_cache: str = ""
    crawl_timeout: int = 0
    cache_ttl_hours: int = 0
    cache_file: str = ""
    top_level_dirs: list[str] | None = None
    crawl_concurrency: int = 5


ArchivePaths = ArchiveRuntimeConfig
