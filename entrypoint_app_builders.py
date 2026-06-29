"""Non-runtime builders for entrypoint app assembly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from entrypoint_bridge import EntrypointComponentAccess

if TYPE_CHECKING:
    from entrypoint_launcher_support import EntrypointSupport

def build_entrypoint_component_access(
    *,
    support: EntrypointSupport,
    ensure_components: Callable[[], None],
) -> EntrypointComponentAccess:
    return EntrypointComponentAccess(
        state=support.state,
        ensure_components=ensure_components,
    )
