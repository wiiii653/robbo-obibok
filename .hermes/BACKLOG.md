# Backlog

## Zrobione

- **`PlaySubsongCallable(Protocol)`** — zastąpiono `Callable[..., Awaitable[bool]]` konkretnym
  Protokołem w `runtime_protocols.py`. Gdzie: `playback_service.py`, `session_runtime.py`,
  `entrypoint_callback_groups.py`, `runtime_callback_builders.py`, `runtime_composition.py`.
  Zrobione: 2026-07-01.

## Zrobione

- Refaktor faz 0-6 (MAINTAINABILITY_PLAN.md)
- Bugfix: play_subsong brak 3 keyword args w skip_to_next
- Timeout subprocess: timeout=10 dodany do 16 wywołań w playback_process.py
