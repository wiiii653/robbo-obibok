"""Typed collection configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(slots=True)
class CollectionSpec:
    label: str
    flip_tag: str
    load_func: Callable[[], list[str] | None]
    fallback_func: Callable[[], list[str] | None] | None
    already_msg: str | None
    load_msg: str | None
    error_msg: str | None
    ready_msg: str | None
    ready_empty_msg: str | None = None
    flip_load_msg: str | None = None
    flip_ready_msg: str | None = None
    flip_ready_empty_msg: str | None = None
    flip_fail_msg: str | None = None
    log_msg: str = ""
    log_args: bool = True
    after_hook: Callable[..., Awaitable[None]] | None = None
    allow_empty: bool = False
