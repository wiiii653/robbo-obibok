"""Importable runtime facade for the robbo-obibok executable surface."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import TYPE_CHECKING, Callable, cast

from collection_catalog import (
    FLIP_ORDER as COLLECTION_FLIP_ORDER,
    FLIP_SEQ as COLLECTION_FLIP_SEQ,
)
from entrypoint_compat_policy import build_compat_policy
from entrypoint_module_bindings import (
    resolve_bound_entrypoint_module_attr,
    resolve_compat_entrypoint_module_attr,
)
import entrypoint_executable_assembly
import entrypoint_runner
import entrypoint_runtime_compat
from entrypoint_runtime_surface import (
    build_compat_runtime_surface,
    build_stable_runtime_surface,
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
        compat_policy=build_compat_policy(),
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


def _assembly_compat_policy():
    return _ensure_executable_assembly().compat_policy


def _assembly_launcher():
    return _ensure_executable_assembly().launcher


def _assembly_surface():
    return _ensure_executable_assembly().surface


def _stable_runtime_surface():
    return build_stable_runtime_surface(
        _assembly_bindings(),
        alias_source=_assembly_compat_bindings(),
    )


def _compat_runtime_surface():
    return build_compat_runtime_surface(_assembly_compat_bindings())


def initialize_runtime():
    global BOT_TOKEN
    assembly = _ensure_executable_assembly()
    app = _RUNTIME_HOLDER.initialize_runtime()
    BOT_TOKEN = assembly.launcher.runtime.bot_token()
    return app


def __getattr__(name: str):
    try:
        return entrypoint_runtime_compat.resolve_runtime_internal_attr(
            name,
            assembly_peek=lambda: _RUNTIME_HOLDER.assembly,
            bindings_getter=_assembly_bindings,
            compat_bindings_getter=_assembly_compat_bindings,
            compat_policy_getter=_assembly_compat_policy,
            launcher_getter=_assembly_launcher,
            deps_getter=lambda: _ensure_executable_assembly().deps,
            legacy_resolve_getter=lambda: _ensure_executable_assembly().legacy_resolve,
            surface_getter=_assembly_surface,
        )
    except AttributeError:
        if entrypoint_runtime_compat.is_runtime_internal_attr(name):
            raise
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
    entrypoint_runner.run_bot_entrypoint(
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
    stable_surface = build_stable_runtime_surface(
        assembly.bindings,
        alias_source=assembly.compat_bindings,
    )
    entrypoint_runner.run_bot_entrypoint(
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
