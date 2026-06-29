"""Compat-facing entrypoint surface contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntrypointCompatBindingSpec:
    export_name: str
    view_name: str
    state_attr: str | None = None


ENTRYPOINT_COMPAT_GUILD_ID = EntrypointCompatBindingSpec("GUILD_ID", "guild_id")
ENTRYPOINT_COMPAT_STREAM_RUNTIME = EntrypointCompatBindingSpec(
    "_STREAM_RUNTIME",
    "stream_runtime",
    "stream_runtime",
)
ENTRYPOINT_COMPAT_NOW_PLAYING_DEPS = EntrypointCompatBindingSpec(
    "_NOW_PLAYING_DEPS",
    "now_playing_deps",
    "now_playing_deps",
)
ENTRYPOINT_COMPAT_LEGACY = EntrypointCompatBindingSpec("_LEGACY", "legacy_runtime", "legacy")
ENTRYPOINT_COMPAT_APP = EntrypointCompatBindingSpec("_APP", "app_instance", "app")
ENTRYPOINT_COMPAT_RUNTIME_REGISTRATION = EntrypointCompatBindingSpec(
    "_RUNTIME_REGISTRATION",
    "runtime_registration",
    "runtime_registration",
)
ENTRYPOINT_COMPAT_LOCK_FILE = EntrypointCompatBindingSpec("LOCK_FILE", "lock_file", "lock_file")
ENTRYPOINT_COMPAT_SHUTDOWN_FLAG = EntrypointCompatBindingSpec(
    "_shutdown_flag",
    "shutdown_flag",
    "shutdown_flag",
)

ENTRYPOINT_COMPAT_RUNTIME_BINDINGS = (
    ENTRYPOINT_COMPAT_GUILD_ID,
    ENTRYPOINT_COMPAT_STREAM_RUNTIME,
    ENTRYPOINT_COMPAT_NOW_PLAYING_DEPS,
    ENTRYPOINT_COMPAT_LEGACY,
    ENTRYPOINT_COMPAT_APP,
    ENTRYPOINT_COMPAT_RUNTIME_REGISTRATION,
    ENTRYPOINT_COMPAT_LOCK_FILE,
    ENTRYPOINT_COMPAT_SHUTDOWN_FLAG,
)

ENTRYPOINT_COMPAT_VIEW_SPECS_BY_NAME = {
    spec.view_name: spec for spec in ENTRYPOINT_COMPAT_RUNTIME_BINDINGS
}
