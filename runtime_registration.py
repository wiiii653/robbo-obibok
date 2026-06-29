"""Compose the runtime and register commands/events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from bot_dependencies import PlaybackHandlerDependencies
from bot_runtime import BotRuntime
from bot_runtime import RuntimeConfig, RuntimeState
from runtime_composition import AppCompositionCallbacks, ComposedRuntime, compose_runtime


@dataclass(slots=True)
class RuntimeRegistration:
    composed: ComposedRuntime
    runtime: BotRuntime


def build_registered_runtime(
    *,
    config: RuntimeConfig,
    state: RuntimeState,
    app_callbacks: AppCompositionCallbacks,
    bot: Any,
    build_playback_handlers: Callable[[PlaybackHandlerDependencies], dict[str, Any]],
    register_core_events: Callable[..., None],
    register_playback_commands: Callable[..., None],
    register_library_commands: Callable[..., None],
    health_watchdog: Callable[..., Any],
    fetch_metadata_background: Callable[..., Any],
) -> RuntimeRegistration:
    composed = compose_runtime(
        config=config,
        state=state,
        app_callbacks=app_callbacks,
    )
    runtime = composed.runtime
    runtime.state.playback_handlers = build_playback_handlers(runtime.build_playback_handler_deps())
    register_core_events(
        bot,
        runtime.build_event_deps(),
        health_watchdog=health_watchdog,
        fetch_metadata_background=fetch_metadata_background,
    )
    register_playback_commands(bot, runtime.build_playback_command_deps())
    register_library_commands(bot, runtime.build_library_command_deps())
    return RuntimeRegistration(composed=composed, runtime=runtime)
