# Launcher Contract

- `robbo_obibok_launcher.py` is the canonical process launcher for local entrypoint scripts.
- `run_bot.sh` must stay a minimal shell shim that delegates to `robbo_obibok_launcher.py`.
- `run_bot_logged.py` may add logging behavior, but it must reuse launcher helpers instead of reimplementing:
  - `.env` loading
  - `DISCORD_BOT_TOKEN` validation
  - strict compatibility mode selection
  - final entry command construction
- `robbo_obibok_launch.py` owns default vs strict executable target selection.
- `robbo-obibok.py` and `robbo-obibok-strict.py` are the canonical executable targets.
- Systemd units should point at those executable targets directly, not reconstruct launch logic with env-only switching.
- Launcher family naming:
  - `robbo_obibok_launch.py`: target-selection helpers
  - `robbo_obibok_launcher.py`: process launcher
  - `run_bot.sh`: minimal shell shim
  - `robbo_obibok_logged_launcher.py`: logging-oriented launcher module
  - `run_bot_logged.py`: compatibility entrypoint for the logged launcher module

# Boundary Notes

- `entrypoint_bootstrap.py` still loads `.env` for application/config bootstrap. That is separate from process-launch selection and should not be treated as launcher duplication by itself.
- `boot_runtime.py` still validates that a bot token exists when startup state is initialized. That is runtime guard logic, not a replacement for launcher validation.
- `robbo_obibok_logged_launcher.py` remains separate on purpose. It adds log-file process supervision behavior, which is distinct from plain launcher execution and should stay thin rather than being merged back into `robbo_obibok_launcher.py`.

# Test Surface

- Use `make test-launchers` for the focused launcher smoke suite.
- The standalone script alias is `./test_launchers.sh`.
- The launcher smoke CI surface is `.github/workflows/test-launchers.yml` and should call `./test_launchers.sh` directly instead of reconstructing the launcher test list.
- The broader entrypoint/runtime CI surface is `.github/workflows/test-entrypoint-runtime.yml`.
