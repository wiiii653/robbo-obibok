"""Lazy accessors for entrypoint configuration and process runtimes."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol

from app_config import AppConfig
from archive_runtime import ArchiveRuntimeConfig
from entrypoint_bootstrap import EntrypointBootstrapBuilder
from entrypoint_helpers import build_temp_path as build_entry_temp_path
from runtime_io import AudioProcessRuntime
from subsong_runtime import SubsongRuntime

class EntrypointResourceStateProtocol(Protocol):
    audio_runtime: AudioProcessRuntime | None
    subsongs_runtime: SubsongRuntime | None


@dataclass(slots=True)
class EntrypointResources:
    boot: EntrypointBootstrapBuilder
    state: EntrypointResourceStateProtocol
    logger: logging.Logger

    def app_cfg(self) -> AppConfig:
        return self.boot.app_cfg

    def config(self) -> dict[str, object]:
        return self.boot.config

    def archive_runtime_config(self) -> ArchiveRuntimeConfig:
        return self.boot.archive_runtime_config

    def get_audio_runtime(self) -> AudioProcessRuntime:
        if self.state.audio_runtime is None:
            self.state.audio_runtime = AudioProcessRuntime(
                sink_name=self.app_cfg().sink_name,
                logger=self.logger,
            )
        return self.state.audio_runtime

    def get_subsongs_runtime(self) -> SubsongRuntime:
        if self.state.subsongs_runtime is None:
            self.state.subsongs_runtime = SubsongRuntime(self.app_cfg().temp_dir, self.logger)
        return self.state.subsongs_runtime

    async def command_prefix(self, _bot: object, _message: object) -> str:
        return self.app_cfg().command_prefix

    def build_temp_path(self, url: str) -> str:
        return build_entry_temp_path(self.app_cfg().temp_dir, url)

    def setup_virtual_sink(self) -> None:
        self.get_audio_runtime().setup_virtual_sink()

    def ensure_audacious(self) -> None:
        self.get_audio_runtime().ensure_audacious()

    def setup_audacious_sid_config(self) -> None:
        self.get_audio_runtime().setup_audacious_sid_config()

    def set_volume_for_collection(self, mode: str) -> None:
        self.get_audio_runtime().set_volume_for_collection(mode)

    def move_playback_to_sink(self) -> None:
        self.get_audio_runtime().move_playback_to_sink()

    def audacious_play(self, filepath: str) -> None:
        self.get_audio_runtime().audacious_play(filepath)

    def audacious_stop(self) -> None:
        self.get_audio_runtime().audacious_stop()

    def audacious_song(self) -> str:
        return self.get_audio_runtime().audacious_song()

    def is_playing(self) -> bool:
        return self.get_audio_runtime().is_playing()
