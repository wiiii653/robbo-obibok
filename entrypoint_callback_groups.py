"""Grouped callback bundles for entrypoint runtime assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine

from domain_state import PlaylistState
from bot_dependencies import CommandDecoratorFactory
from collection_specs import CollectionSpec

if TYPE_CHECKING:
    from aiohttp import ClientSession

@dataclass(slots=True)
class PlaybackEntrypointCallbacks:
    apply_queue_state: Callable[[PlaylistState, dict[str, object]], bool]
    audacious_play: Callable[[str], None]
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    build_temp_path: Callable[[str], str]
    classify_track_route: Callable[..., dict[str, str]]
    clear_predownload_state: Callable[..., None]
    cleanup_subsong_temp_wavs: Callable[[PlaylistState], None]
    get_shared_session: Callable[[], Awaitable[ClientSession]]
    is_playing: Callable[[], bool]
    monitor_playback: Callable[..., Coroutine[Any, Any, None]]
    play_subsong: Callable[..., Awaitable[bool]]
    play_via_audacious: Callable[..., Awaitable[None]]
    place_track_in_queue: Callable[[list[str], str], tuple[list[str], int]]
    prepare_playback_queue: Callable[..., dict[str, object]]
    queue_position: Callable[[PlaylistState], tuple[int, int]]
    send_now_playing_embed: Callable[..., Awaitable[None]]


@dataclass(slots=True)
class PlaybackStaticCallbacks:
    audacious_play: Callable[[str], None]
    audacious_song: Callable[[], str]
    audacious_stop: Callable[[], None]
    classify_track_route: Callable[..., dict[str, str]]
    clear_predownload_state: Callable[..., None]
    get_shared_session: Callable[[], Awaitable[ClientSession]]
    is_playing: Callable[[], bool]
    prepare_playback_queue: Callable[..., dict[str, object]]


@dataclass(slots=True)
class LibraryEntrypointCallbacks:
    filter_blacklisted_track_entries: Callable[[list[dict], dict, int], list[dict]]
    load_user_tracks: Callable[[dict, int | str], list[dict]]
    remove_user_track: Callable[[dict, int | str, str], tuple[dict, bool]]
    toggle_user_track_entry: Callable[[dict, int | str, dict], tuple[dict, bool]]


@dataclass(slots=True)
class LibraryStaticCallbacks:
    filter_blacklisted_track_entries: Callable[[list[dict], dict, int], list[dict]]
    load_user_tracks: Callable[[dict, int | str], list[dict]]
    remove_user_track: Callable[[dict, int | str, str], tuple[dict, bool]]
    toggle_user_track_entry: Callable[[dict, int | str, dict], tuple[dict, bool]]


@dataclass(slots=True)
class CollectionEntrypointCallbacks:
    auto_play_after_switch: Callable[[object, PlaylistState], Awaitable[None]]
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]]
    format_flip_sequence: Callable[[list[str], str], str]
    save_last_collection: Callable[[str, str], None]
    set_volume_for_collection: Callable[[str], None]
    stop_all_players: Callable[[], None]
    switch_collection: Callable[..., Awaitable[bool]]


@dataclass(slots=True)
class CollectionStaticCallbacks:
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]]
    format_flip_sequence: Callable[[list[str], str], str]
    save_last_collection: Callable[[str, str], None]
    set_volume_for_collection: Callable[[str], None]


@dataclass(slots=True)
class BootstrapEntrypointCallbacks:
    close_shared_session: Callable[[], Awaitable[None]]
    mod_only: CommandDecoratorFactory
    cleanup_orphan_players: Callable[[], None]
    setup_virtual_sink: Callable[[], None]
    ensure_audacious: Callable[[], None]
    setup_audacious_sid_config: Callable[[], None]


@dataclass(slots=True)
class BootstrapStaticCallbacks:
    close_shared_session: Callable[[], Awaitable[None]]
    mod_only: CommandDecoratorFactory
    setup_virtual_sink: Callable[[], None]
    ensure_audacious: Callable[[], None]
    setup_audacious_sid_config: Callable[[], None]


@dataclass(slots=True)
class AppEntrypointCallbacks:
    playback: PlaybackEntrypointCallbacks
    library: LibraryEntrypointCallbacks
    collection: CollectionEntrypointCallbacks
    bootstrap: BootstrapEntrypointCallbacks


@dataclass(slots=True)
class EntrypointRawCallbacks:
    playback: PlaybackStaticCallbacks
    library: LibraryStaticCallbacks
    collection: CollectionStaticCallbacks
    bootstrap: BootstrapStaticCallbacks
