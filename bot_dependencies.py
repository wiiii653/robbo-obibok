"""Typed dependency bundles shared by command and playback modules."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Iterable, Protocol

from archive_catalog import CollectionInfo
from app_state import PlaylistState

if TYPE_CHECKING:
    from aiohttp import ClientSession


CommandDecoratorFactory = Callable[[], Callable[[Any], Any]]
PlaybackHandlerMap = dict[str, Callable[..., Awaitable[bool]]]


class SearchTracksProtocol(Protocol):
    def __call__(
        self,
        query: str,
        tracks: list[str],
        *,
        limit: int = 10,
    ) -> list[str]: ...


@dataclass(slots=True)
class PlaybackCommandDependencies:
    ASMA_BASE: str
    FLIP_ORDER: list[str]
    FLIP_SEQ: list[str]
    PLAYBACK_LOOP: bool
    PLAYBACK_SHUFFLE: bool
    PLAYLIST_DIR: str
    SINK_NAME: str
    apply_queue_state: Callable[[PlaylistState, dict[str, object]], bool]
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    clear_predownload_state: Callable[..., None]
    ensure_tracks: Callable[[PlaylistState], Awaitable[bool]]
    fetch_metadata_batch: Callable[..., Awaitable[dict[str, dict[str, str]]]]
    filter_blacklisted: Callable[[list[str], int], list[str]]
    get_all_cache_counts: Callable[[dict[str, tuple[str, str]]], dict[str, tuple[str, int | str]]]
    get_collection_info: Callable[[str], CollectionInfo]
    get_state: Callable[[int], PlaylistState]
    is_playing: Callable[[], bool]
    load_queue: Callable[[int], dict | None]
    load_snes_cache: Callable[[], list[str] | None]
    load_tracks_for_mode: Callable[[str], Awaitable[list[str] | None]]
    log: logging.Logger
    get_metadata_entry: Callable[[str], dict[str, str] | None]
    metadata_index_size: Callable[[], int]
    mod_only: CommandDecoratorFactory
    get_modarchive_track_name: Callable[[str], str | None]
    monitor_playback: Callable[..., Coroutine[Any, Any, None]]
    parse_sap_header: Callable[[str], dict[str, str]]
    parse_sid_header: Callable[[bytes], dict[str, str]]
    play_current_track: Callable[[object], Awaitable[bool]]
    prepare_playback_queue: Callable[..., dict[str, object]]
    register_np_message: Callable[[int, str, str, str], None]
    save_queue: Callable[[PlaylistState], None]
    search_tracks: SearchTracksProtocol
    skip_to_next: Callable[[object], Awaitable[None]]
    has_snes_metadata: Callable[[], bool]
    iter_snes_metadata: Callable[[], Iterable[tuple[str, dict[str, object]]]]
    start_targeted_playback_session: Callable[[object, PlaylistState, str], Awaitable[bool]]
    stop_all_players: Callable[[], None]
    stop_state_streams: Callable[[PlaylistState], Awaitable[None]]
    switch_collection: Callable[..., Awaitable[bool]]


@dataclass(slots=True)
class LibraryCommandDependencies:
    PLAYLIST_DIR: str
    audacious_song: Callable[[], str]
    clear_predownload_state: Callable[..., None]
    ensure_playlist_dir: Callable[[], None]
    ensure_tracks: Callable[[PlaylistState], Awaitable[bool]]
    filter_blacklisted_track_entries: Callable[[list[dict], dict, int], list[dict]]
    get_state: Callable[[int], PlaylistState]
    list_playlists: Callable[[], list[dict]]
    load_blacklist: Callable[[], dict]
    load_favorites: Callable[[], dict]
    load_playlist: Callable[[str], dict | None]
    load_user_tracks: Callable[[dict, int | str], list[dict]]
    log: logging.Logger
    get_message_track: Callable[[int], dict[str, object] | None]
    monitor_playback: Callable[..., Awaitable[None]]
    play_current_track: Callable[[object], Awaitable[bool]]
    remove_user_track: Callable[[dict, int | str, str], tuple[dict, bool]]
    save_blacklist: Callable[[dict], None]
    save_favorites: Callable[[dict], None]
    save_playlist: Callable[[str, list[dict], int, str], str]
    save_queue: Callable[[PlaylistState], None]
    skip_to_next: Callable[[object], Awaitable[None]]
    toggle_user_track_entry: Callable[[dict, int | str, dict], tuple[dict, bool]]


@dataclass(slots=True)
class PlaybackHandlerDependencies:
    ASMA_DIR: str
    AY_DIR: str
    HVSC_DIR: str
    TINY_DIR: str
    YM_DIR: str
    audacious_play: Callable[[str], None]
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    build_temp_path: Callable[[str], str]
    cleanup_subsong_temp_wavs: Callable[[PlaylistState], None]
    clear_predownload_state: Callable[..., None]
    download_modarchive_module: Callable[[str], Awaitable[str]]
    download_sap: Callable[[str], Awaitable[str]]
    download_spc_rsn: Callable[[str, str, str], Awaitable[str | None]]
    get_shared_session: Callable[[], Awaitable[ClientSession]]
    get_subsongs: Callable[[str], list[float]]
    log: logging.Logger
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
