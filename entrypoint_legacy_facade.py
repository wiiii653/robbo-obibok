"""Legacy module-surface fallback resolver for the entrypoint launcher."""

from __future__ import annotations

from typing import Callable, Protocol

from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXPORT_GRAPH,
)


class EntrypointLegacyResolverLoaderProtocol(Protocol):
    def resolve_legacy(self, name: str) -> object: ...

    def resolve(self, name: str) -> object: ...


def build_entrypoint_legacy_resolver(
    *,
    loader: EntrypointLegacyResolverLoaderProtocol,
) -> Callable[[str], object]:
    def resolve(name: str) -> object:
        if name in {
            "bot",
            "get_guild_id_override",
            "set_guild_id_override",
        } | ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES:
            return loader.resolve_legacy(name)
        if name not in ENTRYPOINT_EXPORT_GRAPH.compat_names:
            raise AttributeError(name)
        return loader.resolve(name)

    return resolve
