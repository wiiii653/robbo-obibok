"""Unit tests for playback_commands.py — Discord command definitions."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robbo_obibok.playback_commands import register_playback_commands


class PlaybackCommandsStructureTests(unittest.TestCase):
    def test_register_playback_commands_callable(self):
        """register_playback_commands is a callable function."""
        self.assertTrue(callable(register_playback_commands))


class PlaybackCommandsRegistrationTests(unittest.TestCase):
    def test_commands_registered_on_bot(self):
        """register_playback_commands attaches commands to a mock bot."""
        from unittest.mock import MagicMock
        mock_bot = MagicMock()
        mock_bot.command = MagicMock()
        register_playback_commands(mock_bot, MagicMock())
        self.assertGreater(
            mock_bot.command.call_count, 3,
            f"Expected >3 commands, got {mock_bot.command.call_count}",
        )
