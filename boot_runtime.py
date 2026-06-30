"""Startup environment helpers for the bot entrypoint."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class StartupEnvironment:
    bot_token: str
    lock_file: str
    shutdown_flag: asyncio.Event


def initialize_startup_environment(
    *,
    bot_token: str | None,
    root_dir: str,
    validate_runtime_dependencies: Callable[[], None],
    acquire_process_lock: Callable[[str, str], int],
    process_name: str,
) -> StartupEnvironment:
    if not bot_token:
        raise SystemExit("Set DISCORD_BOT_TOKEN environment variable.")

    try:
        validate_runtime_dependencies()
    except RuntimeError as exc:
        raise SystemExit(str(exc))

    lock_file = os.path.join(root_dir, "obibok.pid")
    acquire_process_lock(lock_file, process_name)
    return StartupEnvironment(
        bot_token=bot_token,
        lock_file=lock_file,
        shutdown_flag=asyncio.Event(),
    )
