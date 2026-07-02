"""Voice stream source and active-stream registry helpers."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import discord


class MonitorAudioSource(discord.AudioSource):
    FRAME_SIZE = 3840
    MAX_RESTARTS = 5
    RESTART_COOLDOWN = 1.0

    def __init__(
        self,
        *,
        sink_name: str,
        audio_format: str,
        sample_rate: int,
        channels: int,
        logger: logging.Logger,
    ):
        self.buffer = b""
        self.sink_name = sink_name
        self.audio_format = audio_format
        self.sample_rate = sample_rate
        self.channels = channels
        self.logger = logger
        self.source_id = 0
        self.process = self._start_ffmpeg()
        self._restart_count = 0
        self._last_restart_ts = 0.0

    def _start_ffmpeg(self) -> subprocess.Popen:
        return subprocess.Popen(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "pulse",
                "-i",
                f"{self.sink_name}.monitor",
                "-f",
                self.audio_format,
                "-ar",
                str(self.sample_rate),
                "-ac",
                str(self.channels),
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def _restart_ffmpeg(self) -> None:
        self.cleanup()
        self.process = self._start_ffmpeg()

    def read(self) -> bytes:
        while len(self.buffer) < self.FRAME_SIZE:
            if self.process.poll() is not None:
                if self._restart_count >= self.MAX_RESTARTS:
                    self.logger.warning(
                        "MonitorAudioSource: max restarts (%d) reached, ending stream",
                        self.MAX_RESTARTS,
                    )
                    return b""
                if time.time() - self._last_restart_ts < self.RESTART_COOLDOWN:
                    time.sleep(0.05)
                    continue
                self._last_restart_ts = time.time()
                self._restart_count += 1
                time.sleep(0.1)
                self._restart_ffmpeg()
            assert self.process.stdout is not None
            chunk = self.process.stdout.read(4096)
            if not chunk:
                return b""
            self.buffer += chunk
            self._restart_count = 0
        frame = self.buffer[: self.FRAME_SIZE]
        self.buffer = self.buffer[self.FRAME_SIZE :]
        return frame

    def cleanup(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


@dataclass(slots=True)
class StreamRuntime:
    sink_name: str
    audio_format: str
    sample_rate: int
    channels: int
    logger: logging.Logger
    clear_predownload_state: Callable[[Any], None]
    active_streams: dict[int, MonitorAudioSource] = field(default_factory=dict)
    _source_counter: int = 0

    def next_source_id(self) -> int:
        self._source_counter += 1
        return self._source_counter

    def after_stream_end(self, guild_id: int | None, error: Exception | None, source_id: int = 0) -> None:
        self.logger.info("Stream ended for guild %s: %s", guild_id, error)
        if guild_id is None:
            return
        current = self.active_streams.get(guild_id)
        if current is not None and getattr(current, "source_id", None) == source_id:
            self.active_streams.pop(guild_id, None)
            current.cleanup()
        elif current is not None and source_id:
            self.logger.debug("Stale _after_stream_end for guild %s — current source differs, ignoring", guild_id)

    def setup_monitor_source(self, state: Any) -> None:
        if state.vc and state.vc.is_connected():
            state.vc.stop()
            old_source = self.active_streams.pop(state.guild_id, None)
            if old_source:
                self.logger.debug(
                    "setup_monitor_source: cleaning up old source %s for guild %s",
                    old_source.source_id,
                    state.guild_id,
                )
                old_source.cleanup()
            source = MonitorAudioSource(
                sink_name=self.sink_name,
                audio_format=self.audio_format,
                sample_rate=self.sample_rate,
                channels=self.channels,
                logger=self.logger,
            )
            source_id = self.next_source_id()
            source.source_id = source_id
            state.vc.play(
                source,
                after=lambda e, sid=source_id: self.after_stream_end(state.guild_id, e, sid),
            )
            self.active_streams[state.guild_id] = source

    async def cancel_monitor(self, state: Any) -> None:
        if state.monitor_task and not state.monitor_task.done():
            state.monitor_task.cancel()
            try:
                await state.monitor_task
            except (asyncio.CancelledError, Exception):
                pass
            finally:
                state.set_monitor_task(None)

    async def stop_state_streams(self, state: Any) -> None:
        await self.cancel_monitor(state)
        if state.guild_id is not None:
            stream = self.active_streams.pop(state.guild_id, None)
            if stream:
                stream.cleanup()
        self.clear_predownload_state(state)
