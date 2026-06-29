from contextlib import contextmanager
from copy import copy
from copy import deepcopy
from dataclasses import dataclass, replace
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_live_support import load_live_runtime_bundle


def _clone_value(value: object) -> object:
    try:
        return deepcopy(value)
    except (TypeError, ValueError):
        return copy(value)


@dataclass(frozen=True, slots=True)
class RuntimeTestContext:
    state: object
    runtime: object
    stream_runtime: object
    active_streams: object
    service_facade: object
    collection_service: object
    collections: object
    app_services: object
    message_track_map: object
    playback_handlers: object
    app_config: object
    archive_runtime_config: object

    def with_overrides(self, **changes) -> "RuntimeTestContext":
        return replace(self, **changes)

    def playback_command_deps(self, **changes):
        return replace(self.runtime.build_playback_command_deps(), **changes)

    def library_command_deps(self, **changes):
        return replace(self.runtime.build_library_command_deps(), **changes)

    def guilds_map(self):
        app_state = self.app_services.app_state
        return app_state.guilds_view if hasattr(app_state, "guilds_view") else app_state.guilds

    def message_track_entries(self):
        app_state = self.app_services.app_state
        return app_state.message_track_map_view if hasattr(app_state, "message_track_map_view") else app_state.message_track_map

    def replace_guilds(self, guilds: dict[int, object]) -> None:
        app_state = self.app_services.app_state
        if hasattr(app_state, "replace_guilds"):
            app_state.replace_guilds(guilds)
            return
        app_state.guilds.clear()
        app_state.guilds.update(guilds)

    def replace_message_track_map(self, entries: dict[int, object]) -> None:
        app_state = self.app_services.app_state
        if hasattr(app_state, "replace_message_track_map"):
            app_state.replace_message_track_map(entries)
            return
        app_state.message_track_map.clear()
        app_state.message_track_map.update(entries)

    def register_guild_state(self, guild_id: int, state: object) -> None:
        app_state = self.app_services.app_state
        if hasattr(app_state, "register_guild_state"):
            app_state.register_guild_state(guild_id, state)
            return
        app_state.guilds[guild_id] = state

    @contextmanager
    def scoped_guilds(self, guilds: dict[int, object]):
        original = deepcopy(dict(self.guilds_map()))
        try:
            self.replace_guilds(guilds)
            yield self
        finally:
            self.replace_guilds(original)

    @contextmanager
    def scoped_playback_handlers(self, updates: dict[str, object]):
        original = dict(self.playback_handlers)
        try:
            self.playback_handlers.update(updates)
            yield self
        finally:
            self.playback_handlers.clear()
            self.playback_handlers.update(original)

    @contextmanager
    def scoped_collection(self, name: str, value: object):
        original = self.collections[name]
        try:
            self.collections[name] = value
            yield self
        finally:
            self.collections[name] = original

    @contextmanager
    def scoped_message_track_map(self, entries: dict[int, object]):
        original = deepcopy(dict(self.message_track_entries()))
        try:
            self.replace_message_track_map(entries)
            yield self
        finally:
            self.replace_message_track_map(original)

    @contextmanager
    def scoped_attrs(self, obj: object, **updates):
        originals = {name: getattr(obj, name) for name in updates}
        try:
            for name, value in updates.items():
                setattr(obj, name, value)
            yield obj
        finally:
            for name, value in originals.items():
                setattr(obj, name, value)

    @contextmanager
    def isolated_command_runtime(self):
        cloned_guilds = deepcopy(dict(self.guilds_map()))
        cloned_handlers = dict(self.playback_handlers)
        cloned_collections = {name: _clone_value(value) for name, value in self.collections.items()}
        cloned_active_streams = deepcopy(self.stream_runtime.active_streams)
        cloned_message_track_map = deepcopy(dict(self.message_track_entries()))

        runtime_state = self.runtime.state

        with (
            self.scoped_guilds(cloned_guilds),
            self.scoped_message_track_map(cloned_message_track_map),
            self.scoped_attrs(runtime_state, playback_handlers=cloned_handlers, collections=cloned_collections),
            self.scoped_attrs(self.collection_service, collections=cloned_collections),
            self.scoped_attrs(self.stream_runtime, active_streams=cloned_active_streams),
        ):
            yield self.with_overrides(
                active_streams=cloned_active_streams,
                collections=cloned_collections,
                message_track_map=cloned_message_track_map,
                playback_handlers=cloned_handlers,
            )


def build_runtime_test_context_from_live_state(
    *,
    state: object,
    runtime: object,
    app_config: object,
    archive_runtime_config: object,
) -> RuntimeTestContext:
    return build_runtime_test_context(
        state=state,
        runtime=runtime,
        app_config=app_config,
        archive_runtime_config=archive_runtime_config,
    )


def build_runtime_test_context(
    *,
    state: object,
    runtime: object,
    app_config: object,
    archive_runtime_config: object,
) -> RuntimeTestContext:
    return RuntimeTestContext(
        state=state,
        runtime=runtime,
        stream_runtime=state.stream_runtime,
        active_streams=state.stream_runtime.active_streams,
        service_facade=state.service_facade,
        collection_service=state.collection_service,
        collections=state.collections,
        app_services=runtime.state.app_services,
        message_track_map=runtime.state.app_services.app_state.message_track_map,
        playback_handlers=runtime.state.playback_handlers,
        app_config=app_config,
        archive_runtime_config=archive_runtime_config,
    )


def get_runtime_test_context() -> RuntimeTestContext:
    bundle = load_live_runtime_bundle()
    return build_runtime_test_context_from_live_state(
        state=bundle.state,
        runtime=bundle.runtime,
        app_config=bundle.app_config,
        archive_runtime_config=bundle.archive_runtime_config,
    )


@contextmanager
def command_test_context():
    with get_runtime_test_context().isolated_command_runtime() as runtime_ctx:
        yield runtime_ctx
