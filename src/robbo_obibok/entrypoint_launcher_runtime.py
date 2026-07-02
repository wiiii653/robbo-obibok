"""Runtime launcher components extracted from entrypoint_launcher_loader."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Any, Callable, Protocol, cast

from .archive_runtime import ArchiveRuntimeConfig
from .domain_config import AppConfig
from .entrypoint_bootstrap import (
    EntrypointBootstrapBuilder,
    EntrypointResources,
    build_entrypoint_bootstrap,
)
from .entrypoint_launcher_loader import _EntrypointModuleLoader
from .entrypoint_runtime_surface import (
    EntrypointRuntimeStateSurface,
    EntrypointRuntimeSurface,
    build_runtime_state_surface,
    build_runtime_surface,
)
from .entrypoint_state import EntrypointRuntimeStateProtocol, EntrypointStateProtocol
from .runtime_bootstrap import StartupEnvironment
from .runtime_io import SharedSessionRuntime

if TYPE_CHECKING:
    from .entrypoint_runtime import AppAssembly
    from .entrypoint_module import EntrypointModule, EntrypointModuleDeps


# ─── Inlined from entrypoint_launcher_state.py ──────────────────────────────


class RuntimeAppProtocol(Protocol):
    startup_env: StartupEnvironment


class RuntimeInitializerProtocol(Protocol):
    def initialize_runtime(self) -> "AppAssembly": ...


class BootstrapAppProtocol(Protocol):
    runtime_initializer: RuntimeInitializerProtocol


class RuntimeViewProtocol(Protocol):
    def state(self) -> EntrypointRuntimeStateProtocol: ...

    def app_config(self) -> AppConfig: ...

    def archive_runtime_config(self) -> ArchiveRuntimeConfig: ...


class EntrypointRuntimeLoaderProtocol(Protocol):
    def bootstrap_app(self) -> BootstrapAppProtocol: ...

    def runtime_state_surface(self) -> RuntimeViewProtocol: ...

    def lock_file(self) -> str: ...


@dataclass(slots=True)
class _EntrypointRuntimeStateAccess:
    state: EntrypointRuntimeStateProtocol
    app: BootstrapAppProtocol

    def ensure_initialized(self) -> "AppAssembly":
        if self.state.app is None:
            app = self.app.runtime_initializer.initialize_runtime()
            if self.state.app is None:
                self.state.app = app
        if self.state.app is not None:
            self.state.startup_env = self.state.app.startup_env
        return self.state.app


@dataclass(slots=True)
class _EntrypointRuntimeController:
    loader: EntrypointRuntimeLoaderProtocol

    def state_access(self) -> _EntrypointRuntimeStateAccess:
        return _EntrypointRuntimeStateAccess(
            state=self.loader.runtime_state_surface().state(),
            app=self.loader.bootstrap_app(),
        )

    def initialize_runtime(self) -> "AppAssembly":
        return self.state_access().ensure_initialized()

    async def graceful_shutdown(self) -> None:
        self.initialize_runtime()
        runtime = self.loader.runtime_state_surface().state().runtime
        assert runtime is not None
        await runtime.graceful_shutdown()

    def handle_signal(self, signum: int, frame: object) -> None:
        self.initialize_runtime()
        runtime = self.loader.runtime_state_surface().state().runtime
        assert runtime is not None
        runtime.handle_signal(signum, frame)

    def lock_file(self) -> str:
        return self.loader.lock_file()

    def bot_token(self) -> str:
        runtime_state = self.loader.runtime_state_surface()
        state = runtime_state.state()
        if state.startup_env is not None:
            return state.startup_env.bot_token
        return runtime_state.app_config().bot_token


# ─── Inlined from entrypoint_launcher_support.py ────────────────────────────


def _configure_entrypoint_logger(root_dir: str, logger_name: str) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger
    log_file = os.path.join(root_dir, "var", "bot_output.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
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
    state: EntrypointStateProtocol
    resources: EntrypointResources
    guild_scope: _GuildScope


def build_entrypoint_support(
    *,
    module_path: str,
    logger_name: str,
    load_last_collection: Callable[[str], str | None],
    atomic_json_write: Callable[[str, object, object], None],
    state: EntrypointStateProtocol | None = None,
    configure_logger: Callable[[str, str], logging.Logger] = _configure_entrypoint_logger,
) -> EntrypointSupport:
    root_dir = os.path.dirname(os.path.abspath(module_path))
    # module is in src/<package>/ or src/ directly — walk up past src/
    parent = os.path.dirname(root_dir)
    if os.path.basename(root_dir) in ("src", "src-"):
        root_dir = parent
    elif os.path.basename(parent) in ("src", "src-"):
        # module is in src/<package>/module.py — go up two levels
        root_dir = os.path.dirname(parent)
    logger = configure_logger(root_dir, logger_name)
    session_runtime = SharedSessionRuntime()
    boot = build_entrypoint_bootstrap(
        root_dir,
        logger,
        load_last_collection=load_last_collection,
        atomic_json_write=atomic_json_write,
    )
    if state is None:
        from .entrypoint_state import EntrypointState  # type: ignore[unused-ignore]

        state = EntrypointState()
    resources = EntrypointResources(boot=boot, state=state, logger=logger)
    guild_scope = _GuildScope()
    return EntrypointSupport(
        root_dir=root_dir,
        logger=logger,
        session_runtime=session_runtime,
        boot=boot,
        state=state,
        resources=resources,
        guild_scope=guild_scope,
    )


# ─── Inlined from entrypoint_launcher_support.py (GuildScope) ───────────────


@dataclass(slots=True)
class _GuildScope:
    override_guild_id: int | None = None

    def resolve(self, configured_guild_id: int | None) -> int | None:
        return configured_guild_id if self.override_guild_id is None else self.override_guild_id

    def set_override(self, guild_id: int | None) -> None:
        self.override_guild_id = guild_id

    def get_override(self) -> int | None:
        return self.override_guild_id


# ─── Inlined from entrypoint_launcher_config.py ─────────────────────────────


def build_entrypoint_launcher(
    *,
    module_path: str,
    logger_name: str,
    load_last_collection: Callable[[str], str | None],
    save_last_collection: Callable[[str, str], None],
    atomic_json_write: Callable[[str, Any, Any], None],
    command_prefix: Callable[[Any, Any], Any],
    deps: EntrypointModuleDeps,
    flip_order: list[str],
    flip_seq: list[str],
) -> LazyEntrypointLauncher:
    from .entrypoint_module import build_entrypoint_module

    module_builder = build_entrypoint_module

    def module_factory():
        return module_builder(
            module_path=module_path,
            logger_name=logger_name,
            load_last_collection=load_last_collection,
            save_last_collection=save_last_collection,
            atomic_json_write=atomic_json_write,
            command_prefix=command_prefix,
            deps=deps,
        )

    launcher = LazyEntrypointLauncher.create(
        module_factory=module_factory,
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    return launcher


# ─── Inlined from entrypoint_launcher_runtime.py ────────────────────────────


@dataclass(slots=True)
class LazyEntrypointLauncher:
    loader: _EntrypointModuleLoader
    runtime: _EntrypointRuntimeController

    @classmethod
    def create(
        cls,
        *,
        module_factory: Callable[[], "EntrypointModule"],
        flip_order: list[str],
        flip_seq: list[str],
    ) -> "LazyEntrypointLauncher":
        loader = _EntrypointModuleLoader(
            module_factory=module_factory,
            flip_order=flip_order,
            flip_seq=flip_seq,
        )
        return cls(
            loader=loader,
            runtime=_EntrypointRuntimeController(loader=loader),
        )


# ── backward-compat aliases for tests ──────────────────────────────────
EntrypointRuntimeController = _EntrypointRuntimeController  # noqa: F401
EntrypointRuntimeStateAccess = _EntrypointRuntimeStateAccess  # noqa: F401
