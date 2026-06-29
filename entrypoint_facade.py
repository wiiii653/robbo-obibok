"""Facade for stateful entrypoint operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app_state import PlaylistState
from entrypoint_bridge import EntrypointComponentAccess


@dataclass(slots=True)
class EntrypointFacade:
    components: EntrypointComponentAccess

    async def switch_collection(self, ctx: object, mode: str, *, flip_seq=None):
        return await self.components.require().service_facade.switch_collection(ctx, mode, flip_seq=flip_seq)

    async def skip_to_next(self, ctx: object) -> None:
        await self.components.require().service_facade.skip_to_next(ctx)

    def cleanup_subsong_temp_wavs(self, state: PlaylistState) -> None:
        self.components.require().service_facade.cleanup_subsong_temp_wavs(state)

    def cleanup_orphan_players(self) -> None:
        self.components.require().legacy.cleanup_orphan_players()

    def stop_all_players(self) -> None:
        self.components.require().legacy.stop_all_players()

    async def auto_play_after_switch(self, ctx: object, state: PlaylistState) -> None:
        await self.components.require().legacy.auto_play_after_switch(ctx, state)

    async def play_subsong(
        self,
        ctx: object,
        state: PlaylistState,
        subsong: int,
        *,
        audacious_stop: Callable[[], None],
        audacious_play: Callable[[str], None],
        setup_monitor_source: Callable[[object], None],
    ) -> bool:
        return await self.components.require().legacy.play_subsong(
            ctx,
            state,
            subsong,
            audacious_stop=audacious_stop,
            audacious_play=audacious_play,
            setup_monitor_source=setup_monitor_source,
        )
