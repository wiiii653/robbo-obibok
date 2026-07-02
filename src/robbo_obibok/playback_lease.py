"""PlaybackLease — single-guild ownership of the shared Audacious process.

Only one Discord guild can own playback at a time.  This lease tracks who
holds it and provides ``acquire`` / ``release`` so commands can enforce the
rule: "someone else is already listening elsewhere — stop them first."
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PlaybackLease:
    """Track which guild currently owns the shared playback backend.

    Thread-safe enough for asyncio: all mutations happen from the event-loop
    thread in practice.
    """

    _owner_guild_id: int | None = None
    _owner_guild_name: str | None = None

    # ── Public API ──────────────────────────────────────────────────────────

    @property
    def is_held(self) -> bool:
        """Return True when some guild currently holds the lease."""
        return self._owner_guild_id is not None

    @property
    def owner_guild_id(self) -> int | None:
        return self._owner_guild_id

    @property
    def owner_guild_name(self) -> str | None:
        return self._owner_guild_name

    def acquire(self, guild_id: int, guild_name: str) -> bool:
        """Try to acquire the lease for *guild_id*.

        Returns True if the caller now holds the lease (either it was
        unclaimed or the caller already held it).  Returns False when
        another guild currently holds it.
        """
        if self._owner_guild_id is None or self._owner_guild_id == guild_id:
            self._owner_guild_id = guild_id
            self._owner_guild_name = guild_name
            return True
        return False

    def release(self) -> None:
        """Release the lease.  Safe to call even when nobody holds it."""
        self._owner_guild_id = None
        self._owner_guild_name = None
