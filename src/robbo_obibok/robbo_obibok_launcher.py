#!/usr/bin/env python3
"""Shared process launcher for robbo-obibok entrypoint surfaces."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence

from .runtime_support import load_dotenv_file

ROOT = Path(__file__).resolve().parent.parent


def load_runtime_environment(
    *,
    root: Path = ROOT,
    env: MutableMapping[str, str] | None = None,
) -> MutableMapping[str, str]:
    runtime_env = os.environ if env is None else env
    load_dotenv_file(str(root / ".env"), env=runtime_env)
    if not runtime_env.get("DISCORD_BOT_TOKEN"):
        raise SystemExit("Set DISCORD_BOT_TOKEN in the environment or .env before starting the bot.")
    return runtime_env


def selected_entry_command(
    *,
    root: Path = ROOT,
    env: Mapping[str, str],
    entry_script: str | None = None,
) -> list[str]:
    resolved_entry_script = entry_script or selected_entry_script_from_env(env)
    return [str(root / "venv" / "bin" / "python3"), "-u", resolved_entry_script]


def exec_runtime_entrypoint(
    *,
    root: Path = ROOT,
    env: dict[str, str] | None = None,
    entry_script: str | None = None,
) -> None:
    runtime_env = load_runtime_environment(root=root, env=env)
    command = selected_entry_command(
        root=root,
        env=runtime_env,
        entry_script=entry_script,
    )
    os.execvpe(command[0], command, runtime_env)


def main(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    entry_script = args[0] if args else None
    exec_runtime_entrypoint(entry_script=entry_script)


DEFAULT_ENTRY_SCRIPT = "robbo-obibok.py"
STRICT_ENTRY_SCRIPT = "robbo-obibok-strict.py"


def selected_entry_script(*, strict: bool = False) -> str:
    if strict:
        return STRICT_ENTRY_SCRIPT
    return DEFAULT_ENTRY_SCRIPT


def selected_entry_script_from_env(env: Mapping[str, str]) -> str:
    return selected_entry_script(strict=env.get("ROBBO_STRICT_COMPAT") == "1")


if __name__ == "__main__":
    main()
