"""Package import and metadata regression tests."""

from __future__ import annotations

import sys
import unittest


class PackagingTests(unittest.TestCase):
    def test_package_imports_do_not_create_flat_module_aliases(self):
        from robbo_obibok import domain_state, robbo_obibok_runtime

        self.assertEqual(domain_state.__name__, "robbo_obibok.domain_state")
        self.assertEqual(robbo_obibok_runtime.__name__, "robbo_obibok.robbo_obibok_runtime")
        self.assertNotIn("domain_state", sys.modules)
        self.assertNotIn("entrypoint_app", sys.modules)


if __name__ == "__main__":
    unittest.main()
