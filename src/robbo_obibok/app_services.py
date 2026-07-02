"""Application service facade over state and persistent stores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .bot_persistence import CachedJsonStore, PlaylistLibraryStore
from .domain_state import AppRuntimeState, PlaylistState


class AppServicesProtocol(Protocol):
    def iter_guild_states(self) -> Iterable[PlaylistState]: ...

    def get_message_track(self, msg_id: int) -> dict[str, object] | None: ...

    def register_now_playing_message(self, msg_id: int, url: str, name: str, author: str) -> None: ...

    def get_state(self, guild_id: int) -> PlaylistState: ...

    def save_queue(self, state: PlaylistState) -> None: ...

    def load_queue(self, guild_id: int) -> dict | None: ...

    def load_favorites(self) -> dict: ...

    def save_favorites(self, data: dict) -> None: ...

    def ensure_playlist_dir(self) -> None: ...

    def save_playlist(self, name: str, tracks: list[dict], author_id: int, author_name: str) -> str: ...

    def load_playlist(self, name: str) -> dict | None: ...

    def list_playlists(self) -> list[dict]: ...

    def load_blacklist(self) -> dict: ...

    def save_blacklist(self, data: dict) -> None: ...


@dataclass(slots=True)
class AppServices:
    app_state: AppRuntimeState
    favorites_store: CachedJsonStore
    blacklist_store: CachedJsonStore
    playlist_store: PlaylistLibraryStore

    def register_now_playing_message(self, msg_id: int, url: str, name: str, author: str) -> None:
        self.app_state.register_now_playing_message(msg_id, url, name, author)

    def get_state(self, guild_id: int) -> PlaylistState:
        return self.app_state.get_state(guild_id)

    def save_queue(self, state: PlaylistState) -> None:
        self.app_state.save_queue(state)

    def load_queue(self, guild_id: int) -> dict | None:
        return self.app_state.load_queue(guild_id)

    def iter_guild_states(self) -> Iterable[PlaylistState]:
        return self.app_state.iter_guild_states()

    def get_message_track(self, msg_id: int) -> dict[str, object] | None:
        return self.app_state.get_message_track(msg_id)

    def load_favorites(self) -> dict:
        return self.favorites_store.load()

    def save_favorites(self, data: dict) -> None:
        self.favorites_store.save(data)

    def ensure_playlist_dir(self) -> None:
        self.playlist_store.ensure_playlist_dir()

    def save_playlist(self, name: str, tracks: list[dict], author_id: int, author_name: str) -> str:
        return self.playlist_store.save_playlist(name, tracks, author_id, author_name)

    def load_playlist(self, name: str) -> dict | None:
        return self.playlist_store.load_playlist(name)

    def list_playlists(self) -> list[dict]:
        return self.playlist_store.list_playlists()

    def load_blacklist(self) -> dict:
        return self.blacklist_store.load()

    def save_blacklist(self, data: dict) -> None:
        self.blacklist_store.save(data)
