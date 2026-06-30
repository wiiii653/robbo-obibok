# Robbo Obibok — AGENTS.md

## Project Identity

Robbo Obibok is a Discord chiptune radio bot. It plays SID, SAP, YM, AY, SPC, MOD and other chiptune formats using Audacious as the playback backend. All collections are stored locally — zero HTTP requests during playback.

Key facts:
- **Language**: Python 3.11+
- **Runtime deps**: `discord.py[voice]`, `PyNaCl`, `aiohttp`, `PyYAML`
- **Playback backend**: Audacious + virtual sink (pulseaudio)
- **Collections**: 7 local archives — ASMA (6.3k), HVSC (60.8k), ModArchive (120k+), AY (4.5k), YM (7.2k), Tiny Music (418), SNES SPC (60k)
- **Test suite**: 186/198 passing (12 fails = flock conflict with live bot). On CI all 198 pass.
- **CI**: 5 workflows (test, integration, launchers, entrypoint-runtime, typecheck)
- **Build**: `make install` sets up venv + indexes

## Architecture

```
domain_*          — pure data models (no IO, no Discord, no asyncio)
entrypoint_*      — DI / IoC / composition root
playback_*        — playback domain logic (Audacious, queue, monitoring)
runtime_*         — runtime wiring and service facades
bot_*             — Discord bot event loop and runtime
archive_*         — archive abstraction layer
collection_*      — collection definitions and specs
```

### Layer Map

| Layer | Files | Responsibility |
|---|---|---|
| `domain_*` | 4 | Config, state, stores, services. Zero dependencies on Discord or asyncio. |
| `entrypoint_*` | 15 | Lazy assembly, DI, mutable state hub, callback groups. |
| `playback_*` | 8 | Audacious control, queue management, monitoring, asset runtime. |
| `bot_*` | 4 | Discord events, bot runtime, command decorator factory. |
| `runtime_*` | 7 | Service facade, composition, bootstrap, protocols, support. |
| `archive_*` | 3 | Archive catalog, runtime config, downloads. |
| `collection_*` | 3 | Collection specs, catalog, service. |
| launcher | 6 | Process launcher, logged launcher, executable targets, shell shim. |
| Build tools | 7 | `build_*_index.py` — index rebuilders for each collection. |

### File Topology

```
robbo-obibok.py                  ← executable target (default mode)
robbo-obibok-strict.py           ← executable target (strict mode)
robbo_obibok_launcher.py         ← process launcher
robbo_obibok_logged_launcher.py  ← logging supervision launcher
robbo_obibok_runtime.py          ← launcher runtime wiring
run_bot_logged.py                ← compat entrypoint for logged launcher

domain_state.py                  ← PlaylistState, AppRuntimeState, stores
domain_config.py                 ← AppConfig, PlaybackConfig, PathConfig
domain_context.py                ← AppContext, ArchiveRegistryViews, BootstrappedApp, bootstrap_app()
domain_services.py               ← AppServices (facade over stores)

entrypoint_app.py                ← EntrypointApp assembly, EntrypointFacade
entrypoint_bootstrap.py          ← EntrypointBootstrapBuilder, EntrypointResources, lazy config
entrypoint_state.py              ← EntrypointState (mutable state hub), Protocol contracts
entrypoint_components.py         ← Component graph assembly
entrypoint_callback_groups.py    ← Callback group definitions
entrypoint_glue.py               ← EntrypointGlue (bridges resources → callbacks)
entrypoint_runtime.py            ← Runtime initializer
entrypoint_runtime_tasks.py      ← Monitor, health watchdog, metadata background
entrypoint_runtime_surface.py    ← Runtime surface for compat exports
entrypoint_startup.py            ← Orphan cleanup, config loading
entrypoint_module.py             ← EntrypointModule for surface assembly
entrypoint_module_bindings.py    ← Surface alias specs
entrypoint_launcher_loader.py    ← EntrypointSupport (launcher scaffolding)
entrypoint_executable_assembly.py ← Full executable assembly
entrypoint_surface_assembly.py   ← Compat registry builders
```

## Code Conventions

### Typing

- Use `from __future__ import annotations` in every file.
- Use `@dataclass(slots=True)` for all data containers — avoid `__init__` where `@dataclass` suffices.
- Use `Protocol` for interface contracts. Prefer Protocols over ABCs.
- Use `TYPE_CHECKING` for import guards on type-only imports. No circular imports.
- Use `Mapping` / `Iterable` (read-only views) in public interfaces, `dict` / `list` internally.
- Only 1 `# type: ignore` / `# noqa` across the whole codebase (~12.8k lines).

### Patterns

- **Lazy initialization**: `EntrypointBootstrapBuilder` caches with `_field: T | None = None` + property getter.
- **State hub**: `EntrypointState` is the single mutable container. Consumers depend on focused `Protocol` contracts, not on the concrete class.
- **Bulk mutation**: Use `apply_bootstrap_registry()` / `apply_runtime_components()` / `cache_initialized_app()` for multi-field updates instead of individual setters.
- **Callbacks**: Grouped in `AppEntrypointCallbacks` — `PlaybackEntrypointCallbacks`, `LibraryEntrypointCallbacks`, `CollectionEntrypointCallbacks`, `BootstrapEntrypointCallbacks`.

### Imports

- Standard library first, then third-party, then local.
- Local imports grouped by layer: `domain_*` before `entrypoint_*` before `playback_*`.
- Avoid `import X` — prefer `from X import Y` for clarity.

