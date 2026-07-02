import sys
import types
import unittest
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_support import install_discord_stubs

install_discord_stubs()

from robbo_obibok.app_context import ArchiveRegistryViews
from robbo_obibok.entrypoint_components import (
    EntrypointBootstrapBundle,
    EntrypointComponents,
    EntrypointMediaBundle,
    EntrypointRuntimeBundle,
    apply_entrypoint_components,
)


class EntrypointComponentsTests(unittest.TestCase):
    def test_apply_entrypoint_components_sets_archive_views_and_runtime_handles(self):
        archive_views = ArchiveRegistryViews(
            metadata_index=MappingProxyType({"track.sap": {"NAME": "Track"}}),
            modarchive_name_map=MappingProxyType({"mod": "Module"}),
            sid_durations=MappingProxyType({"track.sid": 120}),
            snes_metadata=MappingProxyType({"game.rsn": {"name": "Game"}}),
        )
        components = EntrypointComponents(
            bootstrap=EntrypointBootstrapBundle(
                bootstrapped_app="boot",
                app_context="context",
                app_state="state",
                archives="archives",
                app_services="services",
                archive_views=archive_views,
            ),
            runtime=EntrypointRuntimeBundle(
                service_facade="service",
                stream_runtime="stream-runtime",
                active_streams={"guild": "stream"},
                archive_runtime="archive-runtime",
            ),
            media=EntrypointMediaBundle(
                playback_assets="playback-assets",
                now_playing_deps="np",
                collections={"asma": "collection"},
                legacy="legacy",
            ),
        )
        state = types.SimpleNamespace()

        apply_entrypoint_components(state, components)

        self.assertIs(state.archive_views, archive_views)
        self.assertEqual(state.archives, "archives")
        self.assertEqual(state.service_facade, "service")
        self.assertEqual(state.collections, {"asma": "collection"})
