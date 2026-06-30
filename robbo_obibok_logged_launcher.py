#!/usr/bin/env python3
"""Logging-oriented launcher module for robbo-obibok."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import MutableMapping

from robbo_obibok_launcher import load_runtime_environment, selected_entry_command
from robbo_obibok_launch import selected_entry_script_from_env

ROOT = Path(__file__).resolve().parent


def build_logged_launch_command(
    *,
    root: Path = ROOT,
    env: dict[str, str] | None = None,
) -> tuple[MutableMapping[str, str], list[str]]:
    runtime_env = load_runtime_environment(root=root, env=os.environ if env is None else env)
    entry_script = selected_entry_script_from_env(runtime_env)
    command = selected_entry_command(root=root, env=runtime_env, entry_script=entry_script)
    return runtime_env, command


def run_logged_bot(
    *,
    root: Path = ROOT,
    env: dict[str, str] | None = None,
) -> int:
    _runtime_env, command = build_logged_launch_command(root=root, env=env)
    log_path = root / "bot_output.log"
    with log_path.open("a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            command,
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )

        print(f"STARTED PID={proc.pid}")
        sys.stdout.flush()

        try:
            return proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            return 130


def main() -> None:
    raise SystemExit(run_logged_bot())


if __name__ == "__main__":
    main()