## How To: Add a New Collection

1. Define a `CollectionInfo` entry in `archive_catalog.py` (or add to existing catalog).
2. Add collection spec in `collection_specs.py`.
3. Create `build_*_index.py` script that generates the cache JSON.
4. Wire into `EntrypointResources` in `entrypoint_bootstrap.py` if it needs special playback config.
5. Add emoji + label in `playback_commands.py` (`mode_labels` dict + help text).
6. Add command alias in `playback_commands.py` (the `@bot.command` decorator).
7. Add a `flip_ready_msg` and `already_msg` in `collection_catalog.py`.

## How To: Add a Command

1. Add the command function in `playback_commands.py` (monolith by design — easy to grep).
2. If the command needs callbacks beyond what exists, extend the relevant `*EntrypointCallbacks` group in `entrypoint_callback_groups.py`.
3. Wire the callback into the assembly in `entrypoint_app.py`.
4. Add test coverage in `tests/test_command_behavior.py`.
5. Add help text entry in the `!help` embed dict (around line 340 in `playback_commands.py`).

## Testing

- **Framework**: `unittest` (stdlib) + `pytest` runner.
- **Location**: `tests/` directory, one file per module or functional area.
- **Mocking**: Prefer `unittest.mock` over `pytest.monkeypatch`. Use `types.SimpleNamespace` for lightweight fakes.
- **Fixtures**: In `tests/test_entrypoint_launcher_fixtures.py`, `tests/test_entrypoint_module_fixtures.py`.
- **Smoke tests**: `tests/test_runner_smoke.py` (735 lines) exercises the full assembly stack.
- **Launcher tests**: `make test-launchers` — the standalone script alias is `./test_launchers.sh`.
  - The launcher smoke CI surface is `.github/workflows/test-launchers.yml`.
  - The broader entrypoint/runtime CI surface is `.github/workflows/test-entrypoint-runtime.yml`.
- **Integration**: `tests/test_real_services.py` — requires real archives on disk.

## Launcher Contract

- `robbo_obibok_launcher.py` is the canonical process launcher for local entrypoint scripts.
- `run_bot.sh` is a minimal shell shim that delegates to `robbo_obibok_launcher.py`.
- `run_bot_logged.py` may add logging behavior, but it must reuse launcher helpers instead of reimplementing:
  - `.env` loading
  - `DISCORD_BOT_TOKEN` validation
  - strict compatibility mode selection
  - final entry command construction
- `robbo_obibok_launcher.py` owns default vs strict executable target selection.
- `robbo-obibok.py` and `robbo-obibok-strict.py` are the canonical executable targets.
- Systemd units should point at those executable targets directly, not reconstruct launch logic with env-only switching.
- `robbo_obibok_logged_launcher.py` remains separate on purpose. It adds log-file process supervision behavior, which is distinct from plain launcher execution and should stay thin rather than being merged back into `robbo_obibok_launcher.py`.

### Launcher File Map

| File | Role |
|---|---|
| `robbo_obibok_launcher.py` | Process launcher + target selection |
| `robbo_obibok_logged_launcher.py` | logging-oriented launcher module |
| `robbo_obibok_runtime.py` | Launcher runtime wiring |
| `robbo-obibok.py` | Default executable target |
| `robbo-obibok-strict.py` | Strict compat executable target |
| `run_bot_logged.py` | Compat entrypoint for logged launcher |
| `run_bot.sh` | Minimal shell shim |

### Boundary Notes

- `entrypoint_bootstrap.py` loads `.env` for application/config bootstrap. That is separate from process-launch selection and not launcher duplication.
- Token validation happens at runtime in `entrypoint_launcher_loader.py` / `robbo_obibok_runtime.py` — not in the launcher itself.

### Test Surface

- Use `make test-launchers` for the focused launcher smoke suite.
- The standalone script alias is `./test_launchers.sh`.
- The launcher smoke CI surface is `.github/workflows/test-launchers.yml`.
- The broader entrypoint/runtime CI surface is `.github/workflows/test-entrypoint-runtime.yml`.

## Git Conventions

- **Branch names**: `category/topic` — `refactor/`, `fix/`, `polish/`, `feature/`.
- **Commits**: Imperative present tense, e.g. "absorb runner into entrypoint_app".
- **Merge commits**: Include a summary + test results.
- **Cleanup**: Delete branches after merge. Stale WIP branches older than 2 weeks should be reviewed or pruned.

## CI/CD

5 GitHub Actions workflows:
| Workflow | Trigger | Scope |
|---|---|---|
| `test.yml` | push, PR | All unit tests |
| `integration.yml` | push to main | Real dependency tests |
| `test-launchers.yml` | push, PR | Launcher smoke tests |
| `test-entrypoint-runtime.yml` | push, PR | Entrypoint + runtime tests |
| `typecheck.yml` | push, PR | Mypy static type analysis (requires `pip install mypy`) |

## Quick Reference

```bash
make install          # Full setup (venv + indexes)
make run              # Start bot
make test             # Run tests
make build-indexes    # Rebuild all track indexes
make clean            # Remove venv + caches

pytest tests/ -q --tb=short                  # Quick test run
pytest tests/test_command_behavior.py -q     # Command tests only
pytest tests/test_install_assets.py -q       # Asset consistency checks
python -c 'from domain_state import AppRuntimeState'  # Verify imports
```
