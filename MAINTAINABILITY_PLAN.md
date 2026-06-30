# Robbo Obibok Maintainability Plan

## Objective

Reduce maintenance and operational risk without changing playback behavior, the
launcher contract, collection semantics, or the local-only playback model.

This is an incremental hardening operation, not a rewrite. Each phase must leave
the default and strict launchers usable and the relevant test surfaces green.

## Status

| Phase | State |
|---|---|
| 0 — Reproducible baseline | Complete |
| 1 — Process-lock isolation | Complete |
| 2 — Command boundary | Complete |
| 3 — State lifecycle | Complete |
| 4 — Compatibility indirection | Complete |
| 5 — Operational diagnostics | Complete |
| 6 — Dependencies and documentation | Not started |

Change a phase to `In progress` only when its implementation begins. Mark it
`Complete` only after its gate has passed and the validation commands have been
recorded.

## Success Criteria

- Unit tests do not contend with the lock held by a running bot.
- `make test`, `make test-launchers`, and the entrypoint/runtime test surface pass
  without real archives, Discord, Audacious, or network access.
- Default and strict executable targets retain their supported exports and
  startup/shutdown behavior.
- Command registration and help text remain easy to find in
  `playback_commands.py`, while non-Discord policy and system calls are tested
  behind focused interfaces.
- Runtime state mutations occur through explicit lifecycle operations and
  focused protocols.
- Compatibility behavior is represented by one documented export graph; no new
  implicit aliases or fallback paths are introduced.
- Startup failures identify missing external tools and relevant configuration
  directly.
- Documentation describes the repository as it exists; it does not contain
  fixed test totals or file counts that silently become stale.

## Non-Goals

- Replacing Audacious, PulseAudio/PipeWire, or the Discord library.
- Changing command names, collection order, queue semantics, or user-visible
  playback behavior.
- Removing strict compatibility mode in one step.
- Eliminating `EntrypointState` or the command registry solely to reduce file
  size.
- Introducing a framework or container for dependency injection.
- Adding network access to playback.

## Protected Contracts

The following behavior must be characterized by tests before related code is
changed:

- `run_bot.sh` delegates to `robbo_obibok_launcher.py`.
- `robbo_obibok_launcher.py` selects the default or strict executable target.
- `robbo-obibok.py` and `robbo-obibok-strict.py` remain canonical executable
  targets.
- The logged launcher remains a separate, thin supervision layer.
- `ENTRYPOINT_EXPORT_GRAPH` remains the authority for supported and compatibility
  exports.
- Token validation remains in runtime/bootstrap code, not process-target
  selection.
- Playback uses local collections and performs no HTTP requests while playing.

## Phase 0 — Establish a Reproducible Baseline

1. Record the exact commands used by each CI workflow.
2. Run and classify the unit, launcher, entrypoint/runtime, and integration
   surfaces separately.
3. Add characterization tests for default/strict target selection, supported
   exports, initialization order, and lock release during shutdown.
4. Document which integration tests require archives or host audio services.
5. Add an explicit development setup target and declare `pytest` and any other
   test-only packages in `requirements-dev.txt`; keep runtime requirements
   separate.

Gate: failures are classified as product defects, environment requirements, or
test-isolation defects. No architecture refactoring starts with unexplained
baseline failures.

## Phase 1 — Isolate Process Locks in Tests

1. Identify tests that initialize `runtime_bootstrap` with the repository lock
   path.
2. Inject a temporary runtime root or lock path from each test; never reuse the
   production `obibok.pid`.
3. Ensure lock descriptors and files are released in cleanup paths, including
   failed initialization.
4. Add a regression test that holds the production-style lock while the isolated
   unit suite exercises startup behavior.
5. Keep a focused test proving that two processes cannot acquire the same lock.

Gate: the unit suite passes while a separate process holds the normal bot lock.

## Phase 2 — Clarify the Command Boundary

Keep command declarations, aliases, and help text in `playback_commands.py` for
discoverability. Move implementation details only when they have an independent
responsibility:

1. Extract pure command decisions and payload construction into typed helper
   modules.
2. Route Audacious, `audtool`, and `pactl` calls through focused playback/runtime
   protocols rather than invoking subprocesses from command policy.
3. Keep Discord context and embed formatting at the command edge.
4. Add behavior tests before moving each command family; compare messages,
   embeds, queue changes, and callback calls.
