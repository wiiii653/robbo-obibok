"""Runtime IO helpers for shared HTTP sessions and audio-process adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import aiohttp

from playback_process import (
    audacious_play as runtime_audacious_play,
    audacious_song as runtime_audacious_song,
    audacious_stop as runtime_audacious_stop,
    ensure_audacious as runtime_ensure_audacious,
    is_playing as runtime_is_playing,
    move_playback_to_sink as runtime_move_playback_to_sink,
    set_volume_for_collection as runtime_set_volume_for_collection,
    setup_audacious_sid_config as runtime_setup_audacious_sid_config,
    setup_virtual_sink as runtime_setup_virtual_sink,
)


@dataclass(slots=True)
class SharedSessionRuntime:
    timeout_total: int = 60
    connector_limit: int = 10
    connector_limit_per_host: int = 5
    _session: aiohttp.ClientSession | None = field(default=None, init=False)

    async def get_shared_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_total),
                connector=aiohttp.TCPConnector(
                    limit=self.connector_limit,
                    limit_per_host=self.connector_limit_per_host,
                    enable_cleanup_closed=True,
                ),
            )
        return self._session

    async def close_shared_session(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None


@dataclass(slots=True)
class AudioProcessRuntime:
    sink_name: str
    logger: Any

    def setup_virtual_sink(self) -> None:
        runtime_setup_virtual_sink(self.sink_name)

    def ensure_audacious(self) -> None:
        runtime_ensure_audacious(self.logger)

    def setup_audacious_sid_config(self) -> None:
        runtime_setup_audacious_sid_config(self.logger)

    def set_volume_for_collection(self, mode: str) -> None:
        runtime_set_volume_for_collection(mode, self.sink_name, self.logger)

    def move_playback_to_sink(self) -> None:
        runtime_move_playback_to_sink(self.sink_name)

    def audacious_play(self, filepath: str) -> None:
        runtime_audacious_play(filepath, self.sink_name, self.logger)

    def audacious_stop(self) -> None:
        runtime_audacious_stop()

    def audacious_song(self) -> str:
        return runtime_audacious_song()

    def is_playing(self) -> bool:
        return runtime_is_playing()
