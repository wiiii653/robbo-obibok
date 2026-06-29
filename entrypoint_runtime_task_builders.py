"""Task-oriented runtime builders for entrypoint app assembly."""

from __future__ import annotations

from typing import Any, Callable

from entrypoint_callback_groups import EntrypointRawCallbacks
from entrypoint_facade import EntrypointFacade
from entrypoint_glue import EntrypointGlue
from entrypoint_runtime_tasks import EntrypointRuntimeTasks


def build_entrypoint_runtime_tasks(
    *,
    bot: Any,
    support: Any,
    app_cfg_getter: Callable[[], Any],
    component_access: Any,
    raw_callbacks: EntrypointRawCallbacks,
    compute_timeout_seconds: Callable[..., int],
    is_gme_format_path: Callable[[str], bool],
    should_advance_after_stop: Callable[..., tuple[bool, float | None]],
    should_confirm_output_drop: Callable[..., tuple[bool, float | None]],
    should_disconnect_for_empty_channel: Callable[..., tuple[bool, float | None]],
    should_force_timeout_stop: Callable[[int, int], bool],
    should_start_predownload: Callable[..., bool],
    facade: EntrypointFacade,
    glue: EntrypointGlue,
) -> EntrypointRuntimeTasks:
    return EntrypointRuntimeTasks(
        bot=bot,
        state=support.state,
        logger=support.logger,
        app_cfg_getter=app_cfg_getter,
        components=component_access,
        audacious_song=raw_callbacks.playback.audacious_song,
        audacious_stop=raw_callbacks.playback.audacious_stop,
        compute_timeout_seconds=compute_timeout_seconds,
        is_gme_format_path=is_gme_format_path,
        is_playing=raw_callbacks.playback.is_playing,
        pre_download_next=glue.pre_download_next,
        should_advance_after_stop=should_advance_after_stop,
        should_confirm_output_drop=should_confirm_output_drop,
        should_disconnect_for_empty_channel=should_disconnect_for_empty_channel,
        should_force_timeout_stop=should_force_timeout_stop,
        should_start_predownload=should_start_predownload,
        skip_to_next=facade.skip_to_next,
        stop_all_players=facade.stop_all_players,
        ensure_audacious=raw_callbacks.bootstrap.ensure_audacious,
        setup_virtual_sink=raw_callbacks.bootstrap.setup_virtual_sink,
    )
