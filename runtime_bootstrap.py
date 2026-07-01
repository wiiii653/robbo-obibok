"""Runtime/bootstrap orchestration helpers for the bot entrypoint."""

from __future__ import annotations

import asyncio
import fcntl
import os
import shutil
import signal
from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence


_LOCK_DESCRIPTORS: dict[str, int] = {}


async def run_startup_steps(
    steps: list[tuple[str, Callable[[], None]]],
    *,
    logger,
) -> None:
    """Run blocking startup steps in the executor with consistent logging."""
    for step_name, func in steps:
        try:
            await asyncio.get_running_loop().run_in_executor(None, func)
        except Exception as exc:
            logger.error("%s failed: %s", step_name, exc)


def log_preloaded_cache(label: str, tracks: list[str] | None, *, logger) -> None:
    """Log cache preload counts when available."""
    if tracks:
        logger.info("%s local: %d tracks preloaded", label, len(tracks))


def schedule_background_tasks(
    task_factories: Sequence[Callable[[], Awaitable[object]]],
) -> None:
    """Create background tasks from factory callables.

    Relies on a running event loop — works when called from within
    an async context (e.g. on_ready).
    """
    loop = asyncio.get_running_loop()
    for factory in task_factories:
        asyncio.ensure_future(factory(), loop=loop)


def acquire_process_lock(lock_file: str, process_name: str) -> int:
    """Acquire and retain an OS-backed process lock."""
    my_pid = os.getpid()
    descriptor = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        try:
            owner = os.read(descriptor, 64).decode("ascii", errors="replace").strip()
        finally:
            os.close(descriptor)
        owner_message = f"PID {owner}" if owner else process_name
        raise SystemExit(f"{owner_message} already running. Stop it first or wait until it exits.")
    os.ftruncate(descriptor, 0)
    os.write(descriptor, str(my_pid).encode("ascii"))
    os.fsync(descriptor)
    _LOCK_DESCRIPTORS[lock_file] = descriptor
    return my_pid


def release_process_lock(lock_file: str) -> None:
    """Release the PID lock if owned by the current process."""
    descriptor = _LOCK_DESCRIPTORS.pop(lock_file, None)
    try:
        if descriptor is not None:
            os.unlink(lock_file)
    except Exception:
        pass
    finally:
        if descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def cleanup_temp_dir(temp_dir: str, *, logger) -> None:
    """Remove the working temp directory."""
    try:
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("Cleaned up temp dir: %s", temp_dir)
    except Exception as exc:
        logger.warning("Temp cleanup failed: %s", exc)


def install_runtime_hooks(
    *,
    handle_signal: Callable[[int, object], None],
    release_lock: Callable[[], None],
) -> None:
    """Install signal and exit handlers for clean runtime shutdown."""
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    ate = __import__("atexit")
    ate.register(release_lock)


@dataclass(slots=True)
class StartupEnvironment:
    bot_token: str
    lock_file: str
    shutdown_flag: asyncio.Event


def initialize_startup_environment(
    *,
    bot_token: str | None,
    root_dir: str,
    lock_file: str | None = None,
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

    if lock_file is None:
        lock_file = os.path.join(root_dir, "obibok.pid")
    acquire_process_lock(lock_file, process_name)
    return StartupEnvironment(
        bot_token=bot_token,
        lock_file=lock_file,
        shutdown_flag=asyncio.Event(),
    )
