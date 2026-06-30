"""Runtime state access for the entrypoint launcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app_config import AppConfig
from archive_runtime import ArchiveRuntimeConfig
from runtime_bootstrap import StartupEnvironment
from bot_runtime import BotRuntime
from entrypoint_state import EntrypointRuntimeStateProtocol

if TYPE_CHECKING:
    from entrypoint_runtime import AppAssembly


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
class EntrypointRuntimeStateAccess:
    state: EntrypointRuntimeStateProtocol
    app: BootstrapAppProtocol

    def ensure_initialized(self) -> "AppAssembly":
        if self.state.app is None:
            app = self.app.runtime_initializer.initialize_runtime()
            if hasattr(self.state, "cache_initialized_app"):
                return self.state.cache_initialized_app(app)
            self.state.app = app
        self.state.startup_env = self.state.app.startup_env
        return self.state.app


@dataclass(slots=True)
class EntrypointRuntimeController:
    loader: EntrypointRuntimeLoaderProtocol

    def state_access(self) -> EntrypointRuntimeStateAccess:
        return EntrypointRuntimeStateAccess(
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
