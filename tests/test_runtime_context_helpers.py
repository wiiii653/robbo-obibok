import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import types

from tests.test_runtime_context import (
    build_runtime_test_context,
    command_test_context,
    get_runtime_test_context,
)


class RuntimeContextTests(unittest.TestCase):
    def test_with_overrides_returns_replaced_context(self):
        context = get_runtime_test_context()
        replaced = context.with_overrides(service_facade="override-service")

        self.assertIsNot(replaced, context)
        self.assertEqual(replaced.service_facade, "override-service")
        self.assertIs(replaced.runtime, context.runtime)

    def test_scoped_helpers_restore_runtime_state(self):
        context = get_runtime_test_context()
        original_guilds = dict(context.guilds_map())
        original_handlers = dict(context.playback_handlers)
        original_collection = context.collections["hvsc"]
        original_message_track_map = dict(context.message_track_map)

        with (
            context.scoped_guilds({999: "guild-state"}),
            context.scoped_playback_handlers({"asma": "handler"}),
            context.scoped_collection("hvsc", "override-collection"),
            context.scoped_message_track_map({77: {"url": "track.sap"}}),
        ):
            self.assertEqual(dict(context.guilds_map()), {999: "guild-state"})
            self.assertEqual(context.playback_handlers["asma"], "handler")
            self.assertEqual(context.collections["hvsc"], "override-collection")
            self.assertEqual(context.message_track_map, {77: {"url": "track.sap"}})

        self.assertEqual(dict(context.guilds_map()), original_guilds)
        self.assertEqual(dict(context.playback_handlers), original_handlers)
        self.assertIs(context.collections["hvsc"], original_collection)
        self.assertEqual(dict(context.message_track_map), original_message_track_map)

    def test_isolated_command_runtime_swaps_mutable_registries(self):
        context = get_runtime_test_context()
        original_handlers = context.playback_handlers
        original_collections = context.collections
        original_message_track_map = context.message_track_map
        original_active_streams = context.active_streams

        with context.isolated_command_runtime() as isolated:
            self.assertIsNot(isolated.playback_handlers, original_handlers)
            self.assertIsNot(isolated.collections, original_collections)
            self.assertIsNot(isolated.message_track_map, original_message_track_map)
            self.assertIsNot(isolated.active_streams, original_active_streams)
            isolated.register_guild_state(5, "guild")
            isolated.playback_handlers["asma"] = "handler"
            isolated.collections["hvsc"] = "collection"
            isolated.message_track_map[7] = {"url": "track.sap"}

        self.assertIs(context.playback_handlers, original_handlers)
        self.assertIs(context.collections, original_collections)
        self.assertIs(context.message_track_map, original_message_track_map)
        self.assertIs(context.active_streams, original_active_streams)

    def test_isolated_command_runtime_deep_copies_nested_guild_state(self):
        guild_state = types.SimpleNamespace(queue=["track-1"])
        state = types.SimpleNamespace(
            stream_runtime=types.SimpleNamespace(active_streams={}),
            service_facade="service",
            collection_service=types.SimpleNamespace(collections={"asma": ["track-1"]}),
            collections={"asma": ["track-1"]},
        )
        runtime = types.SimpleNamespace(
            state=types.SimpleNamespace(
                app_services=types.SimpleNamespace(
                    app_state=types.SimpleNamespace(guilds={5: guild_state}, message_track_map={}),
                ),
                playback_handlers={"asma": "handler"},
                collections=state.collections,
            )
        )

        context = build_runtime_test_context(
            state=state,
            runtime=runtime,
            app_config="cfg",
            archive_runtime_config="archive-cfg",
        )

        original_nested_guild_state = context.guilds_map()[5]

        with context.isolated_command_runtime() as isolated:
            self.assertIsNot(isolated.guilds_map()[5], original_nested_guild_state)
            isolated.guilds_map()[5].queue.append("track-2")

        self.assertEqual(context.guilds_map()[5].queue, ["track-1"])

    def test_command_test_context_uses_isolated_runtime_snapshot(self):
        context = get_runtime_test_context()
        original_handlers = context.playback_handlers
        original_collections = context.collections

        with command_test_context() as isolated:
            self.assertIsNot(isolated.playback_handlers, original_handlers)
            self.assertIsNot(isolated.collections, original_collections)

    def test_isolated_command_runtime_deep_copies_nested_collection_values(self):
        state = types.SimpleNamespace(
            stream_runtime=types.SimpleNamespace(active_streams={}),
            service_facade="service",
            collection_service=types.SimpleNamespace(collections={"asma": ["track-1"]}),
            collections={"asma": ["track-1"]},
        )
        runtime = types.SimpleNamespace(
            state=types.SimpleNamespace(
                app_services=types.SimpleNamespace(
                    app_state=types.SimpleNamespace(guilds={}, message_track_map={}),
                ),
                playback_handlers={"asma": "handler"},
                collections=state.collections,
            )
        )

        context = build_runtime_test_context(
            state=state,
            runtime=runtime,
            app_config="cfg",
            archive_runtime_config="archive-cfg",
        )

        original_nested_collection = context.collections["asma"]

        with context.isolated_command_runtime() as isolated:
            self.assertIsNot(isolated.collections["asma"], original_nested_collection)
            isolated.collections["asma"].append("track-2")

        self.assertEqual(context.collections["asma"], ["track-1"])

    def test_isolated_command_runtime_deep_copies_nested_message_track_map_values(self):
        state = types.SimpleNamespace(
            stream_runtime=types.SimpleNamespace(active_streams={}),
            service_facade="service",
            collection_service=types.SimpleNamespace(collections={"asma": ["track-1"]}),
            collections={"asma": ["track-1"]},
        )
        message_track_map = {10: {"url": "track-1.sap", "tags": ["fav"]}}
        runtime = types.SimpleNamespace(
            state=types.SimpleNamespace(
                app_services=types.SimpleNamespace(
                    app_state=types.SimpleNamespace(guilds={}, message_track_map=message_track_map),
                ),
                playback_handlers={"asma": "handler"},
                collections=state.collections,
            )
        )

        context = build_runtime_test_context(
            state=state,
            runtime=runtime,
            app_config="cfg",
            archive_runtime_config="archive-cfg",
        )

        original_entry = context.message_track_map[10]

        with context.isolated_command_runtime() as isolated:
            self.assertIsNot(isolated.message_track_map[10], original_entry)
            isolated.message_track_map[10]["tags"].append("queued")

        self.assertEqual(context.message_track_map[10]["tags"], ["fav"])

    def test_isolated_command_runtime_deep_copies_nested_active_stream_values(self):
        active_stream = types.SimpleNamespace(history=["start"])
        state = types.SimpleNamespace(
            stream_runtime=types.SimpleNamespace(active_streams={1: active_stream}),
            service_facade="service",
            collection_service=types.SimpleNamespace(collections={"asma": ["track-1"]}),
            collections={"asma": ["track-1"]},
        )
        runtime = types.SimpleNamespace(
            state=types.SimpleNamespace(
                app_services=types.SimpleNamespace(
                    app_state=types.SimpleNamespace(guilds={}, message_track_map={}),
                ),
                playback_handlers={"asma": "handler"},
                collections=state.collections,
            )
        )

        context = build_runtime_test_context(
            state=state,
            runtime=runtime,
            app_config="cfg",
            archive_runtime_config="archive-cfg",
        )

        original_stream = context.active_streams[1]

        with context.isolated_command_runtime() as isolated:
            self.assertIsNot(isolated.active_streams[1], original_stream)
            isolated.active_streams[1].history.append("stop")

        self.assertEqual(context.active_streams[1].history, ["start"])

    def test_build_runtime_test_context_uses_explicit_state_and_runtime(self):
        stream_runtime = types.SimpleNamespace(active_streams="active-streams")
        app_services = types.SimpleNamespace(
            app_state=types.SimpleNamespace(guilds={}, message_track_map={"msg": "track"})
        )
        state = types.SimpleNamespace(
            stream_runtime=stream_runtime,
            service_facade="service",
            collection_service="collections-service",
            collections={"asma": ["track"]},
        )
        runtime = types.SimpleNamespace(
            state=types.SimpleNamespace(
                app_services=app_services,
                playback_handlers={"asma": "handler"},
            )
        )

        context = build_runtime_test_context(
            state=state,
            runtime=runtime,
            app_config="cfg",
            archive_runtime_config="archive-cfg",
        )

        self.assertIs(context.state, state)
        self.assertIs(context.runtime, runtime)
        self.assertIs(context.stream_runtime, stream_runtime)
        self.assertEqual(context.active_streams, "active-streams")
        self.assertEqual(context.service_facade, "service")
        self.assertEqual(context.collection_service, "collections-service")
        self.assertEqual(context.collections, {"asma": ["track"]})
        self.assertIs(context.app_services, app_services)
        self.assertEqual(context.message_track_map, {"msg": "track"})
        self.assertEqual(context.playback_handlers, {"asma": "handler"})
        self.assertEqual(context.app_config, "cfg")
        self.assertEqual(context.archive_runtime_config, "archive-cfg")
