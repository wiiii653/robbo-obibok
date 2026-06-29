"""Bot creation and process startup helpers for the entrypoint."""

from __future__ import annotations

from typing import Callable

import discord
from discord.ext import commands


def build_default_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    return intents


def create_bot(command_prefix: str | Callable[..., object]) -> commands.Bot:
    bot = commands.Bot(command_prefix=command_prefix, intents=build_default_intents())
    bot.remove_command("help")
    return bot


def run_bot_entrypoint(
    *,
    initialize_runtime: Callable[[], object],
    install_runtime_hooks: Callable[..., None],
    handle_signal: Callable[[int, object], None],
    release_process_lock: Callable[[str], None],
    bot: commands.Bot,
    lock_file_getter: Callable[[], str],
    token_getter: Callable[[], str],
) -> None:
    initialize_runtime()
    install_runtime_hooks(
        handle_signal=handle_signal,
        release_lock=lambda: release_process_lock(lock_file_getter()),
    )
    try:
        bot.run(token_getter())
    finally:
        release_process_lock(lock_file_getter())
