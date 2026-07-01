"""Lazy module loader support for the entrypoint launcher."""

from __future__ import annotations

import os
from dataclasses import dataclass
import logging
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Any, Callable, Mapping, Protocol, cast
from entrypoint_runtime_surface import (
    EntrypointRuntimeStateSurface,
    EntrypointRuntimeSurface,
    build_runtime_state_surface,
    build_runtime_surface,
)

from domain_config import AppConfig
from archive_runtime import ArchiveRuntimeConfig
from bot_runtime import BotRuntime
from entrypoint_bootstrap import EntrypointBootstrapBuilder, build_entrypoint_bootstrap
from entrypoint_bootstrap import EntrypointResources
from entrypoint_state import EntrypointRuntimeStateProtocol, EntrypointStateProtocol
from runtime_bootstrap import StartupEnvironment
from runtime_io import SharedSessionRuntime

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from discord.ext import commands
    from entrypoint_app import EntrypointApp
    from entrypoint_module import EntrypointModule
    from entrypoint_runtime import AppAssembly

from entrypoint_module_bindings import (
    ENTRYPOINT_COMPAT_APP,
    ENTRYPOINT_COMPAT_GUILD_ID,
    ENTRYPOINT_COMPAT_LOCK_FILE,
    ENTRYPOINT_COMPAT_NOW_PLAYING_DEPS,
    ENTRYPOINT_COMPAT_RUNTIME_REGISTRATION,
    ENTRYPOINT_COMPAT_SHUTDOWN_FLAG,
    ENTRYPOINT_COMPAT_STREAM_RUNTIME,
    ENTRYPOINT_COMPAT_VIEW_SPECS_BY_NAME,
    EntrypointCompatBindingSpec,
)
from entrypoint_module_bindings import (
    EntrypointDirectExportSpec,
    ENTRYPOINT_DIRECT_EXPORT_SPECS_BY_NAME,
)
from entrypoint_module_bindings import ENTRYPOINT_EXPORT_GRAPH


class SessionRuntimeProtocol(Protocol):
    async def get_shared_session(self) -> ClientSession: ...
    async def close_shared_session(self) -> None: ...


class LegacyAudioResourcesProtocol(Protocol):
    def app_cfg(self) -> AppConfig: ...
    def archive_runtime_config(self) -> ArchiveRuntimeConfig: ...
    def setup_virtual_sink(self) -> None: ...
    def ensure_audacious(self) -> None: ...
    def setup_audacious_sid_config(self) -> None: ...
    def set_volume_for_collection(self, mode: str) -> None: ...
    def move_playback_to_sink(self) -> None: ...
    def audacious_play(self, filepath: str) -> bool: ...
    def audacious_stop(self) -> None: ...
    def audacious_song(self) -> str: ...
    def is_playing(self) -> bool: ...


class EntrypointSupportProtocol(Protocol):
    root_dir: str
    logger: logging.Logger
    session_runtime: SessionRuntimeProtocol
    boot: EntrypointBootstrapBuilder
    state: EntrypointStateProtocol
    resources: LegacyAudioResourcesProtocol
    guild_scope: GuildScope


class EntrypointModuleProtocol(Protocol):
    support: EntrypointSupportProtocol
    bot: commands.Bot
    app: EntrypointApp
    single_guild_check: Callable[[object], bool]
    guild_id_getter: Callable[[], int | None]
    guild_id_setter: Callable[[int | None], None]
    status_count_cache: dict[str, tuple[float, int | str]]
    exports: dict[str, object]


class EntrypointLegacyStateBindings:
    __slots__ = (
        "_SUPPORT", "_ROOT", "log", "_SESSION_RUNTIME", "BOOT",
        "_STATE", "_RESOURCES", "_GUILD_SCOPE",
        "modarchive_name_map", "snes_metadata",
        "_app_cfg", "_archive_runtime_config", "_status_count_cache",
        "_APP", "_FLIP_ORDER", "_FLIP_SEQ",
    )


class EntrypointLegacyControlBindings:
    __slots__ = (
        "bot", "single_guild_check",
        "get_shared_session", "close_shared_session",
        "setup_virtual_sink", "ensure_audacious", "setup_audacious_sid_config",
        "set_volume_for_collection", "move_playback_to_sink",
        "audacious_play", "audacious_stop", "audacious_song", "is_playing",
        "set_guild_id_override", "get_guild_id_override",
    )


class EntrypointLegacyBindings:
    __slots__ = ("state", "control", "exports")

    def __init__(self, state, control, exports):
        self.state = state
        self.control = control
        self.exports = exports

    def resolve(self, name: str) -> object:
        if hasattr(self.state, name):
            return getattr(self.state, name)
        if hasattr(self.control, name):
            return getattr(self.control, name)
        if name in self.exports:
            return self.exports[name]
        raise AttributeError(name)

    def get(self, key: str, default: object = None) -> object:
        try:
            return self.resolve(key)
        except AttributeError:
            return default


