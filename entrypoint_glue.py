"""Glue helpers for entrypoint-local runtime callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app_state import PlaylistState
from entrypoint_bridge import EntrypointComponentAccess
from entrypoint_helpers import build_temp_path as build_entry_temp_path
from playback_helpers import play_via_audacious, queue_position, send_now_playing_embed

if TYPE_CHECKING:
    from discord import Colour
    from entrypoint_bridge import EntrypointGlueStateProtocol
    from entrypoint_resources import EntrypointResources


@dataclass(slots=True)
class EntrypointGlue:
    state: EntrypointGlueStateProtocol
    resources: EntrypointResources
    components: EntrypointComponentAccess

    def apply_queue_state(self, state: PlaylistState, queue_state: dict[str, object]) -> bool:
        state.set_queue_state(
            list(queue_state["queue"]),
            int(queue_state["index"]),
            loop=bool(queue_state["loop"]),
        )
        return bool(queue_state.get("restored"))

    def place_track_in_queue(self, queue: list[str], url: str) -> tuple[list[str], int]:
        from entrypoint_helpers import place_track_in_queue

        return place_track_in_queue(queue, url)

    def queue_position(self, state: PlaylistState) -> tuple[int, int]:
        return queue_position(state)

    def build_temp_path(self, url: str) -> str:
        return build_entry_temp_path(self.resources.app_cfg().temp_dir, url)

    def after_stream_end(self, guild_id: int | None, error: Exception | None, source_id: int = 0) -> None:
        self.components.require().stream_runtime.after_stream_end(guild_id, error, source_id)

    async def cancel_monitor(self, state: PlaylistState) -> None:
        await self.components.require().stream_runtime.cancel_monitor(state)

    async def pre_download_next(self, state: PlaylistState) -> None:
        playback_service = self.components.require().playback_service
        assert playback_service is not None
        await playback_service.pre_download_next(state)

    async def start_targeted_playback_session(
        self,
        ctx: object,
        state: PlaylistState,
        url: str,
    ) -> bool:
        playback_service = self.components.require().playback_service
        assert playback_service is not None
        return await playback_service.start_targeted_playback_session(ctx, state, url)

    async def play_via_audacious(
        self,
        state: PlaylistState,
        playback_path: str,
        *,
        current_path: str | None = None,
    ) -> None:
        now_playing_deps = self.components.require().now_playing_deps
        await play_via_audacious(
            state,
            playback_path,
            now_playing_deps,
            current_path=current_path,
        )

    async def send_now_playing_embed(
        self,
        ctx: object,
        state: PlaylistState,
        url: str,
        *,
        title: str,
        color: Colour,
        footer: str,
        author: str = "",
        extra_fields: list[tuple[str, str]] | None = None,
    ) -> None:
        now_playing_deps = self.components.require().now_playing_deps
        await send_now_playing_embed(
            ctx,
            state,
            url,
            now_playing_deps,
            title=title,
            color=color,
            footer=footer,
            author=author,
            extra_fields=extra_fields,
        )
