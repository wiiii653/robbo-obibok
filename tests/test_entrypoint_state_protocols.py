import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_support import install_discord_stubs


install_discord_stubs()

import entrypoint_app
import entrypoint_components
import entrypoint_resources
import entrypoint_runtime_surface
from entrypoint_state import (
    EntrypointComponentAccessStateProtocol,
    EntrypointComponentAssemblyStateProtocol,
)


class EntrypointStateProtocolTests(unittest.TestCase):
    def test_protocols_are_not_reexported_from_consumer_modules(self):
        self.assertFalse(hasattr(entrypoint_app, "EntrypointComponentStateProtocol"))
        self.assertFalse(hasattr(entrypoint_components, "EntrypointComponentStateProtocol"))
        self.assertFalse(hasattr(entrypoint_resources, "EntrypointResourceStateProtocol"))
        self.assertFalse(hasattr(entrypoint_runtime_surface, "EntrypointRuntimeStateProtocol"))

    def test_component_assembly_and_access_contracts_are_distinct(self):
        self.assertIsNot(EntrypointComponentAssemblyStateProtocol, EntrypointComponentAccessStateProtocol)


if __name__ == "__main__":
    unittest.main()
