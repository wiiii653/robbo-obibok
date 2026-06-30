"""Volume control — pactl wrapper and validation policy.

Extracted from playback_commands.py volume command.
Routes pactl subprocess calls through a focused protocol.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Protocol


# ─── Protocol ────────────────────────────────────────────────────────────────

class VolumeController(Protocol):
    """Abstracts pactl volume operations."""

    def get_volume(self, sink_name: str) -> int | None:
        """Return current volume percentage (0-200) or None if unreadable."""
        ...

    def set_volume(self, sink_name: str, volume: int) -> None:
        """Set volume percentage (0-200)."""
        ...


# ─── Default implementation (pactl) ──────────────────────────────────────────

@dataclass(slots=True)
class PactlVolumeController:
    """VolumeController that calls pactl(1) via subprocess."""

    def get_volume(self, sink_name: str) -> int | None:
        r = subprocess.run(
            ["pactl", "get-sink-volume", sink_name],
            capture_output=True, text=True,
        )
        m = re.search(r"(\d+)%", r.stdout)
        if m:
            return int(m.group(1))
        return None

    def set_volume(self, sink_name: str, volume: int) -> None:
        subprocess.run(
            ["pactl", "set-sink-volume", sink_name, f"{volume}%"],
            capture_output=True,
        )


# ─── Policy ──────────────────────────────────────────────────────────────────

MIN_VOLUME = 0
MAX_VOLUME = 200


@dataclass(slots=True)
class VolumePolicy:
    """Pure validation logic for volume commands."""

    def clamp(self, value: int) -> int:
        return max(MIN_VOLUME, min(MAX_VOLUME, value))

    def is_valid(self, value: int) -> bool:
        return MIN_VOLUME <= value <= MAX_VOLUME

    def describe_range(self) -> str:
        return f"{MIN_VOLUME}–{MAX_VOLUME}"


class VolumeParseError(ValueError):
    """Input could not be parsed as an integer volume."""
