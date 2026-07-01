"""Architecture boundary tests for the robbo-obibok project.

These tests enforce the layered architecture:
- ``domain_*`` — pure data models, sync, no IO, no Discord/aiohttp
- Upper layers (entrypoint_*, runtime_*, bot_*, playback_*, archive_*) must
  NOT import from domain_* — dependency flows downward only.
- ``domain_*`` modules must stay synchronous (no asyncio).
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# ── Layer definitions ──────────────────────────────────────────────────────

DOMAIN_MODULES = frozenset({
    "domain_config",
    "domain_context",
    "domain_services",
    "domain_state",
})

UPPER_LAYER_PREFIXES = frozenset({
    "entrypoint",
    "runtime",
    "playback",
    "archive",
    "collection",
    "bot",
})

FORBIDDEN_IN_DOMAIN = frozenset({
    "discord",
    "aiohttp",
    "asyncio",
    "subprocess",
    "threading",
})


def _py_files(root: Path) -> list[Path]:
    """Return all ``.py`` files under ``root``."""
    return sorted(root.rglob("*.py"))


def _module_name(filepath: Path) -> str:
    """Return the dotted module name for a source file, e.g. ``domain_config``."""
    rel = filepath.relative_to(SRC)
    return str(rel.with_suffix("")).replace("/", ".")


def _module_layer(name: str) -> str | None:
    """Return the layer prefix of a module, or ``None`` if not classified."""
    for prefix in list(DOMAIN_MODULES) + list(UPPER_LAYER_PREFIXES):
        if name.startswith(prefix) or name.startswith(f"src.{prefix}"):
            return prefix
    return None


def _parse_imports(filepath: Path) -> list[str]:
    """Return a list of ``(lineno, qualified_name)`` tuples from a file."""
    tree = ast.parse(filepath.read_text(encoding="utf-8"))
    imports: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level is None:
                imports.append((node.lineno, node.module))
            elif node.module and node.level == 0:
                imports.append((node.lineno, node.module))
            # relative imports (level > 0) are ignored for simplicity
    return imports


class ArchitectureTests(unittest.TestCase):
    """Enforce layer boundaries and domain purity."""

    # ── 1. Domain modules must not import upper layers ──────────────────

    def test_domain_does_not_import_upper_layers(self):
        """Forbid entrypoint_*, runtime_*, playback_*, bot_*, archive_*,
        collection_* imports inside domain_* modules."""
        violations: list[tuple[int, str, str]] = []
        for pyfile in _py_files(SRC):
            mod = _module_name(pyfile)
            layer = _module_layer(mod)
            if layer not in DOMAIN_MODULES:
                continue
            for lineno, imported in _parse_imports(pyfile):
                imported_top = imported.split(".")[0]
                if imported_top in UPPER_LAYER_PREFIXES:
                    violations.append((lineno, mod, imported))
        if violations:
            msg = "\n".join(
                f"  L{lineno:>4}  {mod}  imports  {imported}"
                for lineno, mod, imported in violations
            )
            self.fail(f"Domain modules must not import upper layers:\n{msg}")

    # ── 2. Domain modules must be pure: no Discord, asyncio, etc. ────────

    def test_domain_modules_avoid_forbidden_stdlib(self):
        """Forbid ``discord``, ``aiohttp``, ``asyncio``, ``subprocess``,
        ``threading`` in domain modules."""
        violations: list[tuple[int, str, str]] = []
        for pyfile in _py_files(SRC):
            mod = _module_name(pyfile)
            layer = _module_layer(mod)
            if layer not in DOMAIN_MODULES:
                continue
            for lineno, imported in _parse_imports(pyfile):
                imported_top = imported.split(".")[0]
                if imported_top in FORBIDDEN_IN_DOMAIN:
                    violations.append((lineno, mod, imported))
        if violations:
            msg = "\n".join(
                f"  L{lineno:>4}  {mod}  imports  {imported}"
                for lineno, mod, imported in violations
            )
            self.fail(f"Domain modules must avoid forbidden imports:\n{msg}")

    # ── 3. Domain modules must be synchronous ────────────────────────────

    def test_domain_modules_are_synchronous(self):
        """No ``async def`` or ``await`` in domain modules."""
        for pyfile in _py_files(SRC):
            mod = _module_name(pyfile)
            layer = _module_layer(mod)
            if layer not in DOMAIN_MODULES:
                continue
            tree = ast.parse(pyfile.read_text(encoding="utf-8"))
            async_functions = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
                and isinstance(node, ast.AsyncFunctionDef)
            ]
            awaits = [
                node.lineno
                for node in ast.walk(tree)
                if isinstance(node, ast.Await)
            ]
            errors: list[str] = []
            if async_functions:
                errors.append(f"async def: {', '.join(async_functions)}")
            if awaits:
                errors.append(f"await at lines: {awaits}")
            if errors:
                self.fail(f"{mod}: {'; '.join(errors)}")


if __name__ == "__main__":
    unittest.main()
