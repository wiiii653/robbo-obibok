import sys
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_app import EntrypointComponentAccess, EntrypointComponents


class EntrypointBridgeTests(unittest.TestCase):
    def test_component_access_requires_components_and_returns_typed_bundle(self):
        calls = []
        state = types.SimpleNamespace(
            app_services="app-services",
            service_facade="service-facade",
            stream_runtime="stream-runtime",
            archive_runtime="archive-runtime",
            playback_assets="playback-assets",
            now_playing_deps="now-playing-deps",
            collections="collections",
            active_streams="active-streams",
            playback_service="playback-service",
            legacy="legacy",
        )
        access = EntrypointComponentAccess(
            state=state,
            ensure_components=lambda: calls.append("ensure"),
        )

        bundle = access.require()

        self.assertEqual(calls, ["ensure"])
        self.assertIsInstance(bundle, EntrypointComponents)
        self.assertEqual(bundle.app_services, "app-services")
        self.assertEqual(bundle.service_facade, "service-facade")
        self.assertEqual(bundle.stream_runtime, "stream-runtime")
        self.assertEqual(bundle.archive_runtime, "archive-runtime")
        self.assertEqual(bundle.playback_assets, "playback-assets")
        self.assertEqual(bundle.now_playing_deps, "now-playing-deps")
        self.assertEqual(bundle.collections, "collections")
        self.assertEqual(bundle.active_streams, "active-streams")
        self.assertEqual(bundle.playback_service, "playback-service")
        self.assertEqual(bundle.legacy, "legacy")
