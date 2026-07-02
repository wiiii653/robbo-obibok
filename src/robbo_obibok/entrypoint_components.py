"""Lazy entrypoint component graph assembly."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

from . import entrypoint_state as state_protocols
from .app_context import AppContext, ArchiveRegistryViews, BootstrappedApp
from .app_services import AppServicesProtocol
from .archive_catalog import ArchiveCatalog
from .archive_runtime import ArchiveRuntime, ArchiveRuntimeConfig
from .collection_catalog import build_collections
from .collection_specs import CollectionSpec
from .domain_state import AppRuntimeState, PlaylistState
from .entrypoint_bootstrap import EntrypointBootstrapBuilder
from .playback_assets import PlaybackAssetRuntime
from .playback_helpers import NowPlayingDependencies
from .runtime_bindings import LegacyRuntimeBindings
from .runtime_protocols import SubsongRuntimeProtocol
from .runtime_service_facade import RuntimeServiceFacade
from .stream_runtime import StreamRuntime

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from .stream_runtime import MonitorAudioSource


def _build_now_playing_embed(**kwargs):
    import discord

    return discord.Embed(**kwargs)


def build_service_facade(
    *,
    app_services: AppServicesProtocol,
    blacklist_filter: Callable[[list[str], dict, int | str], list[str]],
    logger: logging.Logger,
    stop_all_players_impl,
    subsongs: SubsongRuntimeProtocol,
) -> RuntimeServiceFacade:
    return RuntimeServiceFacade(
        app_services=app_services,
        blacklist_loader=app_services.load_blacklist,
        blacklist_filter=blacklist_filter,
        logger=logger,
        stop_all_players_impl=stop_all_players_impl,
        subsongs=subsongs,
    )


def build_stream_runtime(
    *,
    sink_name: str,
    audio_format: str,
    sample_rate: int,
    channels: int,
    logger: logging.Logger,
    clear_predownload_state: Callable[..., None],
) -> StreamRuntime:
    return StreamRuntime(
        sink_name=sink_name,
        audio_format=audio_format,
        sample_rate=sample_rate,
        channels=channels,
        logger=logger,
        clear_predownload_state=clear_predownload_state,
    )


def build_archive_runtime(
    *,
    archives: ArchiveCatalog,
    logger: logging.Logger,
    snes_spc_dir: str,
    temp_dir: str,
    build_temp_path: Callable[[str], str],
    get_shared_session: Callable[[], Awaitable[ClientSession]],
    config: ArchiveRuntimeConfig,
) -> ArchiveRuntime:
    return ArchiveRuntime(
        archives=archives,
        logger=logger,
        snes_spc_dir=snes_spc_dir,
        temp_dir=temp_dir,
        build_temp_path=build_temp_path,
        get_shared_session=get_shared_session,
        config=config,
    )


def build_playback_assets(
    *,
    asma_base: str,
    asma_dir: str,
    hvsc_base: str,
    hvsc_dir: str,
    ym_temp_dir: str,
    logger: logging.Logger,
    build_temp_path: Callable[[str], str],
    get_shared_session: Callable[[], Awaitable[ClientSession]],
) -> PlaybackAssetRuntime:
    return PlaybackAssetRuntime(
        asma_base=asma_base,
        asma_dir=asma_dir,
        hvsc_base=hvsc_base,
        hvsc_dir=hvsc_dir,
        ym_temp_dir=ym_temp_dir,
        logger=logger,
        build_temp_path=build_temp_path,
        get_shared_session=get_shared_session,
    )


def build_now_playing_dependencies(
    *,
    audacious_play: Callable[[str], None],
    audacious_stop: Callable[[], None],
    register_np_message: Callable[[int, str, str, str], None],
    setup_monitor_source: Callable[[object], None],
) -> NowPlayingDependencies:
    return NowPlayingDependencies(
        audacious_play=audacious_play,
        audacious_stop=audacious_stop,
        embed_factory=_build_now_playing_embed,
        register_np_message=register_np_message,
        setup_monitor_source=setup_monitor_source,
    )


def build_collection_loaders(
    *,
    archive_runtime: ArchiveRuntime,
):
    return build_collections(
        load_asma_local_cache=archive_runtime.load_asma_local_cache,
        load_hvsc_local_cache=archive_runtime.load_hvsc_local_cache,
        load_modarchive_cache=archive_runtime.load_modarchive_cache,
        load_ay_cache=archive_runtime.load_ay_cache,
        load_ym_cache=archive_runtime.load_ym_cache,
        load_tiny_cache=archive_runtime.load_tiny_cache,
        load_snes_cache=archive_runtime.load_snes_cache,
    )


@dataclass(slots=True)
class EntrypointBootstrapBundle:
    bootstrapped_app: BootstrappedApp
    app_context: AppContext
    app_state: AppRuntimeState
    archives: ArchiveCatalog
    app_services: AppServicesProtocol
    archive_views: ArchiveRegistryViews


@dataclass(slots=True)
class EntrypointRuntimeBundle:
    service_facade: RuntimeServiceFacade
    stream_runtime: StreamRuntime
    active_streams: dict[int, "MonitorAudioSource"]
    archive_runtime: ArchiveRuntime


@dataclass(slots=True)
class EntrypointMediaBundle:
    playback_assets: PlaybackAssetRuntime
    now_playing_deps: NowPlayingDependencies
    collections: dict[str, CollectionSpec]
    legacy: LegacyRuntimeBindings


@dataclass(slots=True)
class EntrypointComponents:
    bootstrap: EntrypointBootstrapBundle
    runtime: EntrypointRuntimeBundle
    media: EntrypointMediaBundle


@dataclass(slots=True)
class EntrypointComponentDeps:
    boot_builder: EntrypointBootstrapBuilder
    logger: logging.Logger
    sink_name: str
    audio_format: str
    sample_rate: int
    channels: int
    temp_dir: str
    archive_runtime_config: ArchiveRuntimeConfig
    subsongs: SubsongRuntimeProtocol
    build_temp_path: Callable[[str], str]
    get_shared_session: Callable[[], Awaitable[ClientSession]]
    clear_predownload_state: Callable[[PlaylistState], None]
    blacklist_filter: Callable[[list[str], dict[object, object], int | str], list[str]]
    stop_all_players_impl: Callable[..., None]
    audacious_play: Callable[[str], None]
    audacious_stop: Callable[[], None]
    cleanup_subsong_temp_wavs_impl: Callable[[PlaylistState], None]
    build_legacy_bindings: Callable[..., LegacyRuntimeBindings]


def build_entrypoint_components(
    deps: EntrypointComponentDeps,
) -> EntrypointComponents:
    boot = deps.boot_builder.materialize()
    service_facade = build_service_facade(
        app_services=boot.app_services,
        blacklist_filter=deps.blacklist_filter,
        logger=deps.logger,
        stop_all_players_impl=deps.stop_all_players_impl,
        subsongs=deps.subsongs,
    )
    stream_runtime = build_stream_runtime(
        sink_name=deps.sink_name,
        audio_format=deps.audio_format,
        sample_rate=deps.sample_rate,
        channels=deps.channels,
        logger=deps.logger,
        clear_predownload_state=deps.clear_predownload_state,
    )
    archive_runtime = build_archive_runtime(
        archives=boot.archives,
        logger=deps.logger,
        snes_spc_dir=boot.app_cfg.snes_spc_dir,
        temp_dir=deps.temp_dir,
        build_temp_path=deps.build_temp_path,
        get_shared_session=deps.get_shared_session,
        config=deps.archive_runtime_config,
    )
    playback_assets = build_playback_assets(
        asma_base=boot.app_cfg.asma_base,
        asma_dir=boot.app_cfg.asma_dir,
        hvsc_base=boot.app_cfg.hvsc_base,
        hvsc_dir=boot.app_cfg.hvsc_dir,
        ym_temp_dir=boot.app_cfg.ym_temp_dir,
        logger=deps.logger,
        build_temp_path=deps.build_temp_path,
        get_shared_session=deps.get_shared_session,
    )
    now_playing_deps = build_now_playing_dependencies(
        audacious_play=deps.audacious_play,
        audacious_stop=deps.audacious_stop,
        register_np_message=boot.app_services.register_now_playing_message,
        setup_monitor_source=stream_runtime.setup_monitor_source,
    )
    collections = build_collection_loaders(
        archive_runtime=archive_runtime,
    )
    legacy = deps.build_legacy_bindings(
        archive_runtime=archive_runtime,
        playback_assets=playback_assets,
        service_facade=service_facade,
        cleanup_subsong_temp_wavs_impl=deps.cleanup_subsong_temp_wavs_impl,
    )
    metadata_cache = archive_runtime.load_metadata_cache()
    boot.archives.store_metadata_entries(metadata_cache)
    return EntrypointComponents(
        bootstrap=EntrypointBootstrapBundle(
            bootstrapped_app=boot.bootstrapped_app,
            app_context=boot.app_context,
            app_state=boot.app_state,
            archives=boot.archives,
            app_services=boot.app_services,
            archive_views=boot.archive_views,
        ),
        runtime=EntrypointRuntimeBundle(
            service_facade=service_facade,
            stream_runtime=stream_runtime,
            active_streams=stream_runtime.active_streams,
            archive_runtime=archive_runtime,
        ),
        media=EntrypointMediaBundle(
            playback_assets=playback_assets,
            now_playing_deps=now_playing_deps,
            collections=collections,
            legacy=legacy,
        ),
    )


def apply_entrypoint_components(
    state: state_protocols.EntrypointComponentAssemblyStateProtocol,
    components: EntrypointComponents,
) -> None:
    if hasattr(state, "apply_bootstrap_registry"):
        state.apply_bootstrap_registry(
            bootstrapped_app=components.bootstrap.bootstrapped_app,
            app_context=components.bootstrap.app_context,
            app_state=components.bootstrap.app_state,
            archives=components.bootstrap.archives,
            app_services=components.bootstrap.app_services,
            archive_views=components.bootstrap.archive_views,
        )
    else:
        state.bootstrapped_app = components.bootstrap.bootstrapped_app
        state.app_context = components.bootstrap.app_context
        state.app_state = components.bootstrap.app_state
        state.archives = components.bootstrap.archives
        state.app_services = components.bootstrap.app_services
        state.archive_views = components.bootstrap.archive_views
    if hasattr(state, "apply_runtime_components"):
        state.apply_runtime_components(
            service_facade=components.runtime.service_facade,
            stream_runtime=components.runtime.stream_runtime,
            active_streams=components.runtime.active_streams,
            archive_runtime=components.runtime.archive_runtime,
            playback_assets=components.media.playback_assets,
            now_playing_deps=components.media.now_playing_deps,
            collections=components.media.collections,
            legacy=components.media.legacy,
        )
    else:
        state.service_facade = components.runtime.service_facade
        state.stream_runtime = components.runtime.stream_runtime
        state.active_streams = components.runtime.active_streams
        state.archive_runtime = components.runtime.archive_runtime
        state.playback_assets = components.media.playback_assets
        state.now_playing_deps = components.media.now_playing_deps
        state.collections = components.media.collections
        state.legacy = components.media.legacy
