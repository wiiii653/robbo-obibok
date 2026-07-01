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
        await tasks.shutdown()
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._logger = logger or logging.getLogger(__name__)

    def create(self, name: str, coro: Coroutine) -> asyncio.Task:
        """Create a tracked background task, replacing any existing task with the same name.

        The task is automatically cleaned up from the internal registry
        when it completes, fails, or is cancelled.
        """
        # Cancel existing task with the same name before creating a new one.
        self._cancel_and_pop(name)

        task = asyncio.create_task(coro)

        def _done_callback(fut: asyncio.Task) -> None:
            self._tasks.pop(name, None)
            if fut.cancelled():
                return
            exc = fut.exception()
            if exc is not None:
                self._logger.error("Task '%s' failed: %s", name, exc)

        task.add_done_callback(_done_callback)
        self._tasks[name] = task
        self._logger.debug("Created task '%s' (%d active)", name, len(self._tasks))
        return task

    def cancel(self, name: str) -> None:
        """Cancel a single tracked task by name."""
        task = self._cancel_and_pop(name)
        if task is not None:
            self._logger.debug("Cancelled task '%s'", name)

    async def shutdown(self) -> None:
        """Cancel every tracked task and await their completion.

        Used during graceful shutdown.
        """
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for t in tasks:
            if not t.done():
                t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self._logger.debug("Waited for %d cancelled task(s)", len(tasks))

    def _cancel_and_pop(self, name: str) -> asyncio.Task | None:
        """Cancel an existing task by name if it's still running and remove it from tracking."""
        task = self._tasks.pop(name, None)
        if task is not None and not task.done():
            task.cancel()
        return task

    @property
    def active_count(self) -> int:
        """Number of tasks currently being tracked."""
        return len(self._tasks)

    @property
    def task_names(self) -> list[str]:
        """Names of all tracked tasks."""
        return list(self._tasks.keys())
