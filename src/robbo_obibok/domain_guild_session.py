"""Discord guild session state — extracted from domain_state.

Keeps Discord-specific types (ctx, vc) weakly typed since they belong
to the Discord layer, not pure domain.  Task references are typed
properly as ``asyncio.Task | None``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class GuildSession:
    """Discord guild session state."""

    guild_id: int | None = None
    ctx: Any = None
    vc: Any = None
    current_track_path: str | None = None
    pre_downloaded: str | None = None
    pre_downloaded_url: str | None = None
    pre_download_task: asyncio.Task[object] | None = None
    monitor_task: asyncio.Task[object] | None = None

    def bind_voice_context(
        self, *, guild_id: int, ctx, vc
    ) -> None:
        self.guild_id = guild_id
        self.ctx = ctx
        self.vc = vc

    def set_guild_id(self, guild_id: int | None) -> None:
        self.guild_id = guild_id

    def set_context(self, ctx) -> None:
        self.ctx = ctx

    def set_current_path(self, path: str | None) -> None:
        self.current_track_path = path

    def set_monitor_task(self, task: asyncio.Task[object] | None) -> None:
        self.monitor_task = task

    def set_voice_client(self, vc) -> None:
        self.vc = vc

    def clear_voice_client(self) -> None:
        self.vc = None

    def set_predownload(self, filepath: str, url: str) -> None:
        self.pre_downloaded = filepath
        self.pre_downloaded_url = url

    def has_predownload_for(self, url: str) -> bool:
        return self.pre_downloaded is not None and self.pre_downloaded_url == url

    def set_predownload_task(self, task: asyncio.Task[object] | None) -> None:
        self.pre_download_task = task

    def clear_predownload(self) -> None:
        self.pre_downloaded = None
        self.pre_downloaded_url = None
        self.pre_download_task = None
