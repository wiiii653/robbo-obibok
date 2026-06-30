"""Application state/store/archive construction helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable, Mapping

from archive_catalog import ArchiveCatalog, ArchivePaths
from app_services import AppServices
from app_state import AppRuntimeState, CachedJsonStore, PlaylistLibraryStore


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


def build_app_context(
    *,
    queue_dir: str,
    default_collection_mode: str,
    favorites_file: str,
    blacklist_file: str,
    playlist_dir: str,
    archive_paths: ArchivePaths,
    json_writer: Callable[[str, dict], None],
    logger: logging.Logger,
) -> AppContext:
    app_state = AppRuntimeState(
        queue_dir=queue_dir,
        default_collection_mode=default_collection_mode,
        json_writer=json_writer,
    )
    favorites_store = CachedJsonStore(favorites_file, json_writer=json_writer)
    blacklist_store = CachedJsonStore(blacklist_file, json_writer=json_writer)
    playlist_store = PlaylistLibraryStore(playlist_dir, json_writer=json_writer, logger=logger)
    archives = ArchiveCatalog(paths=archive_paths, logger=logger)
    return AppContext(
        app_state=app_state,
        favorites_store=favorites_store,
        blacklist_store=blacklist_store,
        playlist_store=playlist_store,
        archives=archives,
        metadata_index=archives.metadata_index_view,
        modarchive_name_map=archives.modarchive_name_map_view,
        sid_durations=archives.sid_durations_view,
        snes_metadata=archives.snes_metadata_view,
    )


def bootstrap_app(
    *,
    queue_dir: str,
    default_collection_mode: str,
    favorites_file: str,
    blacklist_file: str,
    playlist_dir: str,
    archive_paths: ArchivePaths,
    json_writer: Callable[[str, dict], None],
    logger: logging.Logger,
) -> BootstrappedApp:
    context = build_app_context(
        queue_dir=queue_dir,
        default_collection_mode=default_collection_mode,
        favorites_file=favorites_file,
        blacklist_file=blacklist_file,
        playlist_dir=playlist_dir,
        archive_paths=archive_paths,
        json_writer=json_writer,
        logger=logger,
    )
    services = AppServices(
        app_state=context.app_state,
        favorites_store=context.favorites_store,
        blacklist_store=context.blacklist_store,
        playlist_store=context.playlist_store,
    )
    return BootstrappedApp(
        context=context,
        services=services,
        archive_views=ArchiveRegistryViews(
            metadata_index=context.metadata_index,
            modarchive_name_map=context.modarchive_name_map,
            sid_durations=context.sid_durations,
            snes_metadata=context.snes_metadata,
        ),
    )
