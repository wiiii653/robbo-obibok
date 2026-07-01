"""Verify AGENTS.md documentation remains consistent with the repository."""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class AgentsDocConsistencyTests(unittest.TestCase):
    """Read AGENTS.md facts and verify them against the live filesystem.

    This prevents stale numbers and file listings from silently rotting.
    Add a fact to AGENTS.md in a machine-parseable format, then add a test
    here to validate it.
    """

    @staticmethod
    def _agents_md() -> str:
        return (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    # ── Layer file counts ─────────────────────────────────────────────

    LAYER_PATTERNS: dict[str, str] = {
        "domain_*": "domain_",
        "entrypoint_*": "entrypoint_",
        "playback_*": "playback_",
        "bot_*": "bot_",
        "runtime_*": "runtime_",
        "archive_*": "archive_",
        "collection_*": "collection_",
    }

    def test_layer_counts_match_agents_md(self) -> None:
        agents = self._agents_md()
        # Count .py files in src/ (excluding build_* and launcher files)
        src_dir = ROOT / "src"
        all_py = [p.name for p in src_dir.iterdir() if p.suffix == ".py" and not p.name.startswith("build_") and not p.name.startswith("robbo_")]
        for layer, prefix in self.LAYER_PATTERNS.items():
            actual = sum(1 for name in all_py if name.startswith(prefix))
            # Find count in AGENTS.md — look for "| `layer` | N |"
            match = re.search(
                rf"\| `{re.escape(layer)}` \| (\d+) \|",
                agents,
            )
            self.assertIsNotNone(
                match,
                f"Could not find layer count for {layer} in AGENTS.md",
            )
            documented = int(match.group(1))
            self.assertEqual(
                actual,
                documented,
                f"AGENTS.md says {layer} has {documented} files, "
                f"but {actual} exist on disk",
            )

    def test_launcher_count_matches(self) -> None:
        launcher_files = [
            ROOT / "src" / "robbo_obibok_launcher.py",
            ROOT / "src" / "robbo_obibok_logged_launcher.py",
            ROOT / "src" / "robbo_obibok_runtime.py",
            ROOT / "robbo-obibok.py",
            ROOT / "robbo-obibok-strict.py",
            ROOT / "run_bot.sh",
        ]
        actual = sum(1 for f in launcher_files if f.exists())
        match = re.search(r"\| launcher \| (\d+) \|", self._agents_md())
        self.assertIsNotNone(match)
        documented = int(match.group(1))
        self.assertEqual(
            actual,
            documented,
            f"AGENTS.md says launcher has {documented} files, "
            f"but {actual} exist on disk",
        )

    def test_build_tool_count_matches(self) -> None:
        actual = len(list((ROOT / "scripts").glob("build_*_index.py")))
        match = re.search(r"\| Build tools \| (\d+) \|", self._agents_md())
        self.assertIsNotNone(match)
        documented = int(match.group(1))
        self.assertEqual(actual, documented)

    # ── CI / workflows ────────────────────────────────────────────────

    def test_ci_workflow_count_matches(self) -> None:
        agents = self._agents_md()
        headline = re.search(r"(\d+) GitHub Actions workflows:", agents)
        self.assertIsNotNone(headline)
        documented = int(headline.group(1))

        workflow_dir = ROOT / ".github" / "workflows"
        if not workflow_dir.is_dir():
            self.skipTest("CI workflow directory not available")

        actual = len(list(workflow_dir.glob("*.yml")))
        self.assertEqual(actual, documented)

    # ── Requirements files ────────────────────────────────────────────

    def test_requirements_files_exist(self) -> None:
        self.assertTrue((ROOT / "requirements.txt").is_file())
        self.assertTrue((ROOT / "requirements-dev.txt").is_file())

    # ── Docs directory ────────────────────────────────────────────────

    def test_audio_setup_doc_exists(self) -> None:
        self.assertTrue((ROOT / "docs" / "audio-setup.md").is_file())

    # ── Quick reference commands ──────────────────────────────────────

    def test_makefile_targets_referenced_in_agents_are_real(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        agents = self._agents_md()
        for target in ("install", "run", "test", "build-indexes", "clean"):
            self.assertIn(
                f"make {target}",
                agents,
                f"AGENTS.md should reference `make {target}`",
            )
            self.assertIn(
                target,
                makefile,
                f"Makefile should have target `{target}`",
            )
