"""Entrypoint command checks and decorators."""

from __future__ import annotations

from typing import Callable

from discord.ext import commands


def build_single_guild_check(*, guild_id_getter: Callable[[], int | None]):
    def single_guild_check(ctx: commands.Context) -> bool:
        """If a guild id is configured, only allow commands from that guild."""
        guild_id = guild_id_getter()
        if guild_id and ctx.guild and ctx.guild.id != guild_id:
            return False
        return True

    return single_guild_check


def mod_only():
    """Check if user has Manage Channels permission or is bot owner."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author == ctx.bot.owner:
            return True
        if hasattr(ctx.author, "guild_permissions") and ctx.author.guild_permissions.manage_channels:
            return True
        raise commands.MissingPermissions(["manage_channels"])

    return commands.check(predicate)
