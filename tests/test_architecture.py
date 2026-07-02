"""Architecture boundary tests for the robbo-obibok project.

These tests enforce the layered architecture:
- Every ``domain_*`` module is classified as pure or explicitly exempt.
- Pure domain modules must not import runtime, bot, playback, or IO layers.
- ``domain_*`` modules must stay synchronous (no asyncio).
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# These modules contain deterministic data/configuration logic and must stay
# independent from IO frameworks. Runtime-facing session and service adapters
# are intentionally excluded.
PURE_DOMAIN_MODULES = frozenset({
    "domain_archive_config",
    "domain_collection_state",
    "domain_config",
    "domain_queue_state",
    "domain_state",
})

EXEMPT_DOMAIN_MODULES = {
    "domain_guild_session": "holds asyncio task handles owned by a Discord guild session",
}

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
    basename = name.rsplit(".", 1)[-1]
    for prefix in list(PURE_DOMAIN_MODULES) + list(UPPER_LAYER_PREFIXES):
        if basename.startswith(prefix):
            return prefix
    return None


def _parse_imports(filepath: Path) -> list[tuple[int, str]]:
    """Return a list of ``(lineno, qualified_name)`` tuples from a file."""
    tree = ast.parse(filepath.read_text(encoding="utf-8"))
    imports: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


class ArchitectureTests(unittest.TestCase):
    """Enforce layer boundaries and domain purity."""

    def test_all_domain_modules_are_classified(self):
        discovered = {
            pyfile.stem
            for pyfile in (SRC / "robbo_obibok").glob("domain_*.py")
        }
        classified = PURE_DOMAIN_MODULES | EXEMPT_DOMAIN_MODULES.keys()

        self.assertFalse(PURE_DOMAIN_MODULES & EXEMPT_DOMAIN_MODULES.keys())
        self.assertEqual(discovered, classified)
        self.assertTrue(all(EXEMPT_DOMAIN_MODULES.values()))

    # ── 1. Domain modules must not import upper layers ──────────────────

    def test_domain_does_not_import_upper_layers(self):
        """Forbid entrypoint_*, runtime_*, playback_*, bot_*, archive_*,
        collection_* imports inside domain_* modules."""
        violations: list[tuple[int, str, str]] = []
        inspected: set[str] = set()
        for pyfile in _py_files(SRC):
            mod = _module_name(pyfile)
            layer = _module_layer(mod)
            if layer not in PURE_DOMAIN_MODULES:
                continue
            inspected.add(layer)
            for lineno, imported in _parse_imports(pyfile):
                imported_top = imported.split(".")[0]
                if any(imported_top.startswith(p) for p in UPPER_LAYER_PREFIXES):
                    violations.append((lineno, mod, imported))
        if violations:
            msg = "\n".join(
                f"  L{lineno:>4}  {mod}  imports  {imported}"
                for lineno, mod, imported in violations
            )
            self.fail(f"Domain modules must not import upper layers:\n{msg}")
        self.assertEqual(inspected, PURE_DOMAIN_MODULES)

    # ── 2. Domain modules must be pure: no Discord, asyncio, etc. ────────

    def test_domain_modules_avoid_forbidden_stdlib(self):
        """Forbid ``discord``, ``aiohttp``, ``asyncio``, ``subprocess``,
        ``threading`` in domain modules."""
        violations: list[tuple[int, str, str]] = []
        inspected: set[str] = set()
        for pyfile in _py_files(SRC):
            mod = _module_name(pyfile)
            layer = _module_layer(mod)
            if layer not in PURE_DOMAIN_MODULES:
                continue
            inspected.add(layer)
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
        self.assertEqual(inspected, PURE_DOMAIN_MODULES)

    # ── 3. Domain modules must be synchronous ────────────────────────────

    def test_domain_modules_are_synchronous(self):
        """No ``async def`` or ``await`` in domain modules."""
        inspected: set[str] = set()
        for pyfile in _py_files(SRC):
            mod = _module_name(pyfile)
            layer = _module_layer(mod)
            if layer not in PURE_DOMAIN_MODULES:
                continue
            inspected.add(layer)
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
        self.assertEqual(inspected, PURE_DOMAIN_MODULES)


if __name__ == "__main__":
    unittest.main()
