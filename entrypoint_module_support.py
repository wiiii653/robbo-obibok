"""Support/bootstrap helpers for entrypoint module assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from app_state import PlaylistState
from entrypoint_checks import build_single_guild_check
from entrypoint_launcher_support import EntrypointSupport, build_entrypoint_support
from entrypoint_runner import create_bot

if TYPE_CHECKING:
    from discord.ext import commands


@dataclass(slots=True)
class EntrypointModuleBootstrap:
    support: EntrypointSupport
    bot: commands.Bot
    single_guild_check: Callable[[object], bool]
    guild_id_getter: Callable[[], int | None]
    guild_id_setter: Callable[[int | None], None]
    status_count_cache: dict[str, tuple[float, int | str]]
    clear_predownload_state: Callable[[PlaylistState], None]


def build_entrypoint_module_bootstrap(
    *,
    module_path: str,
    logger_name: str,
    load_last_collection: Callable[[str], str | None],
    atomic_json_write: Callable[[str, object, object], None],
    command_prefix: Callable[[object, object], object],
) -> EntrypointModuleBootstrap:
    support = build_entrypoint_support(
        module_path=module_path,
        logger_name=logger_name,
        load_last_collection=load_last_collection,
        atomic_json_write=atomic_json_write,
    )
    bot = create_bot(command_prefix)
    single_guild_check = build_single_guild_check(
        guild_id_getter=lambda: support.guild_scope.resolve(support.resources.app_cfg().guild_id),
    )
    bot.check(single_guild_check)

    def set_guild_id_override(guild_id: int | None) -> None:
        support.guild_scope.set_override(guild_id)

    def get_guild_id_override() -> int | None:
        return support.guild_scope.get_override()

    def clear_predownload_state(state: PlaylistState, *, keep_file: bool = False) -> None:
        from entrypoint_helpers import clear_predownload_state as clear_state

        clear_state(state, keep_file=keep_file)

    return EntrypointModuleBootstrap(
        support=support,
        bot=bot,
        single_guild_check=single_guild_check,
        guild_id_getter=get_guild_id_override,
        guild_id_setter=set_guild_id_override,
        status_count_cache={},
        clear_predownload_state=clear_predownload_state,
    )
