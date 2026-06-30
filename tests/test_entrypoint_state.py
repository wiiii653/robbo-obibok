import asyncio
import sys
from pathlib import Path
import types
import unittest
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_state import EntrypointState
from app_context import ArchiveRegistryViews


class EntrypointStateTests(unittest.TestCase):
    def test_apply_bootstrap_registry_populates_public_bootstrap_properties(self):
        state = EntrypointState()
        archive_views = ArchiveRegistryViews(
            metadata_index=MappingProxyType({"track.sap": {"NAME": "Track"}}),
            modarchive_name_map=MappingProxyType({"mod": "Module"}),
            sid_durations=MappingProxyType({"track.sid": 120}),
            snes_metadata=MappingProxyType({"game.rsn": {"name": "Game"}}),
        )

        state.apply_bootstrap_registry(
            bootstrapped_app="boot",
            app_context="context",
            app_state="runtime-state",
            archives="archives",
            app_services="services",
            archive_views=archive_views,
        )

        self.assertEqual(state.bootstrapped_app, "boot")
        self.assertEqual(state.app_context, "context")
        self.assertEqual(state.app_state, "runtime-state")
        self.assertEqual(state.archives, "archives")
        self.assertEqual(state.app_services, "services")
        self.assertIs(state.archive_views, archive_views)

    def test_cache_initialized_app_populates_initialized_runtime_properties(self):
        state = EntrypointState()
        shutdown_flag = asyncio.Event()
        runtime = object()
        composed = object()
        registration = types.SimpleNamespace(composed=composed, runtime=runtime)
        collection_service = object()
        playback_service = object()
        startup_env = types.SimpleNamespace(lock_file="/tmp/obibok.pid", shutdown_flag=shutdown_flag)
        app = types.SimpleNamespace(
            startup_env=startup_env,
            runtime_registration=registration,
            collection_service=collection_service,
            playback_service=playback_service,
        )

        returned = state.cache_initialized_app(app)

        self.assertIs(returned, app)
        self.assertIs(state.app, app)
        self.assertIs(state.startup_env, startup_env)
        self.assertEqual(state.lock_file, "/tmp/obibok.pid")
        self.assertIs(state.shutdown_flag, shutdown_flag)
        self.assertIs(state.runtime_registration, registration)
        self.assertIs(state.composed_runtime, composed)
        self.assertIs(state.runtime, runtime)
        self.assertIs(state.collection_service, collection_service)
        self.assertIs(state.playback_service, playback_service)

    def test_component_bundle_reads_grouped_component_properties(self):
        state = EntrypointState(app_services="services")
        state.service_facade = "facade"
        state.stream_runtime = "stream"
        state.archive_runtime = "archive"
        state.playback_assets = "assets"
        state.now_playing_deps = "np"
        state.collections = {"asma": "spec"}
        state.active_streams = {7: "source"}
        state.playback_service = "playback"
        state.legacy = "legacy"

        bundle = state.component_bundle()

        self.assertEqual(bundle.app_services, "services")
        self.assertEqual(bundle.service_facade, "facade")
        self.assertEqual(bundle.stream_runtime, "stream")
        self.assertEqual(bundle.archive_runtime, "archive")
        self.assertEqual(bundle.playback_assets, "assets")
        self.assertEqual(bundle.now_playing_deps, "np")
        self.assertEqual(bundle.collections, {"asma": "spec"})
        self.assertEqual(bundle.active_streams, {7: "source"})
        self.assertEqual(bundle.playback_service, "playback")
        self.assertEqual(bundle.legacy, "legacy")
