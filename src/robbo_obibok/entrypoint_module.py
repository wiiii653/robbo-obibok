"""Bootstrap object for the legacy entrypoint module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .bot_dependencies import (
    CommandDecoratorFactory,
    PlaybackHandlerDependencies,
    PlaybackHandlerMap,
)
from .domain_state import PlaylistState
from .entrypoint_app import (
    EntrypointApp,
    EntrypointRegistrationDeps,
    EntrypointRuntimePolicyDeps,
    build_entrypoint_app,
    create_bot,
)
from .entrypoint_callback_groups import (
    BootstrapStaticCallbacks,
    CollectionStaticCallbacks,
    EntrypointRawCallbacks,
    LibraryStaticCallbacks,
    PlaybackStaticCallbacks,
)
from .entrypoint_components import EntrypointComponentDeps
from .entrypoint_glue import build_single_guild_check
from .entrypoint_launcher_runtime import EntrypointSupport, build_entrypoint_support
from .playback_process import stop_all_players as runtime_stop_all_players
from .runtime_bindings import LegacyRuntimeBindings
from .runtime_protocols import ArchiveRuntimeProtocol, PlaybackAssetsProtocol, ServiceFacadeProtocol

if TYPE_CHECKING:
    from discord import Colour
    from discord.ext import commands


@dataclass(slots=True)
class _EntrypointExportBindings:
    app: EntrypointApp

    def ensure_entrypoint_components(self) -> None:
        self.app.ensure_components()

    def after_stream_end(
        self,
        guild_id: int | None,
        error: Exception | None,
        source_id: int = 0,
    ) -> None:
        self.app.glue.after_stream_end(guild_id, error, source_id)

    def apply_queue_state(self, state: PlaylistState, queue_state: dict[str, object]) -> bool:
        return self.app.glue.apply_queue_state(state, queue_state)

    def place_track_in_queue(self, queue: list[str], url: str) -> tuple[list[str], int]:
        return self.app.glue.place_track_in_queue(queue, url)

    def queue_position(self, state: PlaylistState) -> tuple[int, int]:
        return self.app.glue.queue_position(state)

    async def cancel_monitor(self, state: PlaylistState) -> None:
        await self.app.glue.cancel_monitor(state)

    async def pre_download_next(self, state: PlaylistState) -> None:
        await self.app.glue.pre_download_next(state)

    async def start_targeted_playback_session(self, ctx: object, state: PlaylistState, url: str) -> bool:
        return await self.app.glue.start_targeted_playback_session(ctx, state, url)

    async def play_via_audacious(
        self,
        state: PlaylistState,
        playback_path: str,
        *,
        current_path: str | None = None,
    ) -> None:
        await self.app.glue.play_via_audacious(state, playback_path, current_path=current_path)

    async def send_now_playing_embed(
        self,
        ctx: object,
        state: PlaylistState,
        url: str,
        *,
        title: str,
        color: Colour,
        footer: str,
        author: str = "",
        extra_fields: list[tuple[str, str]] | None = None,
    ) -> None:
        await self.app.glue.send_now_playing_embed(
            ctx,
            state,
            url,
            title=title,
            color=color,
            footer=footer,
            author=author,
            extra_fields=extra_fields,
        )

    async def monitor_playback(self, ctx: object, vc: object, guild_id: int) -> None:
        self.app.ensure_components()
        await self.app.runtime_tasks.monitor_playback(ctx, vc, guild_id)

    async def fetch_metadata_background(self) -> None:
        await self.app.runtime_tasks.fetch_metadata_background()

    async def health_watchdog(self) -> None:
        self.app.ensure_components()
        await self.app.runtime_tasks.health_watchdog()


def build_entrypoint_exports(app: EntrypointApp) -> dict[str, object]:
    bindings = _EntrypointExportBindings(app=app)
    return {
        "_ensure_entrypoint_components": lambda: bindings.ensure_entrypoint_components,
        "_after_stream_end": lambda: bindings.after_stream_end,
        "_apply_queue_state": lambda: bindings.apply_queue_state,
        "_place_track_in_queue": lambda: bindings.place_track_in_queue,
        "_queue_position": lambda: bindings.queue_position,
        "_cancel_monitor": lambda: bindings.cancel_monitor,
        "pre_download_next": lambda: bindings.pre_download_next,
        "_start_targeted_playback_session": lambda: bindings.start_targeted_playback_session,
        "_play_via_audacious": lambda: bindings.play_via_audacious,
        "_send_now_playing_embed": lambda: bindings.send_now_playing_embed,
        "monitor_playback": lambda: bindings.monitor_playback,
        "fetch_metadata_background": lambda: bindings.fetch_metadata_background,
        "health_watchdog": lambda: bindings.health_watchdog,
    }


@dataclass(slots=True)
class EntrypointModule:
    support: EntrypointSupport
    bot: commands.Bot
    app: EntrypointApp
    single_guild_check: Callable[[object], bool]
    guild_id_getter: Callable[[], int | None]
    guild_id_setter: Callable[[int | None], None]
    status_count_cache: dict[str, tuple[float, int | str]]
    exports: dict[str, object]


@dataclass(slots=True)
class EntrypointModuleRuntimeDeps:
    build_playback_handlers: Callable[[PlaybackHandlerDependencies], PlaybackHandlerMap]
    register_core_events: Callable[..., None]
    register_playback_commands: Callable[..., None]
    register_library_commands: Callable[..., None]
    validate_runtime_dependencies: Callable[[], None]
    classify_track_route: Callable[..., dict[str, str]]
    compute_timeout_seconds: Callable[..., int]
    is_gme_format_path: Callable[[str | None], bool]
    should_advance_after_stop: Callable[..., tuple[bool, float | None]]
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]]
    should_disconnect_for_empty_channel: Callable[..., tuple[bool, float | None]]
    should_force_timeout_stop: Callable[[int, int], bool]
    should_start_predownload: Callable[..., bool]
    mod_only: CommandDecoratorFactory


@dataclass(slots=True)
class EntrypointModuleCollectionDeps:
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]]
    format_flip_sequence: Callable[[list[str], str], str]
    prepare_playback_queue: Callable[..., dict[str, object]]
    remove_user_track: Callable[[dict[str, object], int | str, str], tuple[dict[str, object], bool]]
    filter_blacklisted_track_entries: Callable[
        [list[dict[str, object]], dict[str, object], int],
        list[dict[str, object]],
    ]
    filter_blacklisted_track_urls: Callable[
        [list[str], dict[object, object], int | str],
        list[str],
    ]
    load_user_tracks: Callable[[dict[str, object], int | str], list[dict[str, object]]]
    toggle_user_track_entry: Callable[
        [dict[str, object], int | str, dict[str, object]],
        tuple[dict[str, object], bool],
    ]
    flip_order: list[str]
    flip_seq: list[str]


@dataclass(slots=True)
class EntrypointModuleDeps:
    runtime: EntrypointModuleRuntimeDeps
    collection: EntrypointModuleCollectionDeps


@dataclass(slots=True)
class EntrypointModuleRegistrationConfig:
    build_playback_handlers: Callable[[PlaybackHandlerDependencies], PlaybackHandlerMap]
    register_core_events: Callable[..., None]
    register_playback_commands: Callable[..., None]
    register_library_commands: Callable[..., None]
    validate_runtime_dependencies: Callable[[], None]


@dataclass(slots=True)
class EntrypointModulePlaybackPolicyConfig:
    classify_track_route: Callable[..., dict[str, str]]
    compute_timeout_seconds: Callable[..., int]
    is_gme_format_path: Callable[[str | None], bool]
    should_advance_after_stop: Callable[..., tuple[bool, float | None]]
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]]
    should_disconnect_for_empty_channel: Callable[..., tuple[bool, float | None]]
    should_force_timeout_stop: Callable[[int, int], bool]
    should_start_predownload: Callable[..., bool]
    mod_only: CommandDecoratorFactory


@dataclass(slots=True)
class EntrypointModuleCollectionConfig:
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]]
    format_flip_sequence: Callable[[list[str], str], str]
    prepare_playback_queue: Callable[..., dict[str, object]]
    remove_user_track: Callable[[dict[str, object], int | str, str], tuple[dict[str, object], bool]]
    filter_blacklisted_track_entries: Callable[
        [list[dict[str, object]], dict[str, object], int],
        list[dict[str, object]],
    ]
    filter_blacklisted_track_urls: Callable[
        [list[str], dict[object, object], int | str],
        list[str],
    ]
    load_user_tracks: Callable[[dict[str, object], int | str], list[dict[str, object]]]
    toggle_user_track_entry: Callable[
        [dict[str, object], int | str, dict[str, object]],
        tuple[dict[str, object], bool],
    ]
    flip_order: list[str]
    flip_seq: list[str]


def build_entrypoint_module_deps(
    *,
    registration: EntrypointModuleRegistrationConfig,
    playback_policy: EntrypointModulePlaybackPolicyConfig,
    collection: EntrypointModuleCollectionConfig,
) -> EntrypointModuleDeps:
    return EntrypointModuleDeps(
        runtime=EntrypointModuleRuntimeDeps(
            build_playback_handlers=registration.build_playback_handlers,
            register_core_events=registration.register_core_events,
            register_playback_commands=registration.register_playback_commands,
            register_library_commands=registration.register_library_commands,
            validate_runtime_dependencies=registration.validate_runtime_dependencies,
            classify_track_route=playback_policy.classify_track_route,
            compute_timeout_seconds=playback_policy.compute_timeout_seconds,
            is_gme_format_path=playback_policy.is_gme_format_path,
            should_advance_after_stop=playback_policy.should_advance_after_stop,
            should_confirm_output_drop=playback_policy.should_confirm_output_drop,
            should_disconnect_for_empty_channel=playback_policy.should_disconnect_for_empty_channel,
            should_force_timeout_stop=playback_policy.should_force_timeout_stop,
            should_start_predownload=playback_policy.should_start_predownload,
            mod_only=playback_policy.mod_only,
        ),
        collection=EntrypointModuleCollectionDeps(
            build_collection_state_update=collection.build_collection_state_update,
            format_flip_sequence=collection.format_flip_sequence,
            prepare_playback_queue=collection.prepare_playback_queue,
            remove_user_track=collection.remove_user_track,
            filter_blacklisted_track_entries=collection.filter_blacklisted_track_entries,
            filter_blacklisted_track_urls=collection.filter_blacklisted_track_urls,
            load_user_tracks=collection.load_user_tracks,
            toggle_user_track_entry=collection.toggle_user_track_entry,
            flip_order=collection.flip_order,
            flip_seq=collection.flip_seq,
        ),
    )


@dataclass(slots=True)
class EntrypointModuleBootstrap:
    support: EntrypointSupport
    bot: commands.Bot
    single_guild_check: Callable[[object], bool]
    guild_id_getter: Callable[[], int | None]
    guild_id_setter: Callable[[int | None], None]
    status_count_cache: dict[str, tuple[float, int | str]]
    clear_predownload_state: Callable[[PlaylistState], None]


def build_entrypoint_module_bootstrap(
    *,
    module_path: str,
    logger_name: str,
    load_last_collection: Callable[[str], str | None],
    atomic_json_write: Callable[[str, object, object], None],
    command_prefix: Callable[[object, object], object],
) -> EntrypointModuleBootstrap:
    support = build_entrypoint_support(
        module_path=module_path,
        logger_name=logger_name,
        load_last_collection=load_last_collection,
        atomic_json_write=atomic_json_write,
    )
    bot = create_bot(command_prefix)
    single_guild_check = build_single_guild_check(
        guild_id_getter=lambda: support.guild_scope.resolve(support.resources.app_cfg().guild_id),
    )
    bot.check(single_guild_check)

    def set_guild_id_override(guild_id: int | None) -> None:
        support.guild_scope.set_override(guild_id)

    def get_guild_id_override() -> int | None:
        return support.guild_scope.get_override()

    def clear_predownload_state(state: PlaylistState, *, keep_file: bool = False) -> None:
        from .entrypoint_glue import clear_predownload_state as clear_state

        clear_state(state, keep_file=keep_file)

    return EntrypointModuleBootstrap(
        support=support,
        bot=bot,
        single_guild_check=single_guild_check,
        guild_id_getter=get_guild_id_override,
        guild_id_setter=set_guild_id_override,
        status_count_cache={},
        clear_predownload_state=clear_predownload_state,
    )


def build_module_component_deps(
    *,
    support: EntrypointSupport,
    clear_predownload_state: Callable[..., None],
    filter_blacklisted_track_urls: Callable[[list[str], dict[object, object], int | str], list[str]],
) -> Callable[[], EntrypointComponentDeps]:
    def cleanup_subsong_temp_wavs(state: PlaylistState) -> None:
        service_facade = support.state.service_facade
        assert service_facade is not None
        service_facade.cleanup_subsong_temp_wavs(state)

    def component_deps() -> EntrypointComponentDeps:
        return EntrypointComponentDeps(
            boot_builder=support.boot,
            logger=support.logger,
            sink_name=support.resources.app_cfg().sink_name,
            audio_format=support.resources.config()["audio"]["format"],
            sample_rate=support.resources.config()["audio"]["sample_rate"],
            channels=support.resources.config()["audio"]["channels"],
            temp_dir=support.resources.app_cfg().temp_dir,
            archive_runtime_config=support.resources.archive_runtime_config(),
            subsongs=support.resources.get_subsongs_runtime(),
            build_temp_path=support.resources.build_temp_path,
            get_shared_session=support.session_runtime.get_shared_session,
            clear_predownload_state=lambda state: clear_predownload_state(state),
            blacklist_filter=filter_blacklisted_track_urls,
            stop_all_players_impl=runtime_stop_all_players,
            audacious_play=support.resources.audacious_play,
            audacious_stop=support.resources.audacious_stop,
            cleanup_subsong_temp_wavs_impl=cleanup_subsong_temp_wavs,
            build_legacy_bindings=build_legacy_bindings,
        )

    return component_deps


def build_module_raw_callbacks(
    *,
    support: EntrypointSupport,
    clear_predownload_state: Callable[..., None],
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]],
    classify_track_route: Callable[..., dict[str, str]],
    format_flip_sequence: Callable[[list[str], str], str],
    prepare_playback_queue: Callable[..., dict[str, object]],
    save_last_collection: Callable[[str, str], None],
    set_volume_for_collection: Callable[[str], None],
    filter_blacklisted_track_entries: Callable[
        [list[dict[str, object]], dict[str, object], int],
        list[dict[str, object]],
    ],
    load_user_tracks: Callable[[dict[str, object], int | str], list[dict[str, object]]],
    remove_user_track: Callable[[dict[str, object], int | str, str], tuple[dict[str, object], bool]],
    toggle_user_track_entry: Callable[
        [dict[str, object], int | str, dict[str, object]],
        tuple[dict[str, object], bool],
    ],
    mod_only: CommandDecoratorFactory,
) -> EntrypointRawCallbacks:
    return EntrypointRawCallbacks(
        playback=PlaybackStaticCallbacks(
            audacious_play=support.resources.audacious_play,
            audacious_song=support.resources.audacious_song,
            audacious_stop=support.resources.audacious_stop,
            classify_track_route=classify_track_route,
            clear_predownload_state=lambda state, *, keep_file=False: clear_predownload_state(state, keep_file=keep_file),
            get_shared_session=support.session_runtime.get_shared_session,
            is_playing=support.resources.is_playing,
            prepare_playback_queue=prepare_playback_queue,
        ),
        library=LibraryStaticCallbacks(
            filter_blacklisted_track_entries=filter_blacklisted_track_entries,
            load_user_tracks=load_user_tracks,
            remove_user_track=remove_user_track,
            toggle_user_track_entry=toggle_user_track_entry,
        ),
        collection=CollectionStaticCallbacks(
            build_collection_state_update=build_collection_state_update,
            format_flip_sequence=format_flip_sequence,
            save_last_collection=save_last_collection,
            set_volume_for_collection=set_volume_for_collection,
        ),
        bootstrap=BootstrapStaticCallbacks(
            close_shared_session=support.session_runtime.close_shared_session,
            mod_only=mod_only,
            setup_virtual_sink=support.resources.setup_virtual_sink,
            ensure_audacious=support.resources.ensure_audacious,
            setup_audacious_sid_config=support.resources.setup_audacious_sid_config,
        ),
    )


def build_legacy_bindings(
    *,
    archive_runtime: ArchiveRuntimeProtocol,
    playback_assets: PlaybackAssetsProtocol,
    service_facade: ServiceFacadeProtocol,
    cleanup_subsong_temp_wavs_impl: Callable[[PlaylistState], None],
) -> LegacyRuntimeBindings:
    return LegacyRuntimeBindings(
        archive_runtime=archive_runtime,
        playback_assets=playback_assets,
        service_facade=service_facade,
        cleanup_subsong_temp_wavs_impl=cleanup_subsong_temp_wavs_impl,
    )


def build_entrypoint_module(
    *,
    module_path: str,
    logger_name: str,
    load_last_collection: Callable[[str], str | None],
    save_last_collection: Callable[[str, str], None],
    atomic_json_write: Callable[[str, object, object], None],
    command_prefix: Callable[[object, object], object],
    deps: EntrypointModuleDeps,
) -> EntrypointModule:
    bootstrap = build_entrypoint_module_bootstrap(
        module_path=module_path,
        logger_name=logger_name,
        load_last_collection=load_last_collection,
        atomic_json_write=atomic_json_write,
        command_prefix=command_prefix,
    )
    support = bootstrap.support

    component_deps = build_module_component_deps(
        support=support,
        clear_predownload_state=bootstrap.clear_predownload_state,
        filter_blacklisted_track_urls=deps.collection.filter_blacklisted_track_urls,
    )

    raw_callbacks = build_module_raw_callbacks(
        support=support,
        clear_predownload_state=bootstrap.clear_predownload_state,
        build_collection_state_update=deps.collection.build_collection_state_update,
        classify_track_route=deps.runtime.classify_track_route,
        format_flip_sequence=deps.collection.format_flip_sequence,
        prepare_playback_queue=deps.collection.prepare_playback_queue,
        save_last_collection=save_last_collection,
        set_volume_for_collection=support.resources.set_volume_for_collection,
        filter_blacklisted_track_entries=deps.collection.filter_blacklisted_track_entries,
        load_user_tracks=deps.collection.load_user_tracks,
        remove_user_track=deps.collection.remove_user_track,
        toggle_user_track_entry=deps.collection.toggle_user_track_entry,
        mod_only=deps.runtime.mod_only,
    )
    app = build_entrypoint_app(
        support=support,
        bot=bootstrap.bot,
        component_deps_factory=component_deps,
        app_cfg_getter=support.resources.app_cfg,
        get_guild_id_override=bootstrap.guild_id_getter,
        registration_deps=EntrypointRegistrationDeps(
            build_playback_handlers=deps.runtime.build_playback_handlers,
            register_core_events=deps.runtime.register_core_events,
            register_playback_commands=deps.runtime.register_playback_commands,
            register_library_commands=deps.runtime.register_library_commands,
            validate_runtime_dependencies=deps.runtime.validate_runtime_dependencies,
        ),
        status_count_cache=bootstrap.status_count_cache,
        flip_order=deps.collection.flip_order,
        flip_seq=deps.collection.flip_seq,
        raw_callbacks=raw_callbacks,
        runtime_policy_deps=EntrypointRuntimePolicyDeps(
            compute_timeout_seconds=deps.runtime.compute_timeout_seconds,
            is_gme_format_path=deps.runtime.is_gme_format_path,
            should_advance_after_stop=deps.runtime.should_advance_after_stop,
            should_confirm_output_drop=deps.runtime.should_confirm_output_drop,
            should_disconnect_for_empty_channel=deps.runtime.should_disconnect_for_empty_channel,
            should_force_timeout_stop=deps.runtime.should_force_timeout_stop,
            should_start_predownload=deps.runtime.should_start_predownload,
        ),
    )
    exports = build_entrypoint_exports(app)
    return EntrypointModule(
        support=support,
        bot=bootstrap.bot,
        app=app,
        single_guild_check=bootstrap.single_guild_check,
        guild_id_getter=bootstrap.guild_id_getter,
        guild_id_setter=bootstrap.guild_id_setter,
        status_count_cache=bootstrap.status_count_cache,
        exports=exports,
    )
