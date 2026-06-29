import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entrypoint_compat_policy import (
    EntrypointCompatPolicy,
    build_compat_policy,
    build_strict_compat_policy,
)
from entrypoint_module_bindings import (
    ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES,
    ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES,
)


class EntrypointCompatPolicyTests(unittest.TestCase):
    def test_default_policy_admits_deprecated_internal_and_core_legacy_attrs_only(self):
        policy = build_compat_policy()

        self.assertTrue(
            all(
                policy.allows_deprecated_runtime_internal_attr(name)
                for name in ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES
            )
        )
        self.assertTrue(
            all(
                policy.allows_legacy_runtime_compat_attr(name)
                for name in ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES
            )
        )
        self.assertTrue(
            all(
                not policy.allows_legacy_runtime_compat_attr(name)
                for name in ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES
            )
        )

    def test_strict_policy_rejects_all_compat_attrs(self):
        policy = build_strict_compat_policy()

        self.assertTrue(
            all(
                not policy.allows_deprecated_runtime_internal_attr(name)
                for name in ENTRYPOINT_EXECUTABLE_DEPRECATED_INTERNAL_ATTR_NAMES
            )
        )
        self.assertTrue(
            all(
                not policy.allows_legacy_runtime_compat_attr(name)
                for name in (
                    ENTRYPOINT_EXECUTABLE_LEGACY_CORE_COMPAT_ATTR_NAMES
                    | ENTRYPOINT_EXECUTABLE_LEGACY_FLIP_COMPAT_ATTR_NAMES
                )
            )
        )

    def test_build_compat_policy_clones_template_without_reusing_instance(self):
        template = EntrypointCompatPolicy(
            allow_deprecated_runtime_internal_attrs=False,
            allow_legacy_runtime_compat_attrs=True,
            allow_legacy_flip_runtime_compat_attrs=True,
        )

        policy = build_compat_policy(template=template)

        self.assertEqual(policy, template)
        self.assertIsNot(policy, template)
