"""Assembled entrypoint application support."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import discord
from discord.ext import commands

import entrypoint_state as state_protocols
from bot_dependencies import (
    PlaybackHandlerDependencies,
    PlaybackHandlerMap,
)
from collection_specs import CollectionSpec
from domain_config import AppConfig
from domain_services import AppServicesProtocol
from domain_state import PlaylistState
from entrypoint_callback_groups import (
    AppEntrypointCallbacks,
    BootstrapEntrypointCallbacks,
    CollectionEntrypointCallbacks,
    EntrypointRawCallbacks,
    LibraryEntrypointCallbacks,
    PlaybackEntrypointCallbacks,
)
from entrypoint_components import (
    EntrypointComponentDeps,
    apply_entrypoint_components,
    build_entrypoint_components,
)
from entrypoint_glue import EntrypointGlue
from entrypoint_runtime import EntrypointRuntimeInitializer, RuntimeRegistrationHooks
from entrypoint_runtime_tasks import EntrypointRuntimeTasks, build_entrypoint_runtime_tasks
from entrypoint_surface_assembly import build_entrypoint_compat_registry_attrs

if TYPE_CHECKING:
    from entrypoint_launcher_loader import EntrypointSupport
    from entrypoint_state import EntrypointCompatStateProtocol
    from playback_assets import PlaybackAssetRuntime
    from playback_helpers import NowPlayingDependencies
    from runtime_bindings import LegacyRuntimeBindings
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
class EntrypointExportRegistry:
    eager_attrs: dict[str, Callable[[], object]] = field(default_factory=dict)
    lazy_attrs: dict[str, Callable[[], object]] = field(default_factory=dict)

    def register_eager(self, **attrs: Callable[[], object]) -> "EntrypointExportRegistry":
        self.eager_attrs.update(attrs)
        return self

    def register_lazy(self, **attrs: Callable[[], object]) -> "EntrypointExportRegistry":
        self.lazy_attrs.update(attrs)
        return self

    def resolve(self, name: str, ensure_components: Callable[[], None]) -> object:
        eager = self.eager_attrs.get(name)
        if eager is not None:
            return eager()
        lazy = self.lazy_attrs.get(name)
        if lazy is None:
            raise AttributeError(name)
        ensure_components()
        return lazy()

    def module_exports(self) -> dict[str, object]:
        return {name: resolver() for name, resolver in self.eager_attrs.items()}


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


def build_entrypoint_runtime_callbacks(
    *,
    raw_callbacks: EntrypointRawCallbacks,
    clear_predownload_state: Callable[..., None],
    facade: EntrypointFacade,
    glue: EntrypointGlue,
    runtime_tasks: EntrypointRuntimeTasks,
) -> AppEntrypointCallbacks:
    return AppEntrypointCallbacks(
        playback=PlaybackEntrypointCallbacks(
            apply_queue_state=glue.apply_queue_state,
            audacious_play=raw_callbacks.playback.audacious_play,
            audacious_song=raw_callbacks.playback.audacious_song,
            audacious_stop=raw_callbacks.playback.audacious_stop,
            build_temp_path=glue.build_temp_path,
            classify_track_route=raw_callbacks.playback.classify_track_route,
            clear_predownload_state=clear_predownload_state,
            cleanup_subsong_temp_wavs=facade.cleanup_subsong_temp_wavs,
            get_shared_session=raw_callbacks.playback.get_shared_session,
            is_playing=raw_callbacks.playback.is_playing,
            monitor_playback=runtime_tasks.monitor_playback,
            play_subsong=facade.play_subsong,
            play_via_audacious=glue.play_via_audacious,
            place_track_in_queue=glue.place_track_in_queue,
            prepare_playback_queue=raw_callbacks.playback.prepare_playback_queue,
            queue_position=glue.queue_position,
            send_now_playing_embed=glue.send_now_playing_embed,
        ),
        library=LibraryEntrypointCallbacks(
            filter_blacklisted_track_entries=raw_callbacks.library.filter_blacklisted_track_entries,
            load_user_tracks=raw_callbacks.library.load_user_tracks,
            remove_user_track=raw_callbacks.library.remove_user_track,
            toggle_user_track_entry=raw_callbacks.library.toggle_user_track_entry,
        ),
        collection=CollectionEntrypointCallbacks(
            auto_play_after_switch=facade.auto_play_after_switch,
            build_collection_state_update=raw_callbacks.collection.build_collection_state_update,
            format_flip_sequence=raw_callbacks.collection.format_flip_sequence,
            save_last_collection=raw_callbacks.collection.save_last_collection,
            set_volume_for_collection=raw_callbacks.collection.set_volume_for_collection,
            stop_all_players=facade.stop_all_players,
            switch_collection=facade.switch_collection,
        ),
        bootstrap=BootstrapEntrypointCallbacks(
            close_shared_session=raw_callbacks.bootstrap.close_shared_session,
            mod_only=raw_callbacks.bootstrap.mod_only,
            cleanup_orphan_players=facade.cleanup_orphan_players,
            setup_virtual_sink=raw_callbacks.bootstrap.setup_virtual_sink,
            ensure_audacious=raw_callbacks.bootstrap.ensure_audacious,
            setup_audacious_sid_config=raw_callbacks.bootstrap.setup_audacious_sid_config,
        ),
    )


def build_entrypoint_runtime_initializer(
    *,
    bot: commands.Bot,
    support: EntrypointSupport,
    status_count_cache: dict[str, tuple[float, int | str]],
    flip_order: list[str],
    flip_seq: list[str],
    validate_runtime_dependencies: Callable[[], None],
    component_access: EntrypointComponentAccess,
    build_playback_handlers: Callable[[PlaybackHandlerDependencies], PlaybackHandlerMap],
    register_core_events: Callable[..., None],
    register_playback_commands: Callable[..., None],
    register_library_commands: Callable[..., None],
    runtime_tasks: EntrypointRuntimeTasks,
    runtime_callbacks: AppEntrypointCallbacks,
) -> EntrypointRuntimeInitializer:
    return EntrypointRuntimeInitializer(
        root_dir=support.root_dir,
        logger=support.logger,
        bot=bot,
        state=support.state,
        resources=support.resources,
        status_count_cache=status_count_cache,
        flip_order=flip_order,
        flip_seq=flip_seq,
        validate_runtime_dependencies=validate_runtime_dependencies,
        components=component_access,
        registration_hooks=RuntimeRegistrationHooks(
            build_playback_handlers=build_playback_handlers,
            register_core_events=register_core_events,
            register_playback_commands=register_playback_commands,
            register_library_commands=register_library_commands,
            health_watchdog=runtime_tasks.health_watchdog,
            fetch_metadata_background=runtime_tasks.fetch_metadata_background,
        ),
        callbacks=runtime_callbacks,
    )


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


def build_default_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    return intents


def create_bot(command_prefix: Any) -> commands.Bot:
    bot = commands.Bot(command_prefix=command_prefix, intents=build_default_intents())
    bot.remove_command("help")
    return bot


def run_bot_entrypoint(
    *,
    initialize_runtime: Callable[[], object],
    install_runtime_hooks: Callable[..., None],
    handle_signal: Callable[[int, object], None],
    release_process_lock: Callable[[str], None],
    bot: commands.Bot,
    lock_file_getter: Callable[[], str],
    token_getter: Callable[[], str],
) -> None:
    initialize_runtime()
    install_runtime_hooks(
        handle_signal=handle_signal,
        release_lock=lambda: release_process_lock(lock_file_getter()),
    )
    try:
        asyncio.run(bot.start(token_getter()))
    finally:
        release_process_lock(lock_file_getter())
