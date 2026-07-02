"""Collection browsing state — extracted from domain_state."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CollectionState:
    """Collection browsing state."""

    tracks: list[str] = field(default_factory=list)
    collection_mode: str = "asma"
    loaded_collection: str = ""
    search_results: list[str] = field(default_factory=list)
    crawling: bool = False

    def set_collection_mode(self, mode: str) -> None:
        self.collection_mode = mode

    def set_tracks(self, tracks: list[str] | None) -> None:
        self.tracks = list(tracks or [])

    def set_loaded_collection(self, mode: str, tracks: list[str]) -> None:
        self.collection_mode = mode
        self.loaded_collection = mode
        self.set_tracks(tracks)

    def set_loaded_collection_name(self, mode: str) -> None:
        self.loaded_collection = mode

    def clear_loaded_collection(self) -> None:
        self.loaded_collection = ""

    def set_search_results(self, results: list[str]) -> None:
        self.search_results = list(results)
