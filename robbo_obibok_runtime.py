"""Importable runtime facade for the robbo-obibok executable surface."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import TYPE_CHECKING, Callable, cast

from collection_catalog import (
    FLIP_ORDER as COLLECTION_FLIP_ORDER,
    FLIP_SEQ as COLLECTION_FLIP_SEQ,
)
from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES,
    resolve_bound_entrypoint_module_attr,
    resolve_compat_entrypoint_module_attr,
)
import entrypoint_executable_assembly
from entrypoint_app import run_bot_entrypoint
from entrypoint_runtime_surface import (
    build_runtime_surface,
)
import runtime_bootstrap

if TYPE_CHECKING:
    from discord.ext import commands
    from entrypoint_runtime import AppAssembly

BOT_TOKEN = ""
_ASSEMBLY = None


async def _command_prefix(_bot, _message):
    return await _ensure_executable_assembly().launcher.loader.ensure_module().support.resources.command_prefix(
        _bot,
        _message,
    )


def _build_executable_assembly():
    return entrypoint_executable_assembly.build_entrypoint_executable_assembly(
        module_path=__file__,
        logger_name="robbo-obibok",
        command_prefix=_command_prefix,
        flip_order=COLLECTION_FLIP_ORDER,
        flip_seq=COLLECTION_FLIP_SEQ,
    )


def _build_strict_executable_assembly():
    return entrypoint_executable_assembly.build_strict_entrypoint_executable_assembly(
        module_path=__file__,
        logger_name="robbo-obibok",
        command_prefix=_command_prefix,
        flip_order=COLLECTION_FLIP_ORDER,
        flip_seq=COLLECTION_FLIP_SEQ,
    )


@dataclass(slots=True)
class ExecutableRuntimeHolder:
    assembly_builder: Callable[[], entrypoint_executable_assembly.EntrypointExecutableAssembly]
    assembly: entrypoint_executable_assembly.EntrypointExecutableAssembly | None = None
    app: "AppAssembly | None" = None

    def ensure_assembly(self):
        if self.assembly is None:
            self.assembly = self.assembly_builder()
        return self.assembly

    def initialize_runtime(self):
        if self.app is None:
            self.app = self.ensure_assembly().launcher.runtime.initialize_runtime()
        return self.app


_RUNTIME_HOLDER = ExecutableRuntimeHolder(assembly_builder=_build_executable_assembly)


def _ensure_executable_assembly():
    global _ASSEMBLY
    assembly = _RUNTIME_HOLDER.ensure_assembly()
    _ASSEMBLY = assembly
    return assembly


def _assembly_bindings():
    return _ensure_executable_assembly().bindings


def _assembly_compat_bindings():
    return _ensure_executable_assembly().compat_bindings


def _assembly_surface():
    return _ensure_executable_assembly().surface


def _stable_runtime_surface():
    return build_runtime_surface(
        _assembly_bindings(),
        alias_source=_assembly_compat_bindings(),
    )


def initialize_runtime():
    global BOT_TOKEN
    assembly = _ensure_executable_assembly()
    app = _RUNTIME_HOLDER.initialize_runtime()
    BOT_TOKEN = assembly.launcher.runtime.bot_token()
    return app


def __getattr__(name: str):
    _stable_attrs = {
        "_ASSEMBLY": lambda: _RUNTIME_HOLDER.assembly,
        "_BINDINGS": _assembly_bindings,
        "_COMPAT_BINDINGS": _assembly_compat_bindings,
    }
    if name in _stable_attrs:
        return _stable_attrs[name]()
    if name in ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES:
        raise AttributeError(name)
    if name in globals():
        return globals()[name]
    stable_surface = _stable_runtime_surface()
    try:
        return stable_surface.resolve(name)
    except AttributeError:
        try:
            return stable_surface.resolve_alias(name)
        except AttributeError:
            try:
                return resolve_bound_entrypoint_module_attr(
                    name,
                    bindings=_assembly_bindings(),
                )
            except AttributeError:
                return resolve_compat_entrypoint_module_attr(
                    name,
                    fallback_resolver=_assembly_surface().resolve,
                )


async def graceful_shutdown():
    await _ensure_executable_assembly().launcher.runtime.graceful_shutdown()


def handle_signal(signum, frame):
    _ensure_executable_assembly().launcher.runtime.handle_signal(signum, frame)


def main():
    assembly = _ensure_executable_assembly()
    run_bot_entrypoint(
        initialize_runtime=initialize_runtime,
        install_runtime_hooks=runtime_bootstrap.install_runtime_hooks,
        handle_signal=handle_signal,
        release_process_lock=runtime_bootstrap.release_process_lock,
        bot=cast("commands.Bot", _stable_runtime_surface().resolve("bot")),
        lock_file_getter=assembly.launcher.runtime.lock_file,
        token_getter=assembly.launcher.runtime.bot_token,
    )


def main_strict():
    holder = ExecutableRuntimeHolder(assembly_builder=_build_strict_executable_assembly)

    def ensure_assembly():
        return holder.ensure_assembly()

    def initialize_runtime_strict():
        assembly = ensure_assembly()
        app = holder.initialize_runtime()
        global BOT_TOKEN
        BOT_TOKEN = assembly.launcher.runtime.bot_token()
        return app

    def handle_signal_strict(signum, frame):
        ensure_assembly().launcher.runtime.handle_signal(signum, frame)

    assembly = ensure_assembly()
    stable_surface = build_runtime_surface(
        assembly.bindings,
        alias_source=assembly.compat_bindings,
    )
    run_bot_entrypoint(
        initialize_runtime=initialize_runtime_strict,
        install_runtime_hooks=runtime_bootstrap.install_runtime_hooks,
        handle_signal=handle_signal_strict,
        release_process_lock=runtime_bootstrap.release_process_lock,
        bot=cast("commands.Bot", stable_surface.resolve("bot")),
        lock_file_getter=assembly.launcher.runtime.lock_file,
        token_getter=assembly.launcher.runtime.bot_token,
    )


def selected_main():
    if os.environ.get("ROBBO_STRICT_COMPAT") == "1":
        return main_strict
    return main
