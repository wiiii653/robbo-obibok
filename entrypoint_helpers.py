"""Small helper functions used by the bot entrypoint."""

from __future__ import annotations

import os
from hashlib import sha1
from typing import Any


def clear_predownload_state(state: Any, *, keep_file: bool = False) -> None:
    """Reset pre-download bookkeeping and cancel in-flight work when needed."""
    task = state.pre_download_task
    state.set_predownload_task(None)
    if task and not task.done():
        task.cancel()
    if not keep_file and state.pre_downloaded and os.path.exists(state.pre_downloaded):
        try:
            os.remove(state.pre_downloaded)
        except OSError:
            pass
    state.clear_predownload()


def place_track_in_queue(queue: list[str], url: str) -> tuple[list[str], int]:
    """Return queue/index with the target track selected, inserting if needed."""
    positioned_queue = list(queue)
    try:
        index = positioned_queue.index(url)
    except ValueError:
        positioned_queue.insert(0, url)
        index = 0
    return positioned_queue, index


def build_temp_path(temp_dir: str, url: str) -> str:
    """Create a collision-resistant temp path for a downloaded track."""
    filename = url.split("/")[-1] or "track.bin"
    digest = sha1(url.encode("utf-8")).hexdigest()[:12]
    return os.path.join(temp_dir, f"{digest}_{filename}")
