"""Direct export entrypoint surface contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


@dataclass(frozen=True, slots=True)
class EntrypointDirectExportSpec:
    export_name: str
    source_name: str
    attr_path: tuple[str, ...] = ()
    public_module_attr: bool = True


ENTRYPOINT_DIRECT_COLLECTION_BINDINGS = (
    EntrypointDirectExportSpec("_skip_to_next", "collection", ("legacy", "skip_to_next")),
    EntrypointDirectExportSpec(
        "_cleanup_orphan_players",
        "collection",
        ("legacy", "cleanup_orphan_players"),
    ),
    EntrypointDirectExportSpec("_stop_all_players", "collection", ("legacy", "stop_all_players")),
    EntrypointDirectExportSpec(
        "_auto_play_after_switch",
        "collection",
        ("legacy", "auto_play_after_switch"),
    ),
    EntrypointDirectExportSpec("_play_subsong", "collection", ("legacy", "play_subsong")),
    EntrypointDirectExportSpec(
        "_cleanup_subsong_temp_wavs",
        "collection",
        ("service_facade", "cleanup_subsong_temp_wavs"),
    ),
    EntrypointDirectExportSpec(
        "_switch_collection",
        "collection",
        ("service_facade", "switch_collection"),
    ),
)

ENTRYPOINT_DIRECT_RUNTIME_BINDINGS = (
    EntrypointDirectExportSpec("_after_stream_end", "runtime"),
    EntrypointDirectExportSpec("_ensure_entrypoint_components", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("_apply_queue_state", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("_place_track_in_queue", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("_queue_position", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("_cancel_monitor", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("pre_download_next", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("_start_targeted_playback_session", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("_play_via_audacious", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("_send_now_playing_embed", "runtime", public_module_attr=False),
    EntrypointDirectExportSpec("monitor_playback", "runtime"),
    EntrypointDirectExportSpec("fetch_metadata_background", "runtime"),
    EntrypointDirectExportSpec("health_watchdog", "runtime"),
)

ENTRYPOINT_DIRECT_EXPORT_BINDINGS = (
    ENTRYPOINT_DIRECT_COLLECTION_BINDINGS + ENTRYPOINT_DIRECT_RUNTIME_BINDINGS
)

ENTRYPOINT_DIRECT_EXPORT_SPECS_BY_NAME = {
    spec.export_name: spec for spec in ENTRYPOINT_DIRECT_EXPORT_BINDINGS
}

ENTRYPOINT_PUBLIC_DIRECT_EXPORT_BINDINGS = tuple(
    spec for spec in ENTRYPOINT_DIRECT_EXPORT_BINDINGS if spec.public_module_attr
)

ENTRYPOINT_PRIVATE_DIRECT_EXPORT_BINDINGS = tuple(
    spec for spec in ENTRYPOINT_DIRECT_EXPORT_BINDINGS if not spec.public_module_attr
)


class SurfaceExportResolver(Protocol):
    def resolve_legacy(self, name: str) -> Any: ...

    def resolve_collection(self, spec: EntrypointDirectExportSpec) -> Callable[..., Any]: ...

    def resolve_runtime(self, spec: EntrypointDirectExportSpec) -> Callable[..., Any]: ...
