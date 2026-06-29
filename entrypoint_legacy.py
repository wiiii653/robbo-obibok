"""Lazy legacy binding construction."""

from __future__ import annotations

from typing import Callable

from app_state import PlaylistState
from legacy_runtime_bindings import LegacyRuntimeBindings
from runtime_protocols import ArchiveRuntimeProtocol, PlaybackAssetsProtocol, ServiceFacadeProtocol


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
