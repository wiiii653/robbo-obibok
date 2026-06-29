"""Executable assembly helpers for the robbo-obibok entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from entrypoint_launcher_runtime import LazyEntrypointLauncher
from entrypoint_compat_policy import (
    EntrypointCompatPolicy,
    build_compat_policy,
    build_strict_compat_policy,
)
from entrypoint_launcher_config import build_entrypoint_launcher
from entrypoint_executable_providers import (
    EntrypointExecutableProviders,
    build_default_entrypoint_providers,
)
from entrypoint_legacy_facade import build_entrypoint_legacy_resolver
from entrypoint_module_bindings import (
    build_entrypoint_compat_module_bindings,
    build_entrypoint_stable_module_bindings,
)
from entrypoint_module_config import (
    build_entrypoint_module_deps,
)
from entrypoint_module import EntrypointModuleDeps
from entrypoint_startup import atomic_json_write, load_last_collection, save_last_collection
from entrypoint_surface_runtime import EntrypointModuleSurface
from entrypoint_surface_assembly import build_entrypoint_module_surface


@dataclass(frozen=True, slots=True)
class EntrypointExecutableAssembly:
    providers: EntrypointExecutableProviders
    deps: EntrypointModuleDeps
    launcher: LazyEntrypointLauncher
    legacy_resolve: Callable[[str], object]
    surface: EntrypointModuleSurface
    bindings: dict[str, object]
    compat_bindings: dict[str, object]
    compat_policy: EntrypointCompatPolicy


def build_default_entrypoint_module_deps(
    *,
    flip_order: list[str],
    flip_seq: list[str],
) -> EntrypointModuleDeps:
    _, deps = build_entrypoint_executable_dependencies(
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    return deps


def build_entrypoint_executable_dependencies(
    *,
    flip_order: list[str],
    flip_seq: list[str],
) -> tuple[EntrypointExecutableProviders, EntrypointModuleDeps]:
    providers = build_default_entrypoint_providers(
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    deps = build_entrypoint_module_deps(
        registration=providers.registration,
        playback_policy=providers.playback_policy,
        collection=providers.collection,
    )
    return providers, deps


def build_entrypoint_executable_assembly(
    *,
    module_path: str,
    logger_name: str,
    command_prefix: Callable[[object, object], object],
    flip_order: list[str],
    flip_seq: list[str],
    compat_policy: EntrypointCompatPolicy | None = None,
) -> EntrypointExecutableAssembly:
    compat_policy = build_compat_policy(template=compat_policy)
    providers, deps = build_entrypoint_executable_dependencies(
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    launcher = build_entrypoint_launcher(
        module_path=module_path,
        logger_name=logger_name,
        load_last_collection=load_last_collection,
        save_last_collection=save_last_collection,
        atomic_json_write=atomic_json_write,
        command_prefix=command_prefix,
        deps=deps,
        flip_order=flip_order,
        flip_seq=flip_seq,
    )
    legacy_resolve = build_entrypoint_legacy_resolver(loader=launcher.loader)
    surface = build_entrypoint_module_surface(
        launcher=launcher,
        resolve_fallback=legacy_resolve,
    )
    bindings = build_entrypoint_stable_module_bindings(surface)
    compat_bindings = build_entrypoint_compat_module_bindings(
        launcher.loader.legacy_bindings(),
        resolver=launcher.loader.resolve_legacy,
    )
    return EntrypointExecutableAssembly(
        providers=providers,
        deps=deps,
        launcher=launcher,
        legacy_resolve=legacy_resolve,
        surface=surface,
        bindings=bindings,
        compat_bindings=compat_bindings,
        compat_policy=compat_policy,
    )


def build_strict_entrypoint_executable_assembly(
    *,
    module_path: str,
    logger_name: str,
    command_prefix: Callable[[object, object], object],
    flip_order: list[str],
    flip_seq: list[str],
) -> EntrypointExecutableAssembly:
    return build_entrypoint_executable_assembly(
        module_path=module_path,
        logger_name=logger_name,
        command_prefix=command_prefix,
        flip_order=flip_order,
        flip_seq=flip_seq,
        compat_policy=build_strict_compat_policy(),
    )
