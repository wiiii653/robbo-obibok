"""Bootstrap object for the legacy entrypoint module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

from entrypoint_app import (
    EntrypointApp,
    EntrypointRegistrationDeps,
    EntrypointRuntimePolicyDeps,
    build_entrypoint_app,
)
from entrypoint_legacy_surface import build_entrypoint_exports
from entrypoint_module_builders import (
    build_module_component_deps,
    build_module_raw_callbacks,
)
from entrypoint_module_support import build_entrypoint_module_bootstrap

if TYPE_CHECKING:
    from discord.ext import commands
    from entrypoint_launcher_support import EntrypointSupport


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
    build_playback_handlers: Callable[..., object]
    register_core_events: Callable[..., object]
    register_playback_commands: Callable[..., object]
    register_library_commands: Callable[..., object]
    validate_runtime_dependencies: Callable[[], list[str]]
    classify_track_route: Callable[..., dict[str, str]]
    compute_timeout_seconds: Callable[..., int]
    is_gme_format_path: Callable[[str], bool]
    should_advance_after_stop: Callable[..., tuple[bool, float | None]]
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]]
    should_disconnect_for_empty_channel: Callable[..., tuple[bool, float | None]]
    should_force_timeout_stop: Callable[[int, int], bool]
    should_start_predownload: Callable[..., bool]
    mod_only: Callable[[], object]


@dataclass(slots=True)
class EntrypointModuleCollectionDeps:
    build_collection_state_update: Callable[[str, list[str]], dict[str, object]]
    format_flip_sequence: Callable[[list[str], str], str]
    prepare_playback_queue: Callable[..., dict[str, object]]
    remove_user_track: Callable[..., object]
    filter_blacklisted_track_entries: Callable[..., object]
    filter_blacklisted_track_urls: Callable[..., object]
    load_user_tracks: Callable[..., object]
    toggle_user_track_entry: Callable[..., object]
    flip_order: list[str]
    flip_seq: list[str]


@dataclass(slots=True)
class EntrypointModuleDeps:
    runtime: EntrypointModuleRuntimeDeps
    collection: EntrypointModuleCollectionDeps


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
    exports = build_entrypoint_exports(app).module_exports()
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
