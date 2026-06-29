"""Guild scoping helpers for the entrypoint."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GuildScope:
    override_guild_id: int | None = None

    def resolve(self, configured_guild_id: int | None) -> int | None:
        return configured_guild_id if self.override_guild_id is None else self.override_guild_id

    def set_override(self, guild_id: int | None) -> None:
        self.override_guild_id = guild_id

    def get_override(self) -> int | None:
        return self.override_guild_id
