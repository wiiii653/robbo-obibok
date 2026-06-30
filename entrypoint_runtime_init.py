"""Entrypoint runtime assembly and initialization."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from runtime_bootstrap import StartupEnvironment
from bot_dependencies import PlaybackHandlerDependencies, PlaybackHandlerMap
from bot_runtime import BotRuntime, RuntimeConfig, RuntimeState
from entrypoint_bridge import EntrypointComponentAccess
from entrypoint_callback_groups import AppEntrypointCallbacks
from entrypoint_resources import EntrypointResources
from entrypoint_state_protocols import EntrypointRuntimeInitializerStateProtocol

if TYPE_CHECKING:
    from discord.ext import commands
    from entrypoint_runtime import AppAssembly


@dataclass(slots=True)
class RuntimeRegistrationHooks:
    build_playback_handlers: Callable[[PlaybackHandlerDependencies], PlaybackHandlerMap]
    register_core_events: Callable[..., None]
    register_playback_commands: Callable[..., None]
    register_library_commands: Callable[..., None]
    health_watchdog: Callable[[], Awaitable[None]]
    fetch_metadata_background: Callable[[], Awaitable[None]]

@dataclass(slots=True)
class EntrypointRuntimeInitializer:
    root_dir: str
    logger: logging.Logger
    bot: "commands.Bot"
    state: EntrypointRuntimeInitializerStateProtocol
    resources: EntrypointResources
    status_count_cache: dict[str, tuple[float, int | str]]
    flip_order: list[str]
    flip_seq: list[str]
    validate_runtime_dependencies: Callable[[], None]
    components: EntrypointComponentAccess
    registration_hooks: RuntimeRegistrationHooks
    callbacks: AppEntrypointCallbacks

    def build_startup_environment(self) -> StartupEnvironment:
        from entrypoint_runtime import build_startup_env

        return build_startup_env(
            bot_token=self.resources.app_cfg().bot_token,
            root_dir=self.root_dir,
            validate_runtime_dependencies=self.validate_runtime_dependencies,
        )

    def build_runtime_configuration(self, lock_file: str) -> RuntimeConfig:
        from entrypoint_runtime import build_runtime_config

        app_cfg = self.resources.app_cfg()
        return build_runtime_config(
            asma_base=app_cfg.asma_base,
            asma_dir=app_cfg.asma_dir,
            auto_start_channel=app_cfg.auto_start_channel,
            ay_dir=app_cfg.ay_dir,
            flip_order=self.flip_order,
            flip_seq=self.flip_seq,
            hvsc_dir=app_cfg.hvsc_dir,
            lock_file=lock_file,
            playback_loop=app_cfg.playback_loop,
            playback_shuffle=app_cfg.playback_shuffle,
            playlist_dir=app_cfg.playlist_dir,
            root_dir=self.root_dir,
            sink_name=app_cfg.sink_name,
            temp_dir=app_cfg.temp_dir,
            tiny_dir=app_cfg.tiny_dir,
            ym_dir=app_cfg.ym_dir,
        )

    def build_runtime_state_bundle(self, shutdown_flag) -> RuntimeState:
        from entrypoint_runtime import build_runtime_state

        component_bundle = self.components.require()
        return build_runtime_state(
            active_streams=component_bundle.active_streams,
            app_services=component_bundle.app_services,
            bot=self.bot,
            collections=component_bundle.collections,
            metadata_index=self.state.runtime_metadata_index(),
            modarchive_name_map=self.state.runtime_modarchive_name_map(),
            shutdown_flag=shutdown_flag,
            snes_metadata=self.state.runtime_snes_metadata(),
            status_count_cache=self.status_count_cache,
        )

    def build_app_callback_bundle(self):
        from entrypoint_runtime import build_app_callbacks

        component_bundle = self.components.require()
        app_cfg = self.resources.app_cfg()
        assert self.state.archives is not None
        return build_app_callbacks(
            app_services=component_bundle.app_services,
            archive_runtime=component_bundle.archive_runtime,
            playback_assets=component_bundle.playback_assets,
            service_facade=component_bundle.service_facade,
            stream_runtime=component_bundle.stream_runtime,
            callbacks=self.callbacks,
            set_ym_last_wav_path=component_bundle.playback_assets.set_ym_last_wav_path,
            archives=self.state.archives,
            last_collection_file=app_cfg.last_collection_file,
            logger=self.logger,
        )

    def create_app(self) -> AppAssembly:
        from entrypoint_runtime import create_app as create_entry_app

        self.components.require()
        assert self.state.service_facade is not None
        startup_env = self.build_startup_environment()
        return create_entry_app(
            startup_env=startup_env,
            config=self.build_runtime_configuration(startup_env.lock_file),
            state=self.build_runtime_state_bundle(startup_env.shutdown_flag),
            app_callbacks=self.build_app_callback_bundle(),
            bot=self.bot,
            build_playback_handlers=self.registration_hooks.build_playback_handlers,
            register_core_events=self.registration_hooks.register_core_events,
            register_playback_commands=self.registration_hooks.register_playback_commands,
            register_library_commands=self.registration_hooks.register_library_commands,
            health_watchdog=self.registration_hooks.health_watchdog,
            fetch_metadata_background=self.registration_hooks.fetch_metadata_background,
            service_facade=self.state.service_facade,
        )

    def initialize_runtime(self) -> AppAssembly:
        if self.state.app is not None:
            return self.state.app
        return self.state.cache_initialized_app(self.create_app())
