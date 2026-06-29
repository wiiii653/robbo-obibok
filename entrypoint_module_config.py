"""Composition helpers for entrypoint module dependency bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from entrypoint_module import (
    EntrypointModuleCollectionDeps,
    EntrypointModuleDeps,
    EntrypointModuleRuntimeDeps,
)


@dataclass(slots=True)
class EntrypointModuleRegistrationConfig:
    build_playback_handlers: Callable[..., object]
    register_core_events: Callable[..., object]
    register_playback_commands: Callable[..., object]
    register_library_commands: Callable[..., object]
    validate_runtime_dependencies: Callable[[], list[str]]


@dataclass(slots=True)
class EntrypointModulePlaybackPolicyConfig:
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
class EntrypointModuleCollectionConfig:
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