def build_entrypoint_legacy_bindings(
    *,
    entrypoint_module: EntrypointModuleProtocol,
    flip_order: list[str],
    flip_seq: list[str],
) -> EntrypointLegacyBindings:
    support = entrypoint_module.support
    resources = support.resources
    session_runtime = support.session_runtime
    state = EntrypointLegacyStateBindings()
    state._SUPPORT = support
    state._ROOT = support.root_dir
    state.log = support.logger
    state._SESSION_RUNTIME = session_runtime
    state.BOOT = support.boot
    state._STATE = support.state
    state._RESOURCES = resources
    state._GUILD_SCOPE = support.guild_scope
    state.modarchive_name_map = {}
    state.snes_metadata = {}
    state._app_cfg = resources.app_cfg
    state._archive_runtime_config = resources.archive_runtime_config
    state._status_count_cache = entrypoint_module.status_count_cache
    state._APP = entrypoint_module.app
    state._FLIP_ORDER = flip_order
    state._FLIP_SEQ = flip_seq
    control = EntrypointLegacyControlBindings()
    control.bot = entrypoint_module.bot
    control.single_guild_check = entrypoint_module.single_guild_check
    control.get_shared_session = session_runtime.get_shared_session
    control.close_shared_session = session_runtime.close_shared_session
    control.setup_virtual_sink = resources.setup_virtual_sink
    control.ensure_audacious = resources.ensure_audacious
    control.setup_audacious_sid_config = resources.setup_audacious_sid_config
    control.set_volume_for_collection = resources.set_volume_for_collection
    control.move_playback_to_sink = resources.move_playback_to_sink
    control.audacious_play = resources.audacious_play
    control.audacious_stop = resources.audacious_stop
    control.audacious_song = resources.audacious_song
    control.is_playing = resources.is_playing
    control.set_guild_id_override = entrypoint_module.guild_id_setter
    control.get_guild_id_override = entrypoint_module.guild_id_getter
    return EntrypointLegacyBindings(
        state=state,
        control=control,
        exports=entrypoint_module.exports,
    )


class CollectionLegacyProtocol(Protocol):
    skip_to_next: object
    cleanup_orphan_players: object
    stop_all_players: object
    auto_play_after_switch: object
    play_subsong: object


class CollectionServiceFacadeProtocol(Protocol):
    cleanup_subsong_temp_wavs: object
    switch_collection: object


class CollectionStateProtocol(Protocol):
    legacy: CollectionLegacyProtocol
    service_facade: CollectionServiceFacadeProtocol


class EntrypointCompatResolverProtocol(Protocol):
    def resolve(self, name: str) -> object: ...


class EntrypointModuleAppProtocol(Protocol):
    compat: EntrypointCompatResolverProtocol


class EntrypointLoadedModuleProtocol(Protocol):
    app: EntrypointModuleAppProtocol


class EntrypointLegacyExportsBindingsProtocol(Protocol):
    exports: Mapping[str, object]

    def resolve(self, name: str) -> object: ...


class LazyModuleAttr:
    def __init__(self, getter: Callable[[], object], attr_name: str):
        self._getter = getter
        self._attr_name = attr_name

    def _target(self) -> object:
        return getattr(self._getter(), self._attr_name)

    def __getattr__(self, name: str) -> object:
        return getattr(self._target(), name)

    def __call__(self, *args, **kwargs):
        target = cast(Callable[..., object], self._target())
        return target(*args, **kwargs)


@dataclass(frozen=True, slots=True)
class EntrypointCompatView:
    resolve_compat: Callable[[str], object]

    def resolve_spec(self, spec: EntrypointCompatBindingSpec) -> object:
        return self.resolve_compat(spec.export_name)

    def resolve_view(self, view_name: str) -> object:
        try:
            spec = ENTRYPOINT_COMPAT_VIEW_SPECS_BY_NAME[view_name]
        except KeyError as exc:
            raise AttributeError(view_name) from exc
        return self.resolve_spec(spec)


