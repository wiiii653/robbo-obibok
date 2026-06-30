import subprocess
import unittest
from unittest.mock import patch

from playback_process import move_playback_to_sink


class PlaybackProcessTests(unittest.TestCase):
    def test_move_playback_to_sink_uses_argument_lists(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            if command[:3] == ["pactl", "list", "sink-inputs"]:
                return subprocess.CompletedProcess(command, 0, stdout="12 sink-a\ninvalid\n34 sink-b\n")
            return subprocess.CompletedProcess(command, 0)

        with patch("playback_process.subprocess.run", side_effect=run):
            move_playback_to_sink("safe_sink")

        self.assertEqual(
            [call[0] for call in calls],
            [
                ["pactl", "list", "sink-inputs", "short"],
                ["pactl", "move-sink-input", "12", "safe_sink"],
                ["pactl", "move-sink-input", "34", "safe_sink"],
            ],
        )
        self.assertTrue(all("shell" not in kwargs for _command, kwargs in calls))
