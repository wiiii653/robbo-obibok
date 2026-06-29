"""Typed legacy compatibility bindings for the entrypoint module."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Callable, Protocol

from app_config import AppConfig
from archive_runtime import ArchiveRuntimeConfig
from entrypoint_bootstrap import EntrypointBootstrapBuilder
from entrypoint_bridge import EntrypointSupportStateProtocol
from entrypoint_guild import GuildScope
from entrypoint_resources import EntrypointResources

if TYPE_CHECKING:
    from discord.ext import commands
    from entrypoint_app import EntrypointApp


class SessionRuntimeProtocol(Protocol):
    async def get_shared_session(self) -> object:
        ...

    async def close_shared_session(self) -> None:
        ...


class LegacyAudioResourcesProtocol(Protocol):
    def app_cfg(self) -> AppConfig:
        ...

    def archive_runtime_config(self) -> ArchiveRuntimeConfig:
        ...

    def setup_virtual_sink(self) -> None:
        ...

    def ensure_audacious(self) -> None:
        ...

    def setup_audacious_sid_config(self) -> None:
        ...

    def set_volume_for_collection(self, mode: str) -> None:
        ...

    def move_playback_to_sink(self) -> None:
        ...

    def audacious_play(self, filepath: str) -> None:
        ...

    def audacious_stop(self) -> None:
        ...

    def audacious_song(self) -> str:
        ...

    def is_playing(self) -> bool:
        ...


class EntrypointSupportProtocol(Protocol):
    root_dir: str
    logger: logging.Logger
    session_runtime: SessionRuntimeProtocol
    boot: EntrypointBootstrapBuilder
    state: EntrypointSupportStateProtocol
    resources: LegacyAudioResourcesProtocol
    guild_scope: GuildScope


class EntrypointModuleProtocol(Protocol):
    support: EntrypointSupportProtocol
    bot: commands.Bot
    app: EntrypointApp
    single_guild_check: Callable[[object], bool]
    guild_id_getter: Callable[[], int | None]
    guild_id_setter: Callable[[int | None], None]
    status_count_cache: dict[str, tuple[float, int | str]]
    exports: dict[str, object]


@dataclass(slots=True)
class EntrypointLegacyStateBindings:
    _SUPPORT: EntrypointSupportProtocol
    _ROOT: str
    log: logging.Logger
    _SESSION_RUNTIME: SessionRuntimeProtocol
    BOOT: EntrypointBootstrapBuilder
    _STATE: EntrypointSupportStateProtocol
    _RESOURCES: EntrypointResources
    _GUILD_SCOPE: GuildScope
    modarchive_name_map: dict[str, str]
    snes_metadata: dict[str, dict[str, object]]
    _app_cfg: Callable[[], AppConfig]
    _archive_runtime_config: Callable[[], ArchiveRuntimeConfig]
    _status_count_cache: dict[str, tuple[float, int | str]]
    _APP: EntrypointApp
    _FLIP_ORDER: list[str]
    _FLIP_SEQ: list[str]


@dataclass(slots=True)
class EntrypointLegacyControlBindings:
    bot: commands.Bot
    single_guild_check: Callable[[object], bool]
    get_shared_session: Callable[[], object]
    close_shared_session: Callable[[], object]
    setup_virtual_sink: Callable[[], None]
    ensure_audacious: Callable[[], None]
    setup_audacious_sid_config: Callable[[], None]
    set_volume_for_collection: Callable[[str], None]
    move_playback_to_sink: Callable[[], None]
    audacious_play: Callable[[str], None]
    audacious_stop: Callable[[], None]
    audacious_song: Callable[[], str]
    is_playing: Callable[[], bool]
    set_guild_id_override: Callable[[int | None], None]
    get_guild_id_override: Callable[[], int | None]


@dataclass(slots=True)
class EntrypointLegacyBindings:
    state: EntrypointLegacyStateBindings
    control: EntrypointLegacyControlBindings
    exports: dict[str, object]

    def resolve(self, name: str) -> object:
        if hasattr(self.state, name):
            return getattr(self.state, name)
        if hasattr(self.control, name):
            return getattr(self.control, name)
        if name in self.exports:
            return self.exports[name]
        raise AttributeError(name)


def build_entrypoint_legacy_bindings(
    *,
    entrypoint_module: EntrypointModuleProtocol,
    flip_order: list[str],
    flip_seq: list[str],
) -> EntrypointLegacyBindings:
    support = entrypoint_module.support
    resources = support.resources
    session_runtime = support.session_runtime
    return EntrypointLegacyBindings(
        state=EntrypointLegacyStateBindings(
            _SUPPORT=support,
            _ROOT=support.root_dir,
            log=support.logger,
            _SESSION_RUNTIME=session_runtime,
            BOOT=support.boot,
            _STATE=support.state,
            _RESOURCES=resources,
            _GUILD_SCOPE=support.guild_scope,
            modarchive_name_map={},
            snes_metadata={},
            _app_cfg=resources.app_cfg,
            _archive_runtime_config=resources.archive_runtime_config,
            _status_count_cache=entrypoint_module.status_count_cache,
            _APP=entrypoint_module.app,
            _FLIP_ORDER=flip_order,
            _FLIP_SEQ=flip_seq,
        ),
        control=EntrypointLegacyControlBindings(
            bot=entrypoint_module.bot,
            single_guild_check=entrypoint_module.single_guild_check,
            get_shared_session=session_runtime.get_shared_session,
            close_shared_session=session_runtime.close_shared_session,
            setup_virtual_sink=resources.setup_virtual_sink,
            ensure_audacious=resources.ensure_audacious,
            setup_audacious_sid_config=resources.setup_audacious_sid_config,
            set_volume_for_collection=resources.set_volume_for_collection,
            move_playback_to_sink=resources.move_playback_to_sink,
            audacious_play=resources.audacious_play,
            audacious_stop=resources.audacious_stop,
            audacious_song=resources.audacious_song,
            is_playing=resources.is_playing,
            set_guild_id_override=entrypoint_module.guild_id_setter,
            get_guild_id_override=entrypoint_module.guild_id_getter,
        ),
        exports=entrypoint_module.exports,
    )
