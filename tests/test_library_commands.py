"""Unit tests for library_commands.py."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from library_commands import register_library_commands


class LibraryCommandsStructureTests(unittest.TestCase):
    def test_register_library_commands_callable(self):
        """register_library_commands is callable."""
        self.assertTrue(callable(register_library_commands))
