"""Runtime IO helpers for shared HTTP sessions and audio-process adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import aiohttp

from domain_state import PlaylistState
from playback_process import (
    audacious_play as runtime_audacious_play,
)
from playback_process import (
    audacious_song as runtime_audacious_song,
)
from playback_process import (
    audacious_stop as runtime_audacious_stop,
)
from playback_process import (
    audtool_output_length as runtime_audtool_output_length,
)
from playback_process import (
    audtool_song_length as runtime_audtool_song_length,
)
from playback_process import (
    ensure_audacious as runtime_ensure_audacious,
)
from playback_process import (
    is_playing as runtime_is_playing,
)
from playback_process import (
    move_playback_to_sink as runtime_move_playback_to_sink,
)
from playback_process import (
    set_volume_for_collection as runtime_set_volume_for_collection,
)
from playback_process import (
    setup_audacious_sid_config as runtime_setup_audacious_sid_config,
)
from playback_process import (
    setup_virtual_sink as runtime_setup_virtual_sink,
)
from playback_process import (
    stop_all_players as runtime_stop_all_players,
)
from runtime_protocols import PlaybackProcessProtocol  # noqa: F401 — structural protocol impl

# Re-export standalone functions for callers not using AudioProcessRuntime
audtool_output_length: Callable[[], int] = runtime_audtool_output_length
audtool_song_length: Callable[[], int] = runtime_audtool_song_length


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
    """Manages Audacious subprocess lifecycle.

    Implements :class:`runtime_protocols.PlaybackProcessProtocol`.
    Delegates to module-level helpers in :mod:`playback_process` for the
    actual subprocess calls.
    """

    sink_name: str
    logger: Any

    # ── PlaybackProcessProtocol implementation ──

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

    def audacious_play(self, filepath: str) -> bool:
        return runtime_audacious_play(filepath, self.sink_name, self.logger)

    def audacious_stop(self) -> None:
        runtime_audacious_stop()

    def audacious_song(self) -> str:
        return runtime_audacious_song()

    def is_playing(self) -> bool:
        return runtime_is_playing()

    def audtool_output_length(self) -> int:
        return runtime_audtool_output_length()

    def audtool_song_length(self) -> int:
        return runtime_audtool_song_length()

    def stop_all_players(
        self,
        guild_states: Iterable[PlaylistState],
        cleanup_subsong_temp_wavs: Callable[[PlaylistState], None],
    ) -> None:
        runtime_stop_all_players(guild_states, cleanup_subsong_temp_wavs)
