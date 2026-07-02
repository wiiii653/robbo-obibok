# Contributing

## Setup
1. `cp .env.example .env` and fill in `DISCORD_BOT_TOKEN`
2. `make install`
3. `make install-dev`

## Running
- `make run` — starts the bot
- Requires: PulseAudio null-sink named `asma_bot`, Audacious headless

## Testing
- `make test` — runs all unit tests
- `make lint` — ruff check
- Keep coverage ≥ 70%

## Code Style
- Type hints everywhere (no `Any` where avoidable)
- Async-first for I/O
- No `exec`/`eval`, no bare `except:`
- `from __future__ import annotations` in every file

## Pull Requests
1. Branch from `main`
2. Add tests for new functionality
3. Ensure `make test` and `make lint` pass
4. Keep commits small and descriptive
