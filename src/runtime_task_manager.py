"""Centralized asyncio task lifecycle management.

Tracks all background tasks (monitor, pre-download, health watchdog) and
provides a single cancellation point for graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Coroutine


class TaskManager:
    """Creates and tracks async background tasks.

    Usage::

        tasks = TaskManager(logger)
        task = tasks.create("monitor guild 42", coro)
        tasks.cancel_all()
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._logger = logger or logging.getLogger(__name__)

    def create(self, name: str, coro: Coroutine) -> asyncio.Task:
        """Create a tracked background task.

        The task is automatically cleaned up from the internal registry
        when it completes, fails, or is cancelled.
        """
        task = asyncio.create_task(coro)

        def _done_callback(fut: asyncio.Task) -> None:
            self._tasks.pop(name, None)
            exc = fut.exception()
            if exc and not fut.cancelled():
                self._logger.error("Task '%s' failed: %s", name, exc)

        task.add_done_callback(_done_callback)
        self._tasks[name] = task
        self._logger.debug("Created task '%s' (%d active)", name, len(self._tasks))
        return task

    def cancel(self, name: str) -> None:
        """Cancel a single tracked task by name."""
        task = self._tasks.pop(name, None)
        if task and not task.done():
            task.cancel()
            self._logger.debug("Cancelled task '%s'", name)

    def cancel_all(self) -> None:
        """Cancel every tracked task (used during shutdown)."""
        count = len(self._tasks)
        for name, task in self._tasks.items():
            if not task.done():
                task.cancel()
        self._tasks.clear()
        if count:
            self._logger.debug("Cancelled %d tracked task(s)", count)

    @property
    def active_count(self) -> int:
        """Number of tasks currently being tracked."""
        return len(self._tasks)

    @property
    def task_names(self) -> list[str]:
        """Names of all tracked tasks."""
        return list(self._tasks.keys())
