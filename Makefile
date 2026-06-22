# Robbo Obibok — Makefile
# Targets: install | run | test | clean | build-indexes | help

.PHONY: install run test clean build-indexes help

SHELL := /bin/bash
VENV  := venv
PYTHON := $(VENV)/bin/python3

help:
	@echo "Robbo Obibok — Makefile"
	@echo ""
	@echo "  make install         # Full installation (system deps + venv + indexes)"
	@echo "  make run             # Start the bot (requires DISCORD_BOT_TOKEN)"
	@echo "  make test            # Run unit tests"
	@echo "  make build-indexes   # Build all local track indexes"
	@echo "  make clean           # Remove venv, caches, temp files"
	@echo "  make help            # This message"

install: $(VENV)/bin/activate build-indexes
	@echo "✅ Robbo Obibok ready. Edit config.yaml, set DISCORD_BOT_TOKEN, then: make run"

$(VENV)/bin/activate: requirements.txt
	@echo "📦 Creating Python virtual environment..."
	@python3 -m venv $(VENV)
	@$(VENV)/bin/pip install --quiet --upgrade pip
	@$(VENV)/bin/pip install --quiet -r requirements.txt
	@touch $(VENV)/bin/activate
	@echo "✅ Virtual environment ready"

build-indexes: $(VENV)/bin/activate
	@echo "🏗️  Building local track indexes..."
	@-$(PYTHON) build_ay_index.py 2>/dev/null || echo "  ⚠️  AY index skipped (no archive)"
	@-$(PYTHON) build_ym_index.py 2>/dev/null || echo "  ⚠️  YM index skipped (no archive)"
	@-$(PYTHON) build_tiny_index.py 2>/dev/null || echo "  ⚠️  Tiny index skipped (no archive)"
	@-$(PYTHON) build_snes_index.py 2>/dev/null || echo "  ⚠️  SNES index skipped (no archive)"
	@echo "✅ Indexes built"

run: $(VENV)/bin/activate
	@echo "🎵 Starting Robbo Obibok..."
	@test -n "$(DISCORD_BOT_TOKEN)" || (echo "❌ DISCORD_BOT_TOKEN not set"; exit 1)
	@cd $(CURDIR) && $(PYTHON) -u robbo-obibok.py

test: $(VENV)/bin/activate
	@echo "🧪 Running tests..."
	@cd $(CURDIR) && $(PYTHON) -m pytest tests/ -v --tb=short 2>/dev/null \
		|| $(PYTHON) -m unittest discover -s tests/ -v

clean:
	@echo "🧹 Cleaning..."
	@rm -rf $(VENV) __pycache__ */__pycache__ .pytest_cache
	@rm -f *.log *.pid *cache*.json
	@rm -rf temp_sap_* asma_bot_*
	@echo "✅ Clean"
