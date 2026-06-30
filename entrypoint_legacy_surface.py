"""Legacy module surface for the entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from entrypoint_registry import EntrypointExportRegistry
from entrypoint_surface_assembly import build_entrypoint_compat_registry_attrs

if TYPE_CHECKING:
    from discord import Colour
    from app_state import PlaylistState
    from entrypoint_app import EntrypointApp
    from entrypoint_state_protocols import EntrypointCompatStateProtocol


@dataclass(slots=True)
class EntrypointExportBindings:
    app: EntrypointApp

    def ensure_entrypoint_components(self) -> None:
        self.app.ensure_components()

    def after_stream_end(
        self,
        guild_id: int | None,
        error: Exception | None,
        source_id: int = 0,
    ) -> None:
        self.app.glue.after_stream_end(guild_id, error, source_id)

    def apply_queue_state(self, state: PlaylistState, queue_state: dict[str, object]) -> bool:
        return self.app.glue.apply_queue_state(state, queue_state)

    def place_track_in_queue(self, queue: list[str], url: str) -> tuple[list[str], int]:
        return self.app.glue.place_track_in_queue(queue, url)

    def queue_position(self, state: PlaylistState) -> tuple[int, int]:
        return self.app.glue.queue_position(state)

    async def cancel_monitor(self, state: PlaylistState) -> None:
        await self.app.glue.cancel_monitor(state)

    async def pre_download_next(self, state: PlaylistState) -> None:
        await self.app.glue.pre_download_next(state)

    async def start_targeted_playback_session(self, ctx: object, state: PlaylistState, url: str) -> bool:
        return await self.app.glue.start_targeted_playback_session(ctx, state, url)

    async def play_via_audacious(
        self,
        state: PlaylistState,
        playback_path: str,
        *,
        current_path: str | None = None,
    ) -> None:
        await self.app.glue.play_via_audacious(state, playback_path, current_path=current_path)

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
        await self.app.glue.send_now_playing_embed(
            ctx,
            state,
            url,
            title=title,
            color=color,
            footer=footer,
            author=author,
            extra_fields=extra_fields,
        )

    async def monitor_playback(self, ctx: object, vc: object, guild_id: int) -> None:
        self.app.ensure_components()
        await self.app.runtime_tasks.monitor_playback(ctx, vc, guild_id)

    async def fetch_metadata_background(self) -> None:
        await self.app.runtime_tasks.fetch_metadata_background()

    async def health_watchdog(self) -> None:
        self.app.ensure_components()
        await self.app.runtime_tasks.health_watchdog()


@dataclass(slots=True)
class EntrypointCompatEagerBindings:
    state: EntrypointCompatStateProtocol
    guild_id_getter: Callable[[], int | None]

    def as_registry_attrs(self) -> dict[str, Callable[[], object]]:
        return build_entrypoint_compat_registry_attrs(
            state=self.state,
            guild_id_getter=self.guild_id_getter,
        )


def build_entrypoint_exports(app: EntrypointApp) -> EntrypointExportRegistry:
    bindings = EntrypointExportBindings(app=app)
    return EntrypointExportRegistry().register_eager(
        _ensure_entrypoint_components=lambda: bindings.ensure_entrypoint_components,
        _after_stream_end=lambda: bindings.after_stream_end,
        _apply_queue_state=lambda: bindings.apply_queue_state,
        _place_track_in_queue=lambda: bindings.place_track_in_queue,
        _queue_position=lambda: bindings.queue_position,
        _cancel_monitor=lambda: bindings.cancel_monitor,
        pre_download_next=lambda: bindings.pre_download_next,
        _start_targeted_playback_session=lambda: bindings.start_targeted_playback_session,
        _play_via_audacious=lambda: bindings.play_via_audacious,
        _send_now_playing_embed=lambda: bindings.send_now_playing_embed,
        monitor_playback=lambda: bindings.monitor_playback,
        fetch_metadata_background=lambda: bindings.fetch_metadata_background,
        health_watchdog=lambda: bindings.health_watchdog,
    )


@dataclass(slots=True)
class EntrypointCompat:
    state: EntrypointCompatStateProtocol
    ensure_components: Callable[[], None]
    guild_id_getter: Callable[[], int | None]

    def _registry(self) -> EntrypointExportRegistry:
        eager = EntrypointCompatEagerBindings(
            state=self.state,
            guild_id_getter=self.guild_id_getter,
        )
        return EntrypointExportRegistry().register_eager(**eager.as_registry_attrs())

    def resolve(self, name: str) -> object:
        return self._registry().resolve(name, self.ensure_components)
