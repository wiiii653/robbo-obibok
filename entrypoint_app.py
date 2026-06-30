"""Assembled entrypoint application support."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Callable

from app_config import AppConfig
from app_services import AppServicesProtocol
from app_state import PlaylistState
from bot_dependencies import CommandDecoratorFactory, PlaybackHandlerDependencies, PlaybackHandlerMap
from collection_specs import CollectionSpec
import entrypoint_state_protocols as state_protocols

from entrypoint_callback_groups import EntrypointRawCallbacks
from entrypoint_components import EntrypointComponentDeps, apply_entrypoint_components, build_entrypoint_components
from entrypoint_glue import EntrypointGlue
from entrypoint_runtime_callback_builders import (
    build_entrypoint_runtime_callbacks,
    build_entrypoint_runtime_initializer,
)
from entrypoint_runtime_init import EntrypointRuntimeInitializer
from entrypoint_runtime_tasks import EntrypointRuntimeTasks, build_entrypoint_runtime_tasks
from entrypoint_surface_assembly import build_entrypoint_compat_registry_attrs

if TYPE_CHECKING:
    from discord.ext import commands
    from entrypoint_launcher_support import EntrypointSupport
    from entrypoint_state_protocols import EntrypointCompatStateProtocol
    from legacy_runtime_bindings import LegacyRuntimeBindings
    from playback_assets import PlaybackAssetRuntime
    from playback_helpers import NowPlayingDependencies
    from runtime_protocols import ArchiveRuntimeProtocol, PlaybackRuntimeProtocol
    from runtime_service_facade import RuntimeServiceFacade
    from stream_runtime import MonitorAudioSource, StreamRuntime


@dataclass(slots=True)
class EntrypointComponents:
    app_services: AppServicesProtocol
    service_facade: "RuntimeServiceFacade"
    stream_runtime: "StreamRuntime"
    archive_runtime: "ArchiveRuntimeProtocol"
    playback_assets: "PlaybackAssetRuntime"
    now_playing_deps: "NowPlayingDependencies"
    collections: dict[str, CollectionSpec]
    active_streams: dict[int, "MonitorAudioSource"]
    playback_service: "PlaybackRuntimeProtocol | None"
    legacy: "LegacyRuntimeBindings"


@dataclass(slots=True)
class EntrypointComponentAccess:
    state: state_protocols.EntrypointComponentAccessStateProtocol
    ensure_components: Callable[[], None]

    def require(self) -> EntrypointComponents:
        self.ensure_components()
        if hasattr(self.state, "component_bundle"):
            return self.state.component_bundle()
        assert self.state.app_services is not None
        assert self.state.service_facade is not None
        assert self.state.stream_runtime is not None
        assert self.state.archive_runtime is not None
        assert self.state.playback_assets is not None
        assert self.state.now_playing_deps is not None
        assert self.state.legacy is not None
        return EntrypointComponents(
            app_services=self.state.app_services,
            service_facade=self.state.service_facade,
            stream_runtime=self.state.stream_runtime,
            archive_runtime=self.state.archive_runtime,
            playback_assets=self.state.playback_assets,
            now_playing_deps=self.state.now_playing_deps,
            collections=self.state.collections,
            active_streams=self.state.active_streams,
            playback_service=self.state.playback_service,
            legacy=self.state.legacy,
        )


@dataclass(slots=True)
class EntrypointFacade:
    components: EntrypointComponentAccess

    async def switch_collection(
        self,
        ctx: object,
        mode: str,
        *,
        flip_seq: list[str] | None = None,
    ) -> bool:
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


@dataclass(slots=True)
class EntrypointCompat:
    state: EntrypointCompatStateProtocol
    ensure_components: Callable[[], None]
    guild_id_getter: Callable[[], int | None]

    def resolve(self, name: str) -> object:
        attrs = build_entrypoint_compat_registry_attrs(
            state=self.state,
            guild_id_getter=self.guild_id_getter,
        )
        if name in attrs:
            return attrs[name]()
        raise AttributeError(name)


@dataclass(slots=True)
class EntrypointApp:
    support: EntrypointSupport
    bot: commands.Bot
    logger: logging.Logger
    ensure_components: Callable[[], None]
    glue: EntrypointGlue
    facade: EntrypointFacade
    runtime_tasks: EntrypointRuntimeTasks
    runtime_initializer: EntrypointRuntimeInitializer
    compat: EntrypointCompat


@dataclass(slots=True)
class EntrypointRegistrationDeps:
    build_playback_handlers: Callable[[PlaybackHandlerDependencies], PlaybackHandlerMap]
    register_core_events: Callable[..., None]
    register_playback_commands: Callable[..., None]
    register_library_commands: Callable[..., None]
    validate_runtime_dependencies: Callable[[], None]


@dataclass(slots=True)
class EntrypointRuntimePolicyDeps:
    compute_timeout_seconds: Callable[..., int]
    is_gme_format_path: Callable[[str | None], bool]
    should_advance_after_stop: Callable[..., tuple[bool, float | None]]
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]]
    should_disconnect_for_empty_channel: Callable[..., tuple[bool, float | None]]
    should_force_timeout_stop: Callable[[int, int], bool]
    should_start_predownload: Callable[..., bool]


def build_entrypoint_app(
    *,
    support: EntrypointSupport,
    bot: commands.Bot,
    component_deps_factory: Callable[[], EntrypointComponentDeps],
    app_cfg_getter: Callable[[], AppConfig],
    get_guild_id_override: Callable[[], int | None],
    registration_deps: EntrypointRegistrationDeps,
    status_count_cache: dict[str, tuple[float, int | str]],
    flip_order: list[str],
    flip_seq: list[str],
    raw_callbacks: EntrypointRawCallbacks,
    runtime_policy_deps: EntrypointRuntimePolicyDeps,
) -> EntrypointApp:
    def ensure_components() -> None:
        if support.state.archive_runtime is not None:
            return
        components = build_entrypoint_components(component_deps_factory())
        apply_entrypoint_components(support.state, components)

    component_access = build_entrypoint_component_access(
        support=support,
        ensure_components=ensure_components,
    )
    glue = EntrypointGlue(
        state=support.state,
        resources=support.resources,
        components=component_access,
    )
    facade = EntrypointFacade(
        components=component_access,
    )
    runtime_tasks = build_entrypoint_runtime_tasks(
        bot=bot,
        support=support,
        app_cfg_getter=app_cfg_getter,
        component_access=component_access,
        raw_callbacks=raw_callbacks,
        compute_timeout_seconds=runtime_policy_deps.compute_timeout_seconds,
        is_gme_format_path=runtime_policy_deps.is_gme_format_path,
        should_advance_after_stop=runtime_policy_deps.should_advance_after_stop,
        should_confirm_output_drop=runtime_policy_deps.should_confirm_output_drop,
        should_disconnect_for_empty_channel=runtime_policy_deps.should_disconnect_for_empty_channel,
        should_force_timeout_stop=runtime_policy_deps.should_force_timeout_stop,
        should_start_predownload=runtime_policy_deps.should_start_predownload,
        facade=facade,
        glue=glue,
    )
    runtime_callbacks = build_entrypoint_runtime_callbacks(
        raw_callbacks=raw_callbacks,
        clear_predownload_state=raw_callbacks.playback.clear_predownload_state,
        facade=facade,
        glue=glue,
        runtime_tasks=runtime_tasks,
    )
    runtime_initializer = build_entrypoint_runtime_initializer(
        bot=bot,
        support=support,
        status_count_cache=status_count_cache,
        flip_order=flip_order,
        flip_seq=flip_seq,
        validate_runtime_dependencies=registration_deps.validate_runtime_dependencies,
        component_access=component_access,
        build_playback_handlers=registration_deps.build_playback_handlers,
        register_core_events=registration_deps.register_core_events,
        register_playback_commands=registration_deps.register_playback_commands,
        register_library_commands=registration_deps.register_library_commands,
        runtime_tasks=runtime_tasks,
        runtime_callbacks=runtime_callbacks,
    )
    compat = EntrypointCompat(
        state=support.state,
        ensure_components=ensure_components,
        guild_id_getter=get_guild_id_override,
    )
    return EntrypointApp(
        support=support,
        bot=bot,
        logger=support.logger,
        ensure_components=ensure_components,
        glue=glue,
        facade=facade,
        runtime_tasks=runtime_tasks,
        runtime_initializer=runtime_initializer,
        compat=compat,
    )


def build_entrypoint_component_access(
    *,
    support: EntrypointSupport,
    ensure_components: Callable[[], None],
) -> EntrypointComponentAccess:
    return EntrypointComponentAccess(
        state=support.state,
        ensure_components=ensure_components,
    )
