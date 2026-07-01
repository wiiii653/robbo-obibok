"""Verify that every file referenced in CI workflow configurations exists on disk.

This prevents stale references when modules are renamed or moved during
refactoring. It mirrors the approach used by test_doc_consistency.py for
documentation files.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _collect_workflow_references() -> list[tuple[str, str]]:
    """Parse .github/workflows/*.yml and collect file references.

    Returns list of (workflow_name, referenced_path) tuples from the
    ``paths:`` trigger sections and ``run:`` command lines.
    """
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []

    refs: list[tuple[str, str]] = []
    for wf in sorted(workflows_dir.glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        lines = text.splitlines()
        in_paths = False
        in_run = False
        for line in lines:
            stripped = line.strip()
            if stripped == "paths:":
                in_paths = True
                in_run = False
                continue
            if stripped.startswith("run:"):
                in_run = True
                in_paths = False
                # collect continuation lines that look like module refs
                continue
            if in_paths and stripped.startswith("- "):
                ref = stripped[2:].strip().strip('"').strip("'")
                if ref and not ref.startswith(".") and "/" in ref:
                    refs.append((wf.stem, ref))
            if in_run:
                if stripped.startswith("- ") or stripped.startswith("-  "):
                    # shell command, check for test module references
                    pass
                if stripped.startswith("tests."):
                    # unittest module path → file path
                    module_path = stripped.replace(" ", "").replace("\\", "")
                    file_path = module_path.replace(".", "/") + ".py"
                    refs.append((wf.stem, file_path))
                    continue
                if stripped == "" or stripped.startswith("-"):
                    in_run = False
    return refs


def _collect_trigger_paths() -> list[tuple[str, str]]:
    """Collect file paths from the ``paths:`` trigger sections only."""
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []

    refs: list[tuple[str, str]] = []
    for wf in sorted(workflows_dir.glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        lines = text.splitlines()
        in_paths = False
        for line in lines:
            stripped = line.strip()
            if stripped == "paths:":
                in_paths = True
                continue
            if in_paths and stripped.startswith("- "):
                ref = stripped[2:].strip().strip('"').strip("'")
                if ref and not ref.startswith("."):
                    refs.append((wf.stem, ref))
            if in_paths and not stripped.startswith("- ") and stripped != "":
                in_paths = False
    return refs


class TestWorkflowReferences(unittest.TestCase):
    """Verify every file referenced in CI workflows exists on disk."""

    def _resolve(self, ref: str) -> Path | None:
        """Resolve a workflow reference to an existing path.

        Handles glob patterns (``**``, ``*``) by checking if *any* file
        on disk matches the pattern.
        """
        p = REPO_ROOT / ref
        if p.exists():
            return p
        # glob-style pattern — check if any matching file exists
        if "*" in ref or "?" in ref:
            try:
                matches = list(REPO_ROOT.glob(ref))
                if matches:
                    return matches[0]
            except (ValueError, NotImplementedError):
                # pattern too complex for pathlib
                import fnmatch
                for root, _dirs, files in os.walk(REPO_ROOT):
                    for fname in files + _dirs:
                        rel = os.path.relpath(os.path.join(root, fname), REPO_ROOT)
                        if fnmatch.fnmatch(rel, ref):
                            return Path(root) / fname
        return None

    def test_all_trigger_paths_exist(self):
        """Every path listed in a workflow ``paths:`` section must exist."""
        missing: list[tuple[str, str]] = []
        for wf_name, ref in _collect_trigger_paths():
            resolved = self._resolve(ref)
            if resolved is None:
                missing.append((wf_name, ref))
        if missing:
            msg = "\n".join(f"  {wf}: {ref}" for wf, ref in missing)
            self.fail(f"Missing trigger-path references:\n{msg}")

    def test_test_module_references_exist(self):
        """Every test module name in the ``run:`` section must match a file."""
        workflows_dir = REPO_ROOT / ".github" / "workflows"
        for wf in workflows_dir.glob("*.yml"):
            text = wf.read_text(encoding="utf-8")
            lines = text.splitlines()
            in_run = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("run:"):
                    in_run = True
                    continue
                if in_run and stripped.startswith("tests."):
                    # e.g. "tests.test_entrypoint_executable_assembly"
                    module = stripped.replace(" ", "").replace("\\", "").strip()
                    file_path = module.replace(".", "/") + ".py"
                    resolved = REPO_ROOT / file_path
                    if not resolved.exists():
                        self.fail(
                            f"{wf.name}: test module not found: {module} "
                            f"(expected {file_path})"
                        )
                    continue
                if in_run and (
                    stripped == "" or stripped.startswith("-") or stripped.startswith("env:")
                ):
                    in_run = False


if __name__ == "__main__":
    unittest.main()
