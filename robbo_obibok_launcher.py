#!/usr/bin/env python3
"""Shared process launcher for robbo-obibok entrypoint surfaces."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping, Sequence

from robbo_obibok_launch import selected_entry_script_from_env
from runtime_support import load_dotenv_file

ROOT = Path(__file__).resolve().parent


def load_runtime_environment(
    *,
    root: Path = ROOT,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    runtime_env = os.environ if env is None else env
    load_dotenv_file(str(root / ".env"))
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


if __name__ == "__main__":
    main()
