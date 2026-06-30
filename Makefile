# Robbo Obibok — Makefile
# Targets: install | run | test | test-integration | test-launchers | clean | build-indexes | help

.PHONY: install run run-strict test test-integration test-launchers clean build-indexes help

SHELL := /bin/bash
VENV  := venv
PYTHON := $(VENV)/bin/python3
DEV_STAMP := $(VENV)/.dev-installed

help:
	@echo "Robbo Obibok — Makefile"
	@echo ""
	@echo "  make install         # Full installation (system deps + venv + indexes)"
	@echo "  make install-dev     # Install dev dependencies (pytest)"
	@echo "  make run             # Start the bot (reads .env when present)"
	@echo "  make run-strict      # Start the bot in strict compatibility mode"
	@echo "  make test            # Run unit tests"
	@echo "  make test-integration # Run real dependency integration tests"
	@echo "  make test-launchers  # Run launcher smoke tests"
	@echo "  make build-indexes   # Build all local track indexes"
	@echo "  make clean           # Remove venv, caches, temp files"
	@echo "  make help            # This message"

install: $(VENV)/bin/activate build-indexes
	@echo "✅ Robbo Obibok ready. Set DISCORD_BOT_TOKEN in .env or the shell, then: make run"

$(VENV)/bin/activate: requirements.txt
	@echo "📦 Creating Python virtual environment..."
	@python3 -m venv $(VENV)
	@$(VENV)/bin/pip install --quiet --upgrade pip
	@$(VENV)/bin/pip install --quiet -r requirements.txt
	@touch $(VENV)/bin/activate
	@echo "✅ Virtual environment ready"

$(DEV_STAMP): $(VENV)/bin/activate requirements-dev.txt
	@$(VENV)/bin/pip install --quiet -r requirements-dev.txt
	@touch $(DEV_STAMP)

build-indexes: $(VENV)/bin/activate
	@echo "🏗️  Building local track indexes..."
	@-$(PYTHON) build_asma_index.py 2>/dev/null || echo "  ⚠️  ASMA index skipped (no archive)"
	@-$(PYTHON) build_hvsc_index.py 2>/dev/null || echo "  ⚠️  HVSC index skipped (no archive)"
	@-$(PYTHON) build_ay_index.py 2>/dev/null || echo "  ⚠️  AY index skipped (no archive)"
	@-$(PYTHON) build_ym_index.py 2>/dev/null || echo "  ⚠️  YM index skipped (no archive)"
	@-$(PYTHON) build_tiny_index.py 2>/dev/null || echo "  ⚠️  Tiny index skipped (no archive)"
	@-$(PYTHON) build_snes_index.py 2>/dev/null || echo "  ⚠️  SNES index skipped (no archive)"
	@echo "✅ Indexes built"

run: $(VENV)/bin/activate
	@echo "🎵 Starting Robbo Obibok..."
	@cd $(CURDIR) && ./run_bot.sh

run-strict: $(VENV)/bin/activate
	@echo "🎵 Starting Robbo Obibok in strict compatibility mode..."
	@cd $(CURDIR) && ROBBO_STRICT_COMPAT=1 ./run_bot.sh

install-dev: $(DEV_STAMP)
	@echo "✅ Development dependencies installed (pytest, etc.)"

test-launchers: $(VENV)/bin/activate
	@echo "🧪 Running launcher smoke tests..."
	@cd $(CURDIR) && ./test_launchers.sh

test: $(DEV_STAMP)
	@echo "🧪 Running tests..."
	@cd $(CURDIR) && $(PYTHON) -m unittest discover -s tests/ -v

test-integration: $(VENV)/bin/activate
	@echo "Running real dependency integration tests..."
	@cd $(CURDIR) && $(PYTHON) -m unittest discover -s tests/integration -v

clean:
	@echo "🧹 Cleaning..."
	@rm -rf $(VENV) __pycache__ */__pycache__ .pytest_cache
	@rm -f *.log *.pid *cache*.json
	@rm -rf temp_sap_* asma_bot_*
	@echo "✅ Clean"
