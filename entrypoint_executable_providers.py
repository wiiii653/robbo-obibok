"""Default provider wiring for the robbo-obibok executable assembly."""

from __future__ import annotations

from dataclasses import dataclass

from bot_events import register_core_events
from bot_persistence import (
    filter_blacklisted_track_entries,
    filter_blacklisted_track_urls,
    load_user_tracks,
    toggle_user_track_entry,
)
from entrypoint_glue import mod_only
from entrypoint_module_config import (
    EntrypointModuleCollectionConfig,
    EntrypointModulePlaybackPolicyConfig,
    EntrypointModuleRegistrationConfig,
)
from library_commands import register_library_commands
from playback_commands import register_playback_commands
from playback_handlers import build_playback_handlers
from runtime_support import (
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
