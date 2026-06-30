# Baseline Test Results — Phase 0

Date: 2026-06-30
Branch: refactor/maintainability-phase-0
Python: 3.11.15
Bot running: PID 466649 (active)

## Surface Results

### Full unit suite (`python -m unittest discover -s tests/ -v`)
**200 tests, 12 errors, 2 skipped — 186 pass**

| Result | Count | Details |
|--------|-------|---------|
| ✅ Pass | 186 | All non-lock, non-integration tests |
| ❌ Error | 12 | Lock contention with running bot PID 466649 |
| ⏭️ Skip | 2 | Integration preconditions (token, env var) |

### Launcher suite (`./test_launchers.sh`)
**27 tests, 0 errors, 0 skipped — 27 pass**

### Entrypoint/runtime suite (CI command)
**~80 tests, 7 errors** — note: 3 test modules don't exist on this branch

## Error Classification

### 12 Lock contention errors (test-isolation defect — Phase 1 target)
All via `runtime_bootstrap.py:acquire_process_lock` → `BlockingIOError` → `SystemExit`

- `test_command_behavior` (8 tests):
  - `test_favplay_builds_queue_and_starts_monitoring`
  - `test_flip_advances_to_next_collection`
  - `test_play_current_track_reports_handler_exception`
  - `test_play_does_not_schedule_monitor_when_startup_playback_fails`
  - `test_play_numeric_query_uses_targeted_playback_session`
  - `test_refresh_reports_missing_asma_cache`
  - `test_snes_search_populates_results_and_sends_listing`
  - `test_switch_collection_flip_failure_keeps_previous_mode`

- `test_runtime_context_helpers` (4 tests):
  - `test_command_test_context_uses_isolated_runtime_snapshot`
  - `test_isolated_command_runtime_swaps_mutable_registries`
  - `test_scoped_helpers_restore_runtime_state`
  - `test_with_overrides_returns_replaced_context`

Root cause: `get_runtime_test_context()` → `load_live_runtime_bundle()` → `build_live_runtime_bundle()` calls `initialize_runtime()` which acquires the process lock from `runtime_bootstrap.py:129`. The lock file path is the production path (`obibok.pid`), not injected.

### 3 Missing test modules (CI config defect)
The `test-entrypoint-runtime.yml` workflow lists these modules that **do not exist** in the repo:
- `tests.test_entrypoint_runtime_surface`
- `tests.test_entrypoint_launcher_config`
- `tests.test_entrypoint_launcher_state`

These would cause CI failure on any push/PR touching the trigger paths.

### 2 Skipped integration tests (environment requirement)
- `test_discord_token_authenticates` — needs `DISCORD_INTEGRATION_TOKEN`
- `test_live_audio_services_are_reachable` — needs `RUN_LIVE_AUDIO_INTEGRATION=1`

These are correct — they require host services.

## Surface Map (updated)

| Surface | Command | Tests | Pass | Fail | Skip | Requires |
|---------|---------|-------|------|------|------|----------|
| Full unit | `python -m unittest discover -s tests -v` | 200 | 186 | 12* | 2 | ffmpeg |
| Launcher | `./test_launchers.sh` | 27 | 27 | 0 | 0 | venv |
| Entrypoint/runtime | CI explicit modules | 80 | 73 | 7† | 0 | venv |
| Integration | `make test-integration` | 2 | 0 | 0 | 2 | Discord token, archives, audio |

\* All 12 = lock contention with running bot. Zero product defects found.
† 4 lock + 3 missing modules (CI config defect, not a runtime issue)
