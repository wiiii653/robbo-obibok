"""Launch target helpers for robbo-obibok launcher surfaces."""

from __future__ import annotations

from typing import Mapping

DEFAULT_ENTRY_SCRIPT = "robbo-obibok.py"
STRICT_ENTRY_SCRIPT = "robbo-obibok-strict.py"


def selected_entry_script(*, strict: bool = False) -> str:
    if strict:
        return STRICT_ENTRY_SCRIPT
    return DEFAULT_ENTRY_SCRIPT


def selected_entry_script_from_env(env: Mapping[str, str]) -> str:
    return selected_entry_script(strict=env.get("ROBBO_STRICT_COMPAT") == "1")
