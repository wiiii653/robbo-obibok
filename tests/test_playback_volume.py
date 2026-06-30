"""Tests for playback_volume — volume control module."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import unittest
from unittest.mock import patch, MagicMock
from playback_volume import VolumePolicy, PactlVolumeController


class VolumePolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = VolumePolicy()

    def test_is_valid_accepts_zero(self):
        self.assertTrue(self.policy.is_valid(0))

    def test_is_valid_accepts_200(self):
        self.assertTrue(self.policy.is_valid(200))

    def test_is_valid_rejects_negative(self):
        self.assertFalse(self.policy.is_valid(-1))

    def test_is_valid_rejects_over_200(self):
        self.assertFalse(self.policy.is_valid(201))

    def test_volume_bounds(self):
        self.assertEqual(self.policy.describe_range(), "0–200")


class PactlVolumeControllerTests(unittest.TestCase):
    def setUp(self):
        self.ctrl = PactlVolumeController()

    @patch("subprocess.run")
    def test_get_volume_parses_percentage(self, mock_run):
        mock_run.return_value = MagicMock(stdout="Sink: …\n    Volume: 75% …")
        result = self.ctrl.get_volume("test_sink")
        self.assertEqual(result, 75)
        mock_run.assert_called_once_with(
            ["pactl", "get-sink-volume", "test_sink"],
            capture_output=True, text=True,
        )

    @patch("subprocess.run")
    def test_get_volume_returns_none_on_no_match(self, mock_run):
        mock_run.return_value = MagicMock(stdout="nothing here")
        result = self.ctrl.get_volume("test_sink")
        self.assertIsNone(result)

    @patch("subprocess.run")
    def test_set_volume_calls_pactl(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        self.ctrl.set_volume("test_sink", 50)
        mock_run.assert_called_once_with(
            ["pactl", "set-sink-volume", "test_sink", "50%"],
            capture_output=True,
        )
