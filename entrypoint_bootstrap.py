"""Bootstrap configuration and lazy app state for the entrypoint."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from app_bootstrap import ArchiveRegistryViews, BootstrappedApp, bootstrap_app
from app_config import AppConfig
from app_config import build_app_config
from app_context import AppContext
from app_services import AppServicesProtocol
from app_state import AppRuntimeState
from archive_catalog import ArchiveCatalog
from archive_runtime import ArchiveRuntimeConfig
from entrypoint_glue import build_temp_path as build_entry_temp_path
import entrypoint_state as state_protocols
from runtime_io import AudioProcessRuntime
from runtime_support import load_dotenv_file
from subsong_runtime import SubsongRuntime


@dataclass(slots=True)
class EntrypointBootstrap:
    app_cfg: AppConfig
    config: dict[str, Any]
    archive_runtime_config: ArchiveRuntimeConfig
    bootstrapped_app: BootstrappedApp
    app_context: AppContext
    app_state: AppRuntimeState
    archives: ArchiveCatalog
    app_services: AppServicesProtocol
    archive_views: ArchiveRegistryViews


@dataclass(slots=True)
class EntrypointBootstrapBuilder:
    root_dir: str
    logger: logging.Logger
    load_last_collection: Callable[[str], str | None]
    atomic_json_write: Callable[[str, object, object], None]
    _app_cfg: AppConfig | None = None
    _config: dict[str, Any] | None = None
    _archive_runtime_config: ArchiveRuntimeConfig | None = None
    _bootstrap: EntrypointBootstrap | None = None

    @property
    def app_cfg(self) -> AppConfig:
        if self._app_cfg is None:
            load_dotenv_file(f"{self.root_dir}/.env")
            self._app_cfg = build_app_config(self.root_dir, self.logger)
            self._config = self._app_cfg.config
            self._archive_runtime_config = self._app_cfg.archive_runtime_config
        return self._app_cfg

    @property
    def config(self) -> dict[str, Any]:
        return self.app_cfg.config if self._config is None else self._config

    @property
    def archive_runtime_config(self) -> ArchiveRuntimeConfig:
        return self.app_cfg.archive_runtime_config if self._archive_runtime_config is None else self._archive_runtime_config

    def materialize(self) -> EntrypointBootstrap:
        if self._bootstrap is not None:
            return self._bootstrap
        bootstrapped_app = bootstrap_app(
            queue_dir=self.app_cfg.queue_dir,
            default_collection_mode=self.load_last_collection(self.app_cfg.last_collection_file)
            or self.app_cfg.default_collection_mode,
            favorites_file=self.app_cfg.favorites_file,
            blacklist_file=self.app_cfg.blacklist_file,
            playlist_dir=self.app_cfg.playlist_dir,
            archive_paths=self.archive_runtime_config,
            json_writer=lambda path, data: self.atomic_json_write(path, data, self.logger),
            logger=self.logger,
        )
        self._bootstrap = EntrypointBootstrap(
            app_cfg=self.app_cfg,
            config=self.config,
            archive_runtime_config=self.archive_runtime_config,
            bootstrapped_app=bootstrapped_app,
            app_context=bootstrapped_app.context,
            app_state=bootstrapped_app.context.app_state,
            archives=bootstrapped_app.context.archives,
            app_services=bootstrapped_app.services,
            archive_views=bootstrapped_app.archive_views,
        )
        return self._bootstrap


def build_entrypoint_bootstrap(
    root_dir: str,
    logger: logging.Logger,
    *,
    load_last_collection: Callable[[str], str | None],
    atomic_json_write: Callable[[str, object, object], None],
) -> EntrypointBootstrapBuilder:
    return EntrypointBootstrapBuilder(
        root_dir=root_dir,
        logger=logger,
        load_last_collection=load_last_collection,
        atomic_json_write=atomic_json_write,
    )


@dataclass(slots=True)
class EntrypointResources:
    boot: EntrypointBootstrapBuilder
    state: state_protocols.EntrypointResourceStateProtocol
    logger: logging.Logger

    def app_cfg(self) -> AppConfig:
        return self.boot.app_cfg

    def config(self) -> dict[str, Any]:
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

    def audacious_play(self, filepath: str) -> bool:
        return self.get_audio_runtime().audacious_play(filepath)

    def audacious_stop(self) -> None:
        self.get_audio_runtime().audacious_stop()

    def audacious_song(self) -> str:
        return self.get_audio_runtime().audacious_song()

    def is_playing(self) -> bool:
        return self.get_audio_runtime().is_playing()
