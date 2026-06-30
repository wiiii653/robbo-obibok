import sys
from pathlib import Path
import unittest
import warnings

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_runtime_compat import (
    resolve_runtime_internal_attr,
)


class EntrypointRuntimeCompatTests(unittest.TestCase):
    def test_deprecated_internal_warning_message_is_explicit(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertEqual(
                resolve_runtime_internal_attr(
                    "_LAUNCHER",
                    assembly_peek=lambda: "assembly",
                    bindings_getter=lambda: "bindings",
                    compat_bindings_getter=lambda: "compat-bindings",
                    compat_policy_getter=lambda: True,
                    launcher_getter=lambda: "launcher",
                    deps_getter=lambda: "deps",
                    legacy_resolve_getter=lambda: "legacy-resolve",
                    surface_getter=lambda: "surface",
                ),
                "launcher",
            )

        self.assertEqual(len(caught), 1)
        self.assertEqual(
            str(caught[0].message),
            "_LAUNCHER is a deprecated runtime compatibility attribute and will be removed in a future refactor",
        )
        self.assertIs(caught[0].category, DeprecationWarning)
