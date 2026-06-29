import os
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_support import install_discord_stubs


install_discord_stubs()

from collection_catalog import FLIP_ORDER, FLIP_SEQ
from entrypoint_compat_policy import build_compat_policy
from entrypoint_executable_assembly import build_entrypoint_executable_assembly


async def _command_prefix(_bot, _message):
    return "!"


@dataclass(frozen=True, slots=True)
class LiveRuntimeBundle:
    assembly: object
    bindings: dict[str, object]
    state: object
    runtime: object
    app_config: object
    archive_runtime_config: object


def build_live_runtime_bundle():
    os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
    install_discord_stubs()
    with (
        patch("runtime_support.validate_runtime_dependencies", lambda required_tools=None: None),
        patch("entrypoint_executable_providers.validate_runtime_dependencies", lambda required_tools=None: None),
    ):
        assembly = build_entrypoint_executable_assembly(
            module_path=str(ROOT / "robbo-obibok.py"),
            logger_name="robbo-obibok",
            command_prefix=_command_prefix,
            flip_order=FLIP_ORDER,
            flip_seq=FLIP_SEQ,
            compat_policy=build_compat_policy(),
        )
        assembly.launcher.runtime.initialize_runtime()
    state_surface = assembly.launcher.loader.runtime_state_surface()
    bindings = assembly.bindings
    state = state_surface.state()
    return LiveRuntimeBundle(
        assembly=assembly,
        bindings=bindings,
        state=state,
        runtime=state.runtime,
        app_config=state_surface.app_config(),
        archive_runtime_config=state_surface.archive_runtime_config(),
    )


_BUNDLE = None


def get_live_runtime_bundle():
    global _BUNDLE
    if _BUNDLE is None:
        _BUNDLE = build_live_runtime_bundle()
    return _BUNDLE


def load_live_runtime_bundle():
    return get_live_runtime_bundle()