5. Move one coherent command family per change. Do not perform a bulk split.

Gate: command registration remains centralized, command behavior is unchanged,
and extracted logic can be tested without Discord or host binaries.

## Phase 3 — Tighten State Lifecycle Boundaries

1. Inventory every writer to `EntrypointState` and classify it as bootstrap,
   runtime initialization, playback mutation, or shutdown.
2. Replace scattered multi-field writes with existing bulk operations, adding a
   new operation only when it represents a real lifecycle transition.
3. Narrow consumer protocols to the fields and methods each consumer needs.
4. Add invariant checks for required bootstrap/runtime state before it is read.
5. Add tests for partial initialization, repeated initialization, failed startup,
   and idempotent shutdown.

Gate: lifecycle transitions are explicit and tested; ordinary consumers do not
depend on the concrete `EntrypointState`.

## Phase 4 — Reduce Entrypoint Compatibility Indirection

1. Inventory each legacy and compatibility export, its consumers, and its test
   coverage.
2. Make `ENTRYPOINT_EXPORT_GRAPH` the single declarative source for names and
   resolution policy.
3. Prefer explicit stable bindings over dynamic fallback for internal callers.
4. Prevent new compatibility aliases unless a documented external consumer
   requires them.
5. Remove a compatibility path only after repository usage is gone and both
   executable targets have characterization coverage.
6. Simplify one resolver or assembly boundary at a time; do not combine this
   phase with command or state refactors.

Gate: supported exports and strict mode remain unchanged, while internal runtime
paths no longer depend on deprecated fallback resolution.

## Phase 5 — Improve Operational Diagnostics

1. Keep the external-tool inventory centralized and test its error output.
2. Distinguish required-at-startup tools from format-specific tools where runtime
   behavior permits it.
3. Report the failed component, command, exit status, and actionable remedy for
   subprocess failures without exposing secrets.
4. Document PipeWire/PulseAudio sink expectations and a read-only preflight
   procedure.
5. Verify graceful shutdown cleans players, temporary extraction directories,
   and the process lock.

Gate: a clean host reports missing prerequisites before connecting to Discord,
and shutdown cleanup is covered independently of a live Discord session.

## Phase 6 — Dependency and Documentation Hygiene

1. Keep bounded runtime requirements in `requirements.txt` and explicit test
   tooling in `requirements-dev.txt`.
2. Choose and document a reproducibility mechanism before introducing a lock
   file; do not hand-edit generated lock data.
3. Remove volatile test totals and file counts from maintained documentation.
4. Verify the architecture map, workflow list, launcher map, and quick-reference
   commands against the repository.
5. Add a lightweight documentation-consistency check where it can validate facts
   mechanically.

Gate: a fresh development environment can install and run the offline unit suite
from documented commands.

## Change Protocol

For every implementation change:

1. State the behavior being preserved and the specific risk being reduced.
2. Add or identify characterization coverage before moving a boundary.
3. Keep the patch within one phase and one responsibility.
4. Run focused tests first, then the launcher and full offline unit surfaces.
5. Record commands and results in the commit or pull-request description.
6. Stop and update this plan if preserving a protected contract requires a
   materially different design.

## Recommended Change Sequence

1. Establish and classify the baseline; make development dependencies explicit.
2. Isolate process locks in tests.
3. Extract one command family as a boundary proof.
4. Inventory state writers and tighten lifecycle mutations.
5. Inventory compatibility consumers and simplify resolver paths.
6. Improve runtime preflight, subprocess diagnostics, and cleanup coverage.
7. Reconcile dependency and architecture documentation with the final state.

This ordering removes false test failures before architectural work and postpones
compatibility changes until launcher behavior and state transitions are
characterized.

## Validation Matrix

| Change area | Required focused checks | Required regression checks |
|---|---|---|
| Locks/startup | `tests/test_startup_environment.py` | full offline unit suite |
| Commands | relevant command behavior tests | command registration and help tests |
| State | `tests/test_entrypoint_state.py` | entrypoint/runtime tests |
| Compatibility | binding, loader, and launcher tests | default and strict launcher smoke tests |
| Playback process | playback process/runtime tests | startup and graceful-shutdown tests |
| Dependencies/docs | asset/config tests | fresh-environment CI job |

Real-service integration tests remain a separate gate because they require local
archives and host services. They must not be silently treated as unit tests.
