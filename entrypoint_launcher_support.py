"""Launcher support for entrypoint logging and root object setup."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import Callable

from entrypoint_bootstrap import EntrypointBootstrapBuilder, build_entrypoint_bootstrap
from entrypoint_bridge import EntrypointSupportStateProtocol
from entrypoint_guild import GuildScope
from entrypoint_resources import EntrypointResources
from runtime_io import SharedSessionRuntime


def configure_entrypoint_logger(root_dir: str, logger_name: str) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger
    log_file = os.path.join(root_dir, "bot_output.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(logging.StreamHandler())
    logger.propagate = False
    return logger


@dataclass(slots=True)
class EntrypointSupport:
    root_dir: str
    logger: logging.Logger
    session_runtime: SharedSessionRuntime
    boot: EntrypointBootstrapBuilder
    state: EntrypointSupportStateProtocol
    resources: EntrypointResources
    guild_scope: GuildScope


def build_entrypoint_support(
    *,
    module_path: str,
    logger_name: str,
    load_last_collection: Callable[[str], str | None],
    atomic_json_write: Callable[[str, object, object], None],
    state: EntrypointSupportStateProtocol | None = None,
    configure_logger: Callable[[str, str], logging.Logger] = configure_entrypoint_logger,
) -> EntrypointSupport:
    root_dir = os.path.dirname(os.path.abspath(module_path))
    logger = configure_logger(root_dir, logger_name)
    session_runtime = SharedSessionRuntime()
    boot = build_entrypoint_bootstrap(
        root_dir,
        logger,
        load_last_collection=load_last_collection,
        atomic_json_write=atomic_json_write,
    )
    if state is None:
        from entrypoint_state import EntrypointState  # type: ignore[unused-ignore]

        state = EntrypointState()
    resources = EntrypointResources(boot=boot, state=state, logger=logger)
    guild_scope = GuildScope()
    return EntrypointSupport(
        root_dir=root_dir,
        logger=logger,
        session_runtime=session_runtime,
        boot=boot,
        state=state,
        resources=resources,
        guild_scope=guild_scope,
    )
