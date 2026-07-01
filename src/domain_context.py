"""Application state types — pure domain models (no IO, no upper-layer deps)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from domain_services import AppServices
from domain_state import AppRuntimeState


@dataclass(frozen=True, slots=True)
class ArchiveRegistryViews:
    metadata_index: Mapping[str, dict[str, str]]
    modarchive_name_map: Mapping[str, str]
    sid_durations: Mapping[str, int]
    snes_metadata: Mapping[str, dict[str, object]]


@dataclass(slots=True)
class BootstrappedApp:
    context: AppContext
    services: AppServices
    archive_views: ArchiveRegistryViews


@dataclass(slots=True)
class AppContext:
    app_state: AppRuntimeState
    favorites_store: CachedJsonStore
    blacklist_store: CachedJsonStore
    playlist_store: PlaylistLibraryStore
    archives: ArchiveCatalog
    metadata_index: Mapping[str, dict[str, str]]
    modarchive_name_map: Mapping[str, str]
    sid_durations: Mapping[str, int]
    snes_metadata: Mapping[str, dict[str, object]]