@dataclass(slots=True)
class EntrypointModuleLoader:
    module_factory: Callable[[], "EntrypointModule"]
    flip_order: list[str]
    flip_seq: list[str]
    module: "EntrypointModule | None" = None
    bindings: EntrypointLegacyBindings | None = None

    def ensure_module(self) -> "EntrypointModule":
        if self.module is None:
            self.module = self.module_factory()
            self.bindings = build_entrypoint_legacy_bindings(
                entrypoint_module=cast("EntrypointModuleProtocol", self.module),
                flip_order=self.flip_order,
                flip_seq=self.flip_seq,
            )
        return self.module

    def legacy_bindings(self) -> EntrypointLegacyBindings:
        self.ensure_module()
        assert self.bindings is not None
        return self.bindings

    def resolve_legacy(self, name: str) -> object:
        return self.legacy_bindings().resolve(name)

    def resolve_compat(self, name: str) -> object:
        return self.ensure_module().app.compat.resolve(name)

    def bootstrap_app(self) -> "BootstrapAppProtocol":
        return cast("BootstrapAppProtocol", self.legacy_bindings().state._APP)

    def compat(self) -> EntrypointCompatView:
        return EntrypointCompatView(resolve_compat=self.resolve_compat)

    def resolve_compat_view(self, view_name: str) -> object:
        return self.compat().resolve_view(view_name)

    def stable_runtime_surface(self) -> EntrypointRuntimeSurface:
        return build_runtime_surface(
            self.legacy_bindings(),
            resolver=self.resolve_legacy,
        )

    def runtime_state_surface(self) -> EntrypointRuntimeStateSurface:
        return build_runtime_state_surface(
            self.legacy_bindings(),
            resolver=self.resolve_legacy,
        )

    def collection_state(self) -> CollectionStateProtocol:
        return cast(CollectionStateProtocol, self.resolve_legacy("_STATE"))

    def collection_export(self, spec: str | EntrypointDirectExportSpec) -> Callable[..., object]:
        binding = self._direct_export_spec(spec)
        state = self.collection_state()
        target = state
        for attr_name in binding.attr_path:
            target = getattr(target, attr_name)
        return cast(Callable[..., object], target)

    def runtime_export(self, spec: str | EntrypointDirectExportSpec) -> Callable[..., object]:
        binding = self._direct_export_spec(spec)
        exports = self.legacy_bindings().exports
        try:
            return cast(Callable[..., object], exports[binding.export_name])
        except KeyError as exc:
            raise AttributeError(binding.export_name) from exc

    def resolve(self, name: str) -> object:
        try:
            return self.resolve_legacy(name)
        except AttributeError:
            if name not in ENTRYPOINT_EXPORT_GRAPH.compat_names:
                raise
            return self.resolve_compat(name)

    def proxy(self, attr_name: str) -> LazyModuleAttr:
        return LazyModuleAttr(self.ensure_module, attr_name)

    def lock_file(self) -> str:
        lock_file = self.runtime_state_surface().state().lock_file
        if lock_file is None:
            raise RuntimeError("runtime lock file is unavailable before initialization")
        return lock_file

    def _direct_export_spec(self, spec: str | EntrypointDirectExportSpec) -> EntrypointDirectExportSpec:
        if isinstance(spec, EntrypointDirectExportSpec):
            return spec
        try:
            return ENTRYPOINT_DIRECT_EXPORT_SPECS_BY_NAME[spec]
        except KeyError as exc:
            raise AttributeError(spec) from exc


def _build_compat_view_method(spec: EntrypointCompatBindingSpec) -> Callable[[EntrypointCompatView], object]:
    def _method(self: EntrypointCompatView) -> object:
        return self.resolve_spec(spec)

    return _method


def _build_loader_compat_method(spec: EntrypointCompatBindingSpec) -> Callable[[EntrypointModuleLoader], object]:
    def _method(self: EntrypointModuleLoader) -> object:
        return self.resolve_compat_view(spec.view_name)

    return _method


for _compat_spec in (
    ENTRYPOINT_COMPAT_GUILD_ID,
    ENTRYPOINT_COMPAT_STREAM_RUNTIME,
    ENTRYPOINT_COMPAT_NOW_PLAYING_DEPS,
    ENTRYPOINT_COMPAT_APP,
    ENTRYPOINT_COMPAT_RUNTIME_REGISTRATION,
    ENTRYPOINT_COMPAT_LOCK_FILE,
    ENTRYPOINT_COMPAT_SHUTDOWN_FLAG,
):
    setattr(EntrypointCompatView, _compat_spec.view_name, _build_compat_view_method(_compat_spec))
    setattr(EntrypointModuleLoader, _compat_spec.view_name, _build_loader_compat_method(_compat_spec))


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
class EntrypointRuntimeStateAccess:
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


# ─── Inlined from entrypoint_launcher_support.py ────────────────────────────


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
    state: EntrypointStateProtocol
    resources: EntrypointResources
    guild_scope: GuildScope


def build_entrypoint_support(
    *,
    module_path: str,
    logger_name: str,
    load_last_collection: Callable[[str], str | None],
    atomic_json_write: Callable[[str, object, object], None],
    state: EntrypointStateProtocol | None = None,
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


# ─── Inlined from entrypoint_launcher_support.py (GuildScope) ───────────────


@dataclass(slots=True)
class GuildScope:
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
    from entrypoint_module import build_entrypoint_module

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
    loader: EntrypointModuleLoader
    runtime: EntrypointRuntimeController

    @classmethod
    def create(
        cls,
        *,
        module_factory: Callable[[], "EntrypointModule"],
        flip_order: list[str],
        flip_seq: list[str],
    ) -> "LazyEntrypointLauncher":
        loader = EntrypointModuleLoader(
            module_factory=module_factory,
            flip_order=flip_order,
            flip_seq=flip_seq,
        )
        return cls(
            loader=loader,
            runtime=EntrypointRuntimeController(loader=loader),
        )
