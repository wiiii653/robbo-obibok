"""Application runtime composition for dependency bundles and shutdown flow."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Iterable, Mapping, cast

from app_services import AppServicesProtocol
from app_state import PlaylistState
from bot_dependencies import (
    CommandDecoratorFactory,
    LibraryCommandDependencies,
    PlaybackCommandDependencies,
    PlaybackHandlerDependencies,
    SearchTracksProtocol,
)
from bot_events import CoreEventDependencies
from collection_specs import CollectionSpec
from collection_service import CollectionArchiveProtocol, CollectionService
from session_runtime import (
    EmbedFactoryProtocol,
    MetadataSessionDependencies,
    PlaybackSessionContext,
    PlaybackSessionDependencies,
)

if TYPE_CHECKING:
    import discord
    from aiohttp import ClientSession
    from archive_catalog import CollectionInfo
    from discord.ext import commands
    from stream_runtime import MonitorAudioSource


@dataclass(slots=True)
class RuntimeConfig:
    ASMA_BASE: str
    ASMA_DIR: str
    AUTO_START_CHANNEL: str | None
    AY_DIR: str
    FLIP_ORDER: list[str]
    FLIP_SEQ: list[str]
    HVSC_DIR: str
    LOCK_FILE: str
    PLAYBACK_LOOP: bool
    PLAYBACK_SHUFFLE: bool
    PLAYLIST_DIR: str
    ROOT_DIR: str
    SINK_NAME: str
    TEMP_DIR: str
    TINY_DIR: str
    YM_DIR: str


@dataclass(slots=True)
class MetadataIndexStore:
    entries: dict[str, dict[str, str]]

    def get(self, url: str) -> dict[str, str] | None:
        return self.entries.get(url)

    def contains(self, url: str) -> bool:
        return url in self.entries

    def size(self) -> int:
        return len(self.entries)

    def store(self, url: str, metadata: dict[str, str]) -> None:
        self.entries[url] = metadata

    def snapshot(self) -> dict[str, dict[str, str]]:
        return dict(self.entries)


@dataclass(slots=True)
class ModArchiveNameStore:
    entries: Mapping[str, str]

    def get(self, url: str) -> str | None:
        return self.entries.get(url)


@dataclass(slots=True)
class SnesMetadataStore:
    entries: Mapping[str, dict[str, object]]

    def contains_any(self) -> bool:
        return bool(self.entries)

    def contains(self, url: str) -> bool:
        return url in self.entries

    def get(self, url: str) -> dict[str, object] | None:
        return self.entries.get(url)

    def items(self) -> Iterable[tuple[str, dict[str, object]]]:
        return self.entries.items()


@dataclass(slots=True)
class RuntimeState:
    active_streams: dict[int, "MonitorAudioSource"]
    app_services: AppServicesProtocol
    bot: "commands.Bot"
    collections: dict[str, CollectionSpec]
    metadata_index: dict[str, dict[str, str]]
    modarchive_name_map: Mapping[str, str]
    shutdown_flag: asyncio.Event
    snes_metadata: Mapping[str, dict[str, object]]
    status_count_cache: dict[str, tuple[float, int | str]]
    metadata_store: MetadataIndexStore | None = None
    modarchive_store: ModArchiveNameStore | None = None
    snes_store: SnesMetadataStore | None = None
    playback_handlers: dict[str, Callable[..., Awaitable[bool]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.metadata_store is None:
            self.metadata_store = MetadataIndexStore(self.metadata_index)
        if self.modarchive_store is None:
            self.modarchive_store = ModArchiveNameStore(self.modarchive_name_map)
        if self.snes_store is None:
            self.snes_store = SnesMetadataStore(self.snes_metadata)


@dataclass(slots=True)
class PlaybackSessionCallbacks:
    apply_queue_state: Callable[[PlaylistState, dict[str, object]], bool]
    classify_track_route: Callable[..., dict[str, str]]
    clear_predownload_state: Callable[..., None]
    download_sap: Callable[..., Awaitable[str]]
    embed_factory: EmbedFactoryProtocol
    ensure_tracks: Callable[[PlaylistState], Awaitable[bool]]
    filter_blacklisted: Callable[[list[str], int | str], list[str]]
    get_collection_info: Callable[[str], "CollectionInfo"]
    load_asma_local_cache: Callable[[], list[str] | None]
    monitor_playback: Callable[..., Coroutine[Any, Any, None]]
    parse_sap_header: Callable[[str], dict[str, str]]
    place_track_in_queue: Callable[[list[str], str], tuple[list[str], int]]
    prepare_playback_queue: Callable[..., dict[str, object]]
    register_np_message: Callable[[int, str, str, str], None]


@dataclass(slots=True)
class PlaybackCommandCallbacks:
    apply_queue_state: Callable[[PlaylistState, dict[str, object]], bool]
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    clear_predownload_state: Callable[..., None]
    ensure_tracks: Callable[[PlaylistState], Awaitable[bool]]
    fetch_metadata_batch: Callable[..., Awaitable[dict[str, dict[str, str]]]]
    filter_blacklisted: Callable[[list[str], int | str], list[str]]
    get_collection_info: Callable[[str], "CollectionInfo"]
    is_playing: Callable[[], bool]
    load_snes_cache: Callable[[], list[str] | None]
    load_tracks_for_mode: Callable[[str], Awaitable[list[str] | None]]
    monitor_playback: Callable[..., Coroutine[Any, Any, None]]
    parse_sap_header: Callable[[str], dict[str, str]]
    parse_sid_header: Callable[[bytes], dict[str, str]]
    play_current_track: Callable[[object], Awaitable[bool]]
    prepare_playback_queue: Callable[..., dict[str, object]]
    register_np_message: Callable[[int, str, str, str], None]
    search_tracks: SearchTracksProtocol
    skip_to_next: Callable[[object], Awaitable[None]]


@dataclass(slots=True)
class PlaybackHandlerCallbacks:
    audacious_play: Callable[[str], None]
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    build_temp_path: Callable[[str], str]
    cleanup_subsong_temp_wavs: Callable[[PlaylistState], None]
    clear_predownload_state: Callable[..., None]
    download_modarchive_module: Callable[..., Awaitable[str]]
    download_sap: Callable[..., Awaitable[str]]
    download_spc_rsn: Callable[..., Awaitable[str | None]]
    get_shared_session: Callable[[], Awaitable[ClientSession]]
    get_subsongs: Callable[[str], list[float]]
    parse_sap_header: Callable[[str], dict[str, str]]
    parse_sid_header: Callable[[bytes], dict[str, str]]
    play_via_audacious: Callable[..., Awaitable[None]]
    queue_position: Callable[[PlaylistState], tuple[int, int]]
    register_np_message: Callable[[int, str, str, str], None]
    resolve_local_path: Callable[[str], str | None]
    send_now_playing_embed: Callable[..., Awaitable[None]]
    set_ym_last_wav_path: Callable[[str | None], None]
    setup_monitor_source: Callable[[object], None]
    ym_cleanup: Callable[[], None]
    ym_to_wav: Callable[[str], str]


@dataclass(slots=True)
class PlaybackCallbacks:
    session: PlaybackSessionCallbacks
    command: PlaybackCommandCallbacks
    handler: PlaybackHandlerCallbacks


@dataclass(slots=True)
class LibraryCallbacks:
    ensure_playlist_dir: Callable[[], None]
    filter_blacklisted_track_entries: Callable[[list[dict], dict, int], list[dict]]
    list_playlists: Callable[[], list[dict]]
    load_blacklist: Callable[[], dict]
    load_favorites: Callable[[], dict]
    load_playlist: Callable[[str], dict | None]
    load_user_tracks: Callable[[dict, int | str], list[dict]]
    remove_user_track: Callable[[dict, int | str, str], tuple[dict, bool]]
    save_blacklist: Callable[[dict], None]
    save_favorites: Callable[[dict], None]
    save_playlist: Callable[[str, list[dict], int, str], str]
    toggle_user_track_entry: Callable[[dict, int | str, dict], tuple[dict, bool]]


@dataclass(slots=True)
class CollectionCallbacks:
    auto_play_after_switch: Callable[[object, PlaylistState], Awaitable[None]]
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]]
    flip_sequence_formatter: Callable[[list[str], str], str]
    get_all_cache_counts: Callable[[dict[str, tuple[str, str]]], dict[str, tuple[str, int | str]]]
    load_hvsc_local_cache: Callable[[], list[str] | None]
    save_last_collection: Callable[[str], None]
    set_volume_for_collection: Callable[[str], None]
    stop_all_players: Callable[[], None]
    stop_state_streams: Callable[[PlaylistState], Awaitable[None]]
    switch_collection: Callable[..., Awaitable[bool]]


@dataclass(slots=True)
class BootstrapCallbacks:
    cleanup_temp_dir: Callable[..., None]
    close_shared_session: Callable[[], Awaitable[None]]
    log_preloaded_cache: Callable[[str, list[str] | None], None]
    logger: logging.Logger
    mod_only: CommandDecoratorFactory
    release_process_lock: Callable[[str], None]
    run_startup_steps: Callable[..., Awaitable[None]]
    save_metadata_cache: Callable[[dict], None]
    schedule_background_tasks: Callable[[list[Callable[[], Awaitable[None]]]], None]


@dataclass(slots=True)
class BotRuntime:
    config: RuntimeConfig
    state: RuntimeState
    playback: PlaybackCallbacks
    library: LibraryCallbacks
    collection: CollectionCallbacks
    bootstrap: BootstrapCallbacks

    def get_state(self, guild_id: int) -> PlaylistState:
        return self.state.app_services.get_state(guild_id)

    def save_queue(self, state: PlaylistState) -> None:
        self.state.app_services.save_queue(state)

    def load_queue(self, guild_id: int) -> dict | None:
        return self.state.app_services.load_queue(guild_id)

    def get_metadata_entry(self, url: str) -> dict[str, str] | None:
        assert self.state.metadata_store is not None
        return self.state.metadata_store.get(url)

    def has_metadata_entry(self, url: str) -> bool:
        assert self.state.metadata_store is not None
        return self.state.metadata_store.contains(url)

    def metadata_index_size(self) -> int:
        assert self.state.metadata_store is not None
        return self.state.metadata_store.size()

    def store_metadata_entry(self, url: str, metadata: dict[str, str]) -> None:
        assert self.state.metadata_store is not None
        self.state.metadata_store.store(url, metadata)

    def snapshot_metadata_index(self) -> dict[str, dict[str, str]]:
        assert self.state.metadata_store is not None
        return self.state.metadata_store.snapshot()

    def get_modarchive_track_name(self, url: str) -> str | None:
        assert self.state.modarchive_store is not None
        return self.state.modarchive_store.get(url)

    def has_snes_metadata(self) -> bool:
        assert self.state.snes_store is not None
        return self.state.snes_store.contains_any()

    def has_snes_game(self, url: str) -> bool:
        assert self.state.snes_store is not None
        return self.state.snes_store.contains(url)

    def get_snes_game(self, url: str) -> dict[str, object] | None:
        assert self.state.snes_store is not None
        return self.state.snes_store.get(url)

    def iter_snes_metadata(self) -> Iterable[tuple[str, dict[str, object]]]:
        assert self.state.snes_store is not None
        return self.state.snes_store.items()

    def build_playback_session_deps(self) -> PlaybackSessionDependencies:
        return PlaybackSessionDependencies(
            PLAYBACK_LOOP=self.config.PLAYBACK_LOOP,
            PLAYBACK_SHUFFLE=self.config.PLAYBACK_SHUFFLE,
            bot=self.state.bot,
            classify_track_route=self.playback.session.classify_track_route,
            clear_predownload_state=self.playback.session.clear_predownload_state,
            download_sap=self.playback.session.download_sap,
            embed_factory=self.playback.session.embed_factory,
            ensure_tracks=self.playback.session.ensure_tracks,
            filter_blacklisted=self.playback.session.filter_blacklisted,
            get_collection_info=self.playback.session.get_collection_info,
            get_state=self.get_state,
            get_snes_game=self.get_snes_game,
            has_snes_game=self.has_snes_game,
            load_asma_local_cache=self.playback.session.load_asma_local_cache,
            load_queue=self.load_queue,
            log=self.bootstrap.logger,
            monitor_playback=self.playback.session.monitor_playback,
            parse_sap_header=self.playback.session.parse_sap_header,
            playback_handlers=self.state.playback_handlers,
            prepare_playback_queue=self.playback.session.prepare_playback_queue,
            register_np_message=self.playback.session.register_np_message,
            save_queue=self.save_queue,
            apply_queue_state=self.playback.session.apply_queue_state,
            place_track_in_queue=self.playback.session.place_track_in_queue,
        )

    def build_metadata_session_deps(self) -> MetadataSessionDependencies:
        return MetadataSessionDependencies(
            asma_dir=self.config.ASMA_DIR,
            has_metadata_entry=self.has_metadata_entry,
            load_asma_local_cache=self.playback.session.load_asma_local_cache,
            log=self.bootstrap.logger,
            metadata_index_size=self.metadata_index_size,
            parse_sap_header=self.playback.session.parse_sap_header,
            save_metadata_cache=self.bootstrap.save_metadata_cache,
            snapshot_metadata_index=self.snapshot_metadata_index,
            store_metadata_entry=self.store_metadata_entry,
        )

    def build_collection_service(
        self,
        archives: CollectionArchiveProtocol,
        *,
        status_count_cache: dict[str, tuple[float, int | str]],
    ) -> CollectionService:
        return CollectionService(
            archives=archives,
            collections=self.state.collections,
            root_dir=self.config.ROOT_DIR,
            status_count_cache=status_count_cache,
            flip_sequence_formatter=self.collection.flip_sequence_formatter,
            build_collection_state_update=self.collection.build_collection_state_update,
            save_last_collection=self.collection.save_last_collection,
            set_volume_for_collection=self.collection.set_volume_for_collection,
            auto_play_after_switch=self.collection.auto_play_after_switch,
            get_state=self.get_state,
            stop_all_players=self.collection.stop_all_players,
            stop_state_streams=self.collection.stop_state_streams,
            log=self.bootstrap.logger,
        )

    def build_event_deps(self) -> CoreEventDependencies:
        return CoreEventDependencies(
            AUTO_START_CHANNEL=self.config.AUTO_START_CHANNEL,
            PLAYBACK_LOOP=self.config.PLAYBACK_LOOP,
            PLAYBACK_SHUFFLE=self.config.PLAYBACK_SHUFFLE,
            apply_queue_state=self.playback.session.apply_queue_state,
            ensure_tracks=self.playback.session.ensure_tracks,
            get_collection_info=self.playback.session.get_collection_info,
            get_state=self.get_state,
            load_queue=self.load_queue,
            log=self.bootstrap.logger,
            log_preloaded_cache=self.bootstrap.log_preloaded_cache,
            load_asma_local_cache=self.playback.session.load_asma_local_cache,
            load_hvsc_local_cache=self.collection.load_hvsc_local_cache,
            monitor_playback=self.playback.command.monitor_playback,
            play_current_track=self.playback.command.play_current_track,
            prepare_playback_queue=self.playback.command.prepare_playback_queue,
            run_startup_steps=self.bootstrap.run_startup_steps,
            save_queue=self.save_queue,
            schedule_background_tasks=self.bootstrap.schedule_background_tasks,
        )

    def build_playback_command_deps(self) -> PlaybackCommandDependencies:
        return PlaybackCommandDependencies(
            ASMA_BASE=self.config.ASMA_BASE,
            FLIP_ORDER=self.config.FLIP_ORDER,
            FLIP_SEQ=self.config.FLIP_SEQ,
            PLAYBACK_LOOP=self.config.PLAYBACK_LOOP,
            PLAYBACK_SHUFFLE=self.config.PLAYBACK_SHUFFLE,
            PLAYLIST_DIR=self.config.PLAYLIST_DIR,
            apply_queue_state=self.playback.command.apply_queue_state,
            audacious_song=self.playback.command.audacious_song,
            audacious_stop=self.playback.command.audacious_stop,
            clear_predownload_state=self.playback.command.clear_predownload_state,
            ensure_tracks=self.playback.command.ensure_tracks,
            fetch_metadata_batch=self.playback.command.fetch_metadata_batch,
            filter_blacklisted=self.playback.command.filter_blacklisted,
            get_all_cache_counts=self.collection.get_all_cache_counts,
            get_collection_info=self.playback.command.get_collection_info,
            get_state=self.get_state,
            is_playing=self.playback.command.is_playing,
            load_queue=self.load_queue,
            load_snes_cache=self.playback.command.load_snes_cache,
            load_tracks_for_mode=self.playback.command.load_tracks_for_mode,
            log=self.bootstrap.logger,
            get_metadata_entry=self.get_metadata_entry,
            metadata_index_size=self.metadata_index_size,
            mod_only=self.bootstrap.mod_only,
            get_modarchive_track_name=self.get_modarchive_track_name,
            monitor_playback=self.playback.command.monitor_playback,
            parse_sap_header=self.playback.command.parse_sap_header,
            parse_sid_header=self.playback.command.parse_sid_header,
            play_current_track=self.playback.command.play_current_track,
            prepare_playback_queue=self.playback.command.prepare_playback_queue,
            register_np_message=self.playback.command.register_np_message,
            save_queue=self.save_queue,
            search_tracks=self.playback.command.search_tracks,
            skip_to_next=self.playback.command.skip_to_next,
            has_snes_metadata=self.has_snes_metadata,
            iter_snes_metadata=self.iter_snes_metadata,
            start_targeted_playback_session=self.start_targeted_playback_session,
            stop_all_players=self.collection.stop_all_players,
            stop_state_streams=self.collection.stop_state_streams,
            switch_collection=self.collection.switch_collection,
        )

    def build_library_command_deps(self) -> LibraryCommandDependencies:
        return LibraryCommandDependencies(
            PLAYLIST_DIR=self.config.PLAYLIST_DIR,
            audacious_song=self.playback.command.audacious_song,
            clear_predownload_state=self.playback.command.clear_predownload_state,
            ensure_playlist_dir=self.library.ensure_playlist_dir,
            ensure_tracks=self.playback.command.ensure_tracks,
            filter_blacklisted_track_entries=self.library.filter_blacklisted_track_entries,
            get_state=self.get_state,
            list_playlists=self.library.list_playlists,
            load_blacklist=self.library.load_blacklist,
            load_favorites=self.library.load_favorites,
            load_playlist=self.library.load_playlist,
            load_user_tracks=self.library.load_user_tracks,
            log=self.bootstrap.logger,
            get_message_track=self.state.app_services.get_message_track,
            monitor_playback=self.playback.command.monitor_playback,
            play_current_track=self.playback.command.play_current_track,
            remove_user_track=self.library.remove_user_track,
            save_blacklist=self.library.save_blacklist,
            save_favorites=self.library.save_favorites,
            save_playlist=self.library.save_playlist,
            save_queue=self.save_queue,
            skip_to_next=self.playback.command.skip_to_next,
            toggle_user_track_entry=self.library.toggle_user_track_entry,
        )

    def build_playback_handler_deps(self) -> PlaybackHandlerDependencies:
        return PlaybackHandlerDependencies(
            ASMA_DIR=self.config.ASMA_DIR,
            AY_DIR=self.config.AY_DIR,
            HVSC_DIR=self.config.HVSC_DIR,
            TINY_DIR=self.config.TINY_DIR,
            YM_DIR=self.config.YM_DIR,
            audacious_play=self.playback.handler.audacious_play,
            audacious_song=self.playback.handler.audacious_song,
            audacious_stop=self.playback.handler.audacious_stop,
            build_temp_path=self.playback.handler.build_temp_path,
            cleanup_subsong_temp_wavs=self.playback.handler.cleanup_subsong_temp_wavs,
            clear_predownload_state=self.playback.handler.clear_predownload_state,
            download_modarchive_module=self.playback.handler.download_modarchive_module,
            download_sap=self.playback.handler.download_sap,
            download_spc_rsn=self.playback.handler.download_spc_rsn,
            get_shared_session=self.playback.handler.get_shared_session,
            get_subsongs=self.playback.handler.get_subsongs,
            log=self.bootstrap.logger,
            parse_sap_header=self.playback.handler.parse_sap_header,
            parse_sid_header=self.playback.handler.parse_sid_header,
            play_via_audacious=self.playback.handler.play_via_audacious,
            queue_position=self.playback.handler.queue_position,
            register_np_message=self.playback.handler.register_np_message,
            resolve_local_path=self.playback.handler.resolve_local_path,
            send_now_playing_embed=self.playback.handler.send_now_playing_embed,
            set_ym_last_wav_path=self.playback.handler.set_ym_last_wav_path,
            setup_monitor_source=self.playback.handler.setup_monitor_source,
            ym_cleanup=self.playback.handler.ym_cleanup,
            ym_to_wav=self.playback.handler.ym_to_wav,
        )

    async def start_targeted_playback_session(self, ctx: object, state: PlaylistState, url: str) -> bool:
        from session_runtime import start_targeted_playback_session

        return await start_targeted_playback_session(
            cast(PlaybackSessionContext, ctx),
            state,
            url,
            self.build_playback_session_deps(),
        )

    async def graceful_shutdown(self) -> None:
        self.state.shutdown_flag.set()
        self.bootstrap.logger.info("Shutting down gracefully...")
        self.bootstrap.release_process_lock(self.config.LOCK_FILE)
        for state in self.state.app_services.iter_guild_states():
            await self.collection.stop_state_streams(state)
        for _guild_id, source in list(self.state.active_streams.items()):
            source.cleanup()
        self.state.active_streams.clear()
        self.playback.command.audacious_stop()
        for vc in list(self.state.bot.voice_clients):
            await cast("discord.VoiceClient", vc).disconnect()
        await self.bootstrap.close_shared_session()
        self.bootstrap.cleanup_temp_dir(self.config.TEMP_DIR, logger=self.bootstrap.logger)

    def handle_signal(self, signum: int, _frame: object) -> None:
        self.bootstrap.logger.info("Received signal %d, shutting down...", signum)
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(self.graceful_shutdown(), loop)
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.state.bot.close()))
