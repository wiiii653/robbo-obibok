import sys
import types
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_launcher_loader import EntrypointModuleLoader
from entrypoint_module_bindings import (
    ENTRYPOINT_COMPAT_RUNTIME_BINDINGS,
)
from entrypoint_module_bindings import (
    ENTRYPOINT_DIRECT_EXPORT_SPECS_BY_NAME,
)


class EntrypointLauncherLoaderTests(unittest.TestCase):
    def test_loader_exposes_typed_collection_and_runtime_exports_without_compat(self):
        compat_calls = []
        state = types.SimpleNamespace(
            legacy=types.SimpleNamespace(
                skip_to_next="skip",
                cleanup_orphan_players="cleanup",
                stop_all_players="stop",
                auto_play_after_switch="auto",
                play_subsong="subsong",
            ),
            service_facade=types.SimpleNamespace(
                cleanup_subsong_temp_wavs="cleanup_wavs",
                switch_collection="switch",
            ),
        )
        module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(
                    resolve=lambda name: compat_calls.append(name) or f"compat:{name}"
                )
            )
        )

        def resolve_legacy(name):
            if name == "_STATE":
                return state
            raise AttributeError(name)

        bindings = types.SimpleNamespace(
            resolve=resolve_legacy,
            exports={"monitor_playback": "monitor", "_after_stream_end": "after"},
        )

        loader = EntrypointModuleLoader(
            module_factory=lambda: module,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.module = module
        loader.bindings = bindings

        self.assertEqual(loader.collection_export("_skip_to_next"), "skip")
        self.assertEqual(
            loader.collection_export(ENTRYPOINT_DIRECT_EXPORT_SPECS_BY_NAME["_cleanup_subsong_temp_wavs"]),
            "cleanup_wavs",
        )
        self.assertEqual(loader.collection_export("_switch_collection"), "switch")
        self.assertEqual(loader.runtime_export("monitor_playback"), "monitor")
        self.assertEqual(
            loader.runtime_export(ENTRYPOINT_DIRECT_EXPORT_SPECS_BY_NAME["_after_stream_end"]),
            "after",
        )
        self.assertEqual(loader.runtime_export("_after_stream_end"), "after")
        self.assertEqual(compat_calls, [])

    def test_loader_rejects_unknown_direct_export_name(self):
        loader = EntrypointModuleLoader(
            module_factory=lambda: types.SimpleNamespace(
                app=types.SimpleNamespace(compat=types.SimpleNamespace(resolve=lambda name: name))
            ),
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.bindings = types.SimpleNamespace(
            resolve=lambda name: (_ for _ in ()).throw(AttributeError(name)),
            exports={},
        )
        loader.module = types.SimpleNamespace(
            app=types.SimpleNamespace(compat=types.SimpleNamespace(resolve=lambda name: name))
        )

        with self.assertRaises(AttributeError):
            loader.collection_export("not_a_direct_export")

    def test_loader_exposes_bootstrap_app_without_compat_lookup(self):
        compat_calls = []
        bootstrap_app = object()
        module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(
                    resolve=lambda name: compat_calls.append(name) or f"compat:{name}"
                )
            )
        )
        bindings = types.SimpleNamespace(
            state=types.SimpleNamespace(_APP=bootstrap_app),
            resolve=lambda name: (_ for _ in ()).throw(AttributeError(name)),
        )

        loader = EntrypointModuleLoader(
            module_factory=lambda: module,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.module = module
        loader.bindings = bindings

        self.assertIs(loader.bootstrap_app(), bootstrap_app)
        self.assertEqual(compat_calls, [])

    def test_loader_prefers_legacy_and_falls_back_to_compat(self):
        compat_calls = []
        module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(
                    resolve=lambda name: compat_calls.append(name) or f"compat:{name}"
                )
            )
        )
        def resolve_legacy(name):
            if name == "bot":
                return "legacy-bot"
            raise AttributeError(name)

        bindings = types.SimpleNamespace(
            resolve=resolve_legacy
        )

        loader = EntrypointModuleLoader(
            module_factory=lambda: module,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.module = module
        loader.bindings = bindings

        self.assertEqual(loader.resolve("bot"), "legacy-bot")
        with self.assertRaises(AttributeError):
            loader.resolve("_switch_collection")
        self.assertEqual(compat_calls, [])

    def test_loader_falls_back_to_runtime_compat_only(self):
        compat_calls = []
        module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(
                    resolve=lambda name: compat_calls.append(name) or f"compat:{name}"
                )
            )
        )
        bindings = types.SimpleNamespace(resolve=lambda name: (_ for _ in ()).throw(AttributeError(name)))

        loader = EntrypointModuleLoader(
            module_factory=lambda: module,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.module = module
        loader.bindings = bindings

        self.assertEqual(loader.resolve("LOCK_FILE"), "compat:LOCK_FILE")
        self.assertEqual(compat_calls, ["LOCK_FILE"])

    def test_loader_runtime_state_surface_and_lock_file_smoke_cover_state_config_and_lock(self):
        compat_calls = []
        runtime_state = types.SimpleNamespace(startup_env=None)
        module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(
                    resolve=lambda name: compat_calls.append(name) or {"LOCK_FILE": "/tmp/lock"}[name]
                )
            )
        )

        def resolve_legacy(name):
            return {
                "_STATE": runtime_state,
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(name="archive"),
            }[name]

        loader = EntrypointModuleLoader(
            module_factory=lambda: module,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.module = module
        loader.bindings = types.SimpleNamespace(
            resolve=resolve_legacy,
            state=types.SimpleNamespace(_APP=object()),
        )

        runtime = loader.runtime_state_surface()

        self.assertIs(runtime.state(), runtime_state)
        self.assertEqual(runtime.app_config().bot_token, "cfg-token")
        self.assertEqual(runtime.archive_runtime_config().name, "archive")
        self.assertEqual(loader.lock_file(), "/tmp/lock")
        self.assertEqual(compat_calls, ["LOCK_FILE"])

    def test_loader_builds_typed_runtime_state_surface_from_legacy_bindings(self):
        runtime_state = types.SimpleNamespace(startup_env=None)
        loader = EntrypointModuleLoader(
            module_factory=lambda: types.SimpleNamespace(
                app=types.SimpleNamespace(
                    compat=types.SimpleNamespace(resolve=lambda name: f"compat:{name}")
                )
            ),
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.bindings = types.SimpleNamespace(
            resolve=lambda name: {
                "_STATE": runtime_state,
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(name="archive"),
            }[name]
        )
        loader.module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(resolve=lambda name: f"compat:{name}")
            )
        )

        surface = loader.runtime_state_surface()

        self.assertIs(surface.state(), runtime_state)
        self.assertEqual(surface.app_config().bot_token, "cfg-token")
        self.assertEqual(surface.archive_runtime_config().name, "archive")

    def test_loader_builds_typed_stable_runtime_surface_from_legacy_bindings(self):
        runtime_state = types.SimpleNamespace(startup_env=None)
        loader = EntrypointModuleLoader(
            module_factory=lambda: types.SimpleNamespace(
                app=types.SimpleNamespace(
                    compat=types.SimpleNamespace(resolve=lambda name: f"compat:{name}")
                )
            ),
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.bindings = types.SimpleNamespace(
            resolve=lambda name: {
                "bot": "bot",
                "single_guild_check": "check",
                "get_guild_id_override": "getter",
                "set_guild_id_override": "setter",
                "_STATE": runtime_state,
                "_app_cfg": lambda: types.SimpleNamespace(bot_token="cfg-token"),
                "_archive_runtime_config": lambda: types.SimpleNamespace(name="archive"),
                "_FLIP_ORDER": ["asma"],
                "_FLIP_SEQ": ["ASMA"],
            }[name]
        )
        loader.module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(resolve=lambda name: f"compat:{name}")
            )
        )

        surface = loader.stable_runtime_surface()

        self.assertEqual(surface.bot(), "bot")
        self.assertEqual(surface.single_guild_check(), "check")
        self.assertIs(surface.state(), runtime_state)
        self.assertEqual(surface.app_config()().bot_token, "cfg-token")
        self.assertEqual(surface.flip_order(), ["asma"])

    def test_loader_exposes_typed_compat_accessors(self):
        compat_calls = []
        compat_values = {
            "GUILD_ID": 123,
            "_STREAM_RUNTIME": "stream",
            "_NOW_PLAYING_DEPS": "np",
            "_LEGACY": "legacy",
            "_APP": "app",
            "_RUNTIME_REGISTRATION": "registration",
            "LOCK_FILE": "/tmp/lock",
            "_shutdown_flag": "flag",
        }
        module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(
                    resolve=lambda name: compat_calls.append(name) or compat_values[name]
                )
            )
        )
        bindings = types.SimpleNamespace(resolve=lambda name: (_ for _ in ()).throw(AttributeError(name)))

        loader = EntrypointModuleLoader(
            module_factory=lambda: module,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.module = module
        loader.bindings = bindings

        self.assertEqual(loader.guild_id(), 123)
        self.assertEqual(loader.stream_runtime(), "stream")
        self.assertEqual(loader.now_playing_deps(), "np")
        self.assertEqual(loader.legacy_runtime(), "legacy")
        self.assertEqual(loader.app_instance(), "app")
        self.assertEqual(loader.runtime_registration(), "registration")
        self.assertEqual(loader.lock_file(), "/tmp/lock")
        self.assertEqual(loader.shutdown_flag(), "flag")
        self.assertEqual(
            compat_calls,
            [spec.export_name for spec in ENTRYPOINT_COMPAT_RUNTIME_BINDINGS],
        )
        self.assertEqual(loader.resolve_compat_view("lock_file"), "/tmp/lock")

    def test_loader_exposes_typed_compat_view(self):
        compat_calls = []
        compat_values = {
            "GUILD_ID": 55,
            "_STREAM_RUNTIME": "stream-view",
            "_NOW_PLAYING_DEPS": "np-view",
            "_LEGACY": "legacy-view",
            "_APP": "app-view",
            "_RUNTIME_REGISTRATION": "registration-view",
            "LOCK_FILE": "/tmp/view.lock",
            "_shutdown_flag": "flag-view",
        }
        module = types.SimpleNamespace(
            app=types.SimpleNamespace(
                compat=types.SimpleNamespace(
                    resolve=lambda name: compat_calls.append(name) or compat_values[name]
                )
            )
        )
        bindings = types.SimpleNamespace(resolve=lambda name: (_ for _ in ()).throw(AttributeError(name)))

        loader = EntrypointModuleLoader(
            module_factory=lambda: module,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        loader.module = module
        loader.bindings = bindings

        compat = loader.compat()

        self.assertEqual(compat.guild_id(), 55)
        self.assertEqual(compat.stream_runtime(), "stream-view")
        self.assertEqual(compat.now_playing_deps(), "np-view")
        self.assertEqual(compat.legacy_runtime(), "legacy-view")
        self.assertEqual(compat.app_instance(), "app-view")
        self.assertEqual(compat.runtime_registration(), "registration-view")
        self.assertEqual(compat.lock_file(), "/tmp/view.lock")
        self.assertEqual(compat.shutdown_flag(), "flag-view")
        self.assertEqual(
            compat_calls,
            [spec.export_name for spec in ENTRYPOINT_COMPAT_RUNTIME_BINDINGS],
        )
        self.assertEqual(compat.resolve_view("lock_file"), "/tmp/view.lock")

    def test_loader_builds_module_and_bindings_once(self):
        factory_calls = []
        binding_calls = []
        module = types.SimpleNamespace(app=types.SimpleNamespace(compat=types.SimpleNamespace(resolve=lambda name: name)))

        loader = EntrypointModuleLoader(
            module_factory=lambda: factory_calls.append("factory") or module,
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )

        from unittest.mock import patch

        with patch(
            "entrypoint_launcher_loader.build_entrypoint_legacy_bindings",
            side_effect=lambda **kwargs: binding_calls.append(kwargs) or types.SimpleNamespace(resolve=lambda name: name),
        ):
            self.assertIs(loader.ensure_module(), module)
            self.assertIs(loader.ensure_module(), module)

        self.assertEqual(factory_calls, ["factory"])
        self.assertEqual(len(binding_calls), 1)
        self.assertEqual(binding_calls[0]["flip_order"], ["asma"])
        self.assertEqual(binding_calls[0]["flip_seq"], ["ASMA"])
