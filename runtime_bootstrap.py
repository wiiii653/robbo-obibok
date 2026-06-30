"""Runtime/bootstrap orchestration helpers for the bot entrypoint."""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import sys
from typing import Awaitable, Callable, Sequence


async def run_startup_steps(
    steps: list[tuple[str, Callable[[], None]]],
    *,
    logger,
) -> None:
    """Run blocking startup steps in the executor with consistent logging."""
    for step_name, func in steps:
        try:
            await asyncio.get_event_loop().run_in_executor(None, func)
        except Exception as exc:
            logger.error("%s failed: %s", step_name, exc)


def log_preloaded_cache(label: str, tracks: list[str] | None, *, logger) -> None:
    """Log cache preload counts when available."""
    if tracks:
        logger.info("%s local: %d tracks preloaded", label, len(tracks))


def schedule_background_tasks(
    task_factories: Sequence[Callable[[], Awaitable[object]]],
    *,
    loop,
) -> None:
    """Create background tasks from factory callables."""
    for factory in task_factories:
        loop.create_task(factory())


def acquire_process_lock(lock_file: str, process_name: str) -> int:
    """Acquire a PID lock for the current process or exit if a matching process exists."""
    my_pid = os.getpid()
    try:
        if os.path.exists(lock_file):
            with open(lock_file, encoding="utf-8") as handle:
                old_pid_str = handle.read().strip()
            if old_pid_str:
                old_pid = int(old_pid_str)
                try:
                    os.kill(old_pid, 0)
                    with open(f"/proc/{old_pid}/cmdline", "rb") as cmdline_handle:
                        cmd = cmdline_handle.read().decode("utf-8", errors="replace")
                    if process_name in cmd:
                        print(f"PID {old_pid} already running. Stop it first or wait until it exits.")
                        sys.exit(1)
                except (OSError, ProcessLookupError):
                    pass
    except Exception as exc:
        print(f"Lock warning ({exc}), continuing startup...")

    with open(lock_file, "w", encoding="utf-8") as handle:
        handle.write(str(my_pid))
    return my_pid


def release_process_lock(lock_file: str) -> None:
    """Release the PID lock if owned by the current process."""
    try:
        if os.path.exists(lock_file):
            with open(lock_file, encoding="utf-8") as handle:
                lock_pid = handle.read().strip()
            if lock_pid == str(os.getpid()):
                os.unlink(lock_file)
    except Exception:
        pass


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
