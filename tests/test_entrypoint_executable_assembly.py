import sys
import types
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_support import install_discord_stubs


install_discord_stubs()

from entrypoint_module_bindings import ALLOW_DEPRECATED
from entrypoint_executable_assembly import (
    build_entrypoint_executable_assembly,
    build_entrypoint_executable_dependencies,
    build_strict_entrypoint_executable_assembly,
)
from entrypoint_module_bindings import ENTRYPOINT_EXPORT_GRAPH, ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES
from tests.test_entrypoint_launcher_fixtures import build_fake_launcher_module


class EntrypointExecutableAssemblyTests(unittest.TestCase):
    def test_build_entrypoint_executable_dependencies_uses_provider_bundle(self):
        providers = types.SimpleNamespace(
            registration=object(),
            playback_policy=object(),
            collection=object(),
        )
        deps = object()

        with (
            patch(
                "entrypoint_executable_assembly.build_default_entrypoint_providers",
                return_value=providers,
            ) as build_providers,
            patch(
                "entrypoint_executable_assembly.build_entrypoint_module_deps",
                return_value=deps,
            ) as build_deps,
        ):
            resolved_providers, resolved_deps = build_entrypoint_executable_dependencies(
                flip_order=["asma"],
                flip_seq=["ASMA"],
            )

        self.assertIs(resolved_providers, providers)
        self.assertIs(resolved_deps, deps)
        build_providers.assert_called_once_with(
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        build_deps.assert_called_once_with(
            registration=providers.registration,
            playback_policy=providers.playback_policy,
            collection=providers.collection,
        )

    def test_build_entrypoint_executable_assembly_wires_launcher_surface_and_bindings(self):
        providers = types.SimpleNamespace()
        deps = object()
        launcher = types.SimpleNamespace()
        legacy_source = {"_STATE": object()}
        loader = types.SimpleNamespace(
            legacy_bindings=lambda: legacy_source,
            resolve_legacy=lambda name: f"legacy:{name}",
        )
        surface = object()
        bindings = {"bot": object()}
        compat_bindings = {"_STATE": object()}
        legacy_resolve = object()

        setattr(launcher, "loader", loader)

        with (
            patch(
                "entrypoint_executable_assembly.build_entrypoint_executable_dependencies",
                return_value=(providers, deps),
            ) as build_dependencies,
            patch(
                "entrypoint_executable_assembly.build_entrypoint_launcher",
                return_value=launcher,
            ) as build_launcher,
            patch(
                "entrypoint_executable_assembly.build_entrypoint_legacy_resolver",
                return_value=legacy_resolve,
            ) as build_legacy,
            patch(
                "entrypoint_executable_assembly.build_entrypoint_module_surface",
                return_value=surface,
            ) as build_surface,
            patch(
                "entrypoint_executable_assembly.build_entrypoint_stable_module_bindings",
                return_value=bindings,
            ) as build_bindings,
            patch(
                "entrypoint_executable_assembly.build_entrypoint_compat_module_bindings",
                return_value=compat_bindings,
            ) as build_compat_bindings,
        ):
            assembly = build_entrypoint_executable_assembly(
                module_path="/tmp/robbo-obibok.py",
                logger_name="robbo-obibok",
                command_prefix=lambda _bot, _message: "!",
                flip_order=["asma"],
                flip_seq=["ASMA"],
            )

        self.assertIs(assembly.launcher, launcher)
        self.assertIs(assembly.providers, providers)
        self.assertIs(assembly.deps, deps)
        self.assertIs(assembly.legacy_resolve, legacy_resolve)
        self.assertIs(assembly.surface, surface)
        self.assertIs(assembly.bindings, bindings)
        self.assertIs(assembly.compat_bindings, compat_bindings)
        self.assertIs(assembly.compat_policy, ALLOW_DEPRECATED)
        build_dependencies.assert_called_once_with(
            flip_order=["asma"],
            flip_seq=["ASMA"],
        )
        build_launcher.assert_called_once()
        self.assertEqual(build_launcher.call_args.kwargs["deps"], deps)
        build_legacy.assert_called_once_with(loader=loader)
        build_surface.assert_called_once_with(
            launcher=launcher,
            resolve_fallback=legacy_resolve,
        )
        build_bindings.assert_called_once_with(surface)
        build_compat_bindings.assert_called_once_with(
            loader,
            resolver=loader.resolve_legacy,
        )

    def test_executable_smoke_exposes_bound_and_compat_exports_from_assembly_products(self):
        compat_calls = []
        bot_calls = []
        runtime_app = types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token"))
        fake_module = build_fake_launcher_module(
            runtime_app=runtime_app,
            init_calls=[],
            compat_calls=compat_calls,
            bot_calls=bot_calls,
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            assembly = build_entrypoint_executable_assembly(
                module_path=str(ROOT / "robbo-obibok.py"),
                logger_name="robbo-obibok",
                command_prefix=lambda _bot, _message: "!",
                flip_order=["asma"],
                flip_seq=["ASMA"],
            )

        self.assertEqual(set(assembly.bindings), ENTRYPOINT_EXPORT_GRAPH.bound_names())
        self.assertEqual(
            set(assembly.compat_bindings),
            ENTRYPOINT_MODULE_LEGACY_COMPAT_NAMES,
        )
        self.assertIs(assembly.bindings["bot"], assembly.surface.resolve("bot"))
        self.assertEqual(assembly.surface.resolve("_skip_to_next")(), "skip")
        self.assertEqual(assembly.surface.resolve("monitor_playback")(), "monitor")
        self.assertEqual(assembly.surface.resolve("LOCK_FILE"), "resolved:LOCK_FILE")
        self.assertEqual(assembly.surface.resolve("bot").ping(), "pong")
        self.assertEqual(bot_calls, ["ping"])
        self.assertEqual(compat_calls, ["LOCK_FILE"])
        with self.assertRaises(AttributeError):
            assembly.surface.resolve("_FLIP_ORDER")
        with self.assertRaises(AttributeError):
            assembly.surface.resolve("_FLIP_SEQ")
        with self.assertRaises(AttributeError):
            assembly.surface.resolve("definitely_missing")
        self.assertIn("LOCK_FILE", ENTRYPOINT_EXPORT_GRAPH.compat_names)

    def test_build_strict_entrypoint_executable_assembly_disables_compat_shims_per_instance(self):
        compat_calls = []
        bot_calls = []
        runtime_app = types.SimpleNamespace(startup_env=types.SimpleNamespace(bot_token="runtime-token"))
        fake_module = build_fake_launcher_module(
            runtime_app=runtime_app,
            init_calls=[],
            compat_calls=compat_calls,
            bot_calls=bot_calls,
        )

        with patch("entrypoint_module.build_entrypoint_module", return_value=fake_module):
            assembly = build_strict_entrypoint_executable_assembly(
                module_path=str(ROOT / "robbo-obibok.py"),
                logger_name="robbo-obibok",
                command_prefix=lambda _bot, _message: "!",
                flip_order=["asma"],
                flip_seq=["ASMA"],
            )

        self.assertIs(assembly.compat_policy, ALLOW_DEPRECATED)
