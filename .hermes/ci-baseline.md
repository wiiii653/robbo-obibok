# CI Workflow Baseline — Phase 0

Recorded: $(date --iso-8601=seconds)

## Workflow 1: test.yml (Unit suite)

**Trigger:** push/PR modifying `**.py`, `requirements*.txt`, `Makefile`, `test.yml`

**Commands:**
```bash
# Setup
python -m venv venv
./venv/bin/pip install -r requirements.txt

# OS deps
sudo apt-get update && sudo apt-get install -y ffmpeg

# Run
python -m unittest discover -s tests -v
```

**Note:** Runs on ubuntu-latest, Python 3.12. Uses stdlib unittest (not pytest).
`requirements-dev.txt` currently only contains `-r requirements.txt` (no dev extras).

## Workflow 2: test-launchers.yml

**Trigger:** push/PR modifying launcher files

**Commands:**
```bash
# Setup
python -m venv venv
./venv/bin/pip install -r requirements.txt

# Run
./test_launchers.sh   # delegates to ./venv/bin/python3 -m unittest -v \
                      #   tests.test_robbo_obibok_launch \
                      #   tests.test_robbo_obibok_logged_launcher \
                      #   tests.test_runner_smoke \
                      #   tests.test_install_assets
```

## Workflow 3: test-entrypoint-runtime.yml

**Trigger:** push/PR modifying entrypoint/runtime files

**Commands:**
```bash
# Setup
python -m venv venv
./venv/bin/pip install -r requirements.txt

# Run
./venv/bin/python -m unittest -v \
  tests.test_entrypoint_executable_assembly \
  tests.test_entrypoint_launcher \
  tests.test_entrypoint_module_bindings \
  tests.test_robbo_obibok_runtime \
  tests.test_entrypoint_launcher_loader \
  tests.test_entrypoint_launcher_surface \
  tests.test_entrypoint_runtime_surface \
  tests.test_entrypoint_launcher_config \
  tests.test_entrypoint_launcher_state \
  tests.test_runtime_context \
  tests.test_runtime_context_helpers \
  tests.test_install_assets
```

## Workflow 4: integration.yml

**Trigger:** push/PR modifying integration test paths, or workflow_dispatch

**Commands:**
```bash
# Setup
python -m venv venv
./venv/bin/pip install -r requirements.txt

# OS deps
sudo apt-get update && sudo apt-get install -y ffmpeg

# Run
make test-integration   # ./venv/bin/python -m unittest discover -s tests/integration -v
```

**Requires:** `DISCORD_INTEGRATION_TOKEN` secret.

## Local aliases

```bash
make test               # ./venv/bin/python -m unittest discover -s tests/ -v
make test-launchers     # ./test_launchers.sh
make test-integration   # ./venv/bin/python -m unittest discover -s tests/integration -v
```

## Surface map

| Surface | Command | Requires |
|---------|---------|----------|
| Full unit | `python -m unittest discover -s tests -v` | ffmpeg |
| Launcher | `./test_launchers.sh` (4 modules) | — |
| Entrypoint/runtime | `python -m unittest tests.test_entrypoint_* ...` (12 modules) | — |
| Integration | `python -m unittest discover -s tests/integration -v` | Discord token, archives, audio |
