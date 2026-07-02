"""Executable assembly helpers for the robbo-obibok entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from .bot_events import register_core_events
from .bot_persistence import (
    filter_blacklisted_track_entries,
    filter_blacklisted_track_urls,
    load_user_tracks,
    toggle_user_track_entry,
)
from .entrypoint_glue import mod_only
from .entrypoint_launcher_loader import LazyEntrypointLauncher, build_entrypoint_launcher
from .entrypoint_module import (
    EntrypointModuleCollectionConfig,
    EntrypointModuleDeps,
    EntrypointModulePlaybackPolicyConfig,
    EntrypointModuleRegistrationConfig,
    build_entrypoint_module_deps,
)
from .entrypoint_module_bindings import (
    ALLOW_DEPRECATED,
    ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXPORT_GRAPH,
    build_entrypoint_compat_module_bindings,
    build_entrypoint_stable_module_bindings,
)
from .entrypoint_startup import atomic_json_write, load_last_collection, save_last_collection
from .entrypoint_surface_assembly import EntrypointModuleSurface, build_entrypoint_module_surface
from .library_commands import register_library_commands
from .playback_commands import register_playback_commands
from .playback_handlers import build_playback_handlers
from .runtime_support import (
    build_collection_state_update,
    classify_track_route,
    compute_timeout_seconds,
    format_flip_sequence,
    is_gme_format_path,
    prepare_playback_queue,
    remove_user_track,
    should_advance_after_stop,
    should_confirm_output_drop,
    should_disconnect_for_empty_channel,
    should_force_timeout_stop,
    should_start_predownload,
    validate_runtime_dependencies,
)


@dataclass(frozen=True, slots=True)
class EntrypointExecutableProviders:
    registration: EntrypointModuleRegistrationConfig
    playback_policy: EntrypointModulePlaybackPolicyConfig
    collection: EntrypointModuleCollectionConfig


def build_default_entrypoint_providers(
    *,
    flip_order: list[str],
    flip_seq: list[str],
) -> EntrypointExecutableProviders:
    return EntrypointExecutableProviders(
        registration=EntrypointModuleRegistrationConfig(
            build_playback_handlers=build_playback_handlers,
            register_core_events=register_core_events,
            register_playback_commands=register_playback_commands,
            register_library_commands=register_library_commands,
            validate_runtime_dependencies=validate_runtime_dependencies,
        ),
        playback_policy=EntrypointModulePlaybackPolicyConfig(
            classify_track_route=classify_track_route,
            compute_timeout_seconds=compute_timeout_seconds,
            is_gme_format_path=is_gme_format_path,
            should_advance_after_stop=should_advance_after_stop,
            should_confirm_output_drop=should_confirm_output_drop,
            should_disconnect_for_empty_channel=should_disconnect_for_empty_channel,
            should_force_timeout_stop=should_force_timeout_stop,
            should_start_predownload=should_start_predownload,
            mod_only=mod_only,
        ),
        collection=EntrypointModuleCollectionConfig(
            build_collection_state_update=build_collection_state_update,
            format_flip_sequence=format_flip_sequence,
            prepare_playback_queue=prepare_playback_queue,
            remove_user_track=remove_user_track,
            filter_blacklisted_track_entries=filter_blacklisted_track_entries,
            filter_blacklisted_track_urls=filter_blacklisted_track_urls,
            load_user_tracks=load_user_tracks,
            toggle_user_track_entry=toggle_user_track_entry,
            flip_order=flip_order,
            flip_seq=flip_seq,
        ),
    )


@dataclass(frozen=True, slots=True)
class EntrypointExecutableAssembly:
    providers: EntrypointExecutableProviders
    deps: EntrypointModuleDeps
    launcher: LazyEntrypointLauncher
    legacy_resolve: Callable[[str], object]
    surface: EntrypointModuleSurface
    bindings: dict[str, object]
    compat_bindings: dict[str, object]
    compat_policy: bool


def build_default_entrypoint_module_deps(
    *,
    flip_order: list[str],
    flip_seq: list[str],
) -> EntrypointModuleDeps:
    _, deps = build_entrypoint_executable_dependencies(
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    return deps


def build_entrypoint_executable_dependencies(
    *,
    flip_order: list[str],
    flip_seq: list[str],
) -> tuple[EntrypointExecutableProviders, EntrypointModuleDeps]:
    providers = build_default_entrypoint_providers(
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    deps = build_entrypoint_module_deps(
        registration=providers.registration,
        playback_policy=providers.playback_policy,
        collection=providers.collection,
    )
    return providers, deps


def build_entrypoint_executable_assembly(
    *,
    module_path: str,
    logger_name: str,
    command_prefix: Callable[[object, object], object],
    flip_order: list[str],
    flip_seq: list[str],
) -> EntrypointExecutableAssembly:
    providers, deps = build_entrypoint_executable_dependencies(
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    launcher = build_entrypoint_launcher(
        module_path=module_path,
        logger_name=logger_name,
        load_last_collection=load_last_collection,
        save_last_collection=save_last_collection,
        atomic_json_write=atomic_json_write,
        command_prefix=command_prefix,
        deps=deps,
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    legacy_resolve = build_entrypoint_legacy_resolver(loader=launcher.loader)
    surface = build_entrypoint_module_surface(
        launcher=launcher,
        resolve_fallback=legacy_resolve,
    )
    bindings = build_entrypoint_stable_module_bindings(surface)
    compat_bindings = build_entrypoint_compat_module_bindings(
        launcher.loader,
        resolver=launcher.loader.resolve_legacy,
    )
    return EntrypointExecutableAssembly(
        providers=providers,
        deps=deps,
        launcher=launcher,
        legacy_resolve=legacy_resolve,
        surface=surface,
        bindings=bindings,
        compat_bindings=compat_bindings,
        compat_policy=ALLOW_DEPRECATED,
    )


def build_strict_entrypoint_executable_assembly(
    *,
    module_path: str,
    logger_name: str,
    command_prefix: Callable[[object, object], object],
    flip_order: list[str],
    flip_seq: list[str],
) -> EntrypointExecutableAssembly:
    return build_entrypoint_executable_assembly(
        module_path=module_path,
        logger_name=logger_name,
        command_prefix=command_prefix,
        flip_order=flip_order,
        flip_seq=flip_seq,
    )


class EntrypointLegacyResolverLoaderProtocol(Protocol):
    def resolve_legacy(self, name: str) -> object: ...

    def resolve(self, name: str) -> object: ...


def build_entrypoint_legacy_resolver(
    *,
    loader: EntrypointLegacyResolverLoaderProtocol,
) -> Callable[[str], object]:
    def resolve(name: str) -> object:
        if name in {
            "bot",
            "get_guild_id_override",
            "set_guild_id_override",
        } | ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES:
            return loader.resolve_legacy(name)
        if name not in ENTRYPOINT_EXPORT_GRAPH.compat_names:
            raise AttributeError(name)
        return loader.resolve(name)

    return resolve
