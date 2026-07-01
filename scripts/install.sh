#!/usr/bin/env bash
# Robbo Obibok — Installation Script
# Run: bash install.sh
# Supports: Ubuntu/Debian, Arch Linux

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
step()  { echo -e "\n${BOLD}[$1/$TOTAL]${NC} $2"; }

TOTAL=7

# ── Detect OS ──────────────────────────────────────────────────
step 1 "Detecting operating system..."
if command -v apt &>/dev/null; then
    OS="debian"
    info "Detected: Ubuntu/Debian"
elif command -v pacman &>/dev/null; then
    OS="arch"
    info "Detected: Arch Linux"
else
    error "Unsupported OS. Only Ubuntu/Debian and Arch Linux are supported."
    exit 1
fi

# ── Install system dependencies ─────────────────────────────────
step 2 "Installing system dependencies..."

if [ "$OS" = "debian" ]; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-venv python3-pip \
        audacious audacious-plugins \
        ffmpeg pipewire-pulse \
        sidplayfp libopenmpt-dev \
        unrar curl wget p7zip-full \
        git 2>/dev/null
elif [ "$OS" = "arch" ]; then
    sudo pacman -S --noconfirm --needed \
        python python-virtualenv python-pip \
        audacious audacious-plugins \
        ffmpeg pipewire pipewire-pulse \
        sidplayfp libopenmpt \
        unrar curl wget p7zip \
        git 2>/dev/null
fi
info "System dependencies installed"

# ── Clone / update repository ──────────────────────────────────
step 3 "Setting up repository..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$HOME/robbo-obibok"

if [ "$SCRIPT_DIR" != "$REPO_DIR" ]; then
    if [ -d "$REPO_DIR" ]; then
        warn "Directory $REPO_DIR already exists, using it"
    else
        info "Cloning repository..."
        git clone git@github.com:wiiii653/robbo-obibok.git "$REPO_DIR"
    fi
    cd "$REPO_DIR"
else
    cd "$SCRIPT_DIR"
fi

# ── Create virtual environment ──────────────────────────────────
step 4 "Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    info "Virtual environment created"
else
    info "Virtual environment already exists"
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
info "Python dependencies installed"

# ── Configure ───────────────────────────────────────────────────
step 5 "Configuration..."
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# Discord bot token — get from https://discord.com/developers/applications
DISCORD_BOT_TOKEN="your-token-here"
EOF
    warn "Edit .env and set your DISCORD_BOT_TOKEN"
else
    info ".env exists"
fi

if [ ! -f "config.yaml" ]; then
    warn "config.yaml missing from repository checkout"
else
    info "config.yaml exists"
fi

# ── Build local indexes ─────────────────────────────────────────
step 6 "Building local track indexes..."
for script in \
    scripts/build_asma_index.py \
    scripts/build_hvsc_index.py \
    scripts/build_ay_index.py \
    scripts/build_ym_index.py \
    scripts/build_tiny_index.py \
    scripts/build_snes_index.py; do
    if [ -f "$script" ]; then
        python3 "$script" 2>/dev/null && info "$script: OK" || warn "$script: skipped (no archive)"
    fi
done

# ── Setup systemd service ───────────────────────────────────────
step 7 "Systemd service..."
SERVICE_FILES=("robbo-obibok.service" "robbo-obibok-strict.service")
INSTALLED_SERVICE_NAMES=()
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
for SERVICE_SRC in "${SERVICE_FILES[@]}"; do
    if [ -f "$SERVICE_SRC" ]; then
        cp "$SERVICE_SRC" "$SERVICE_DIR/"
        INSTALLED_SERVICE_NAMES+=("$SERVICE_SRC")
    fi
done

if [ "${#INSTALLED_SERVICE_NAMES[@]}" -gt 0 ]; then
    if ! systemctl --user daemon-reload; then
        warn "Could not reload the user systemd manager; run systemctl --user daemon-reload after login"
    fi
    info "Service files installed: ${INSTALLED_SERVICE_NAMES[*]}"
    info "Enable one of them with:"
    echo "  systemctl --user enable --now robbo-obibok.service"
    echo "  systemctl --user enable --now robbo-obibok-strict.service"
else
    warn "No service files found, skipping"
fi

echo ""
echo -e "${GREEN}${BOLD}✅ Robbo Obibok installed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit .env — set your DISCORD_BOT_TOKEN"
echo "  2. Edit config.yaml — set guild_id for single-server mode"
echo "  3. make run        # Start via the shared launcher"
echo "     make run-strict # Start via the shared launcher in strict compatibility mode"
echo "  4. systemctl --user enable --now robbo-obibok.service"
echo "     systemctl --user enable --now robbo-obibok-strict.service"
echo ""
echo "Join a voice channel and type !play to start!"
