```
__________      ___.  ___.            ________ ___.   ._____.           __   
\______   \ ____\_ |__\_ |__   ____   \_____  \\_ |__ |__\_ |__   _____/  |_ 
 |       _//  _ \| __ \| __ \ /  _ \   /   |   \| __ \|  || __ \ /  _ \   __\
 |    |   (  <_> ) \_\ \ \_\ (  <_> ) /    |    \ \_\ \  || \_\ (  <_> )  |  
 |____|_  /\____/|___  /___  /\____/  \_______  /___  /__||___  /\____/|__|  
        \/           \/    \/                 \/    \/        \/              
```

# Robbo Obibot — The Ultimate Chiptune Bot

Named after a fusion of the 1989 Polish Atari classic *Robbo* and the avant-garde jazz band *Robotobibok*, this specialized Discord bot streams vintage retro chipmusic. Blending intricate technical grooves with retro charm, Robbo plays from **seven collections** spanning Atari, C64, ZX Spectrum, Amiga, SNES, and beyond.

**Join a voice channel, type `!play`, and let the chips play.**

## Features

- 🎵 **Seven collections** — switch between ASMA (Atari SAP, 6400+), HVSC (C64 SID, 60 000+), AY (ZX Spectrum, 43 000+), YM (Atari ST, 23 000+), ModArchive (Amiga/PC tracker modules, 120 000+), SNES SPC (RSN), and Tiny Music modules
- 🔀 **Shuffle loop** — never hear the same track twice in a row
- 🎼 **Rich metadata** — track name, composer, copyright from headers
- ❤️ **Favorites playlist** — react to any Now Playing embed to save/remove tracks
- ⏭️ **Skip**, **Stop**, **Now Playing**, **Stats**, **Search**
- 🔄 **Auto-advance** — moves to next track when current ends, with GME-aware monitoring
- 💾 **Queue persistence** — saves/restores queue across restarts
- 📻 **Auto-start** — starts playing when someone joins a configured voice channel
- 🌙 **Auto-stop** — disconnects after channel is empty for a timeout
- 🏥 **Watchdog** — auto-restarts players and PulseAudio sink if they crash
- ⚙️ **Configurable** via `config.yaml`
- 📀 **Local archives** — all collections served from disk, no remote crawling at runtime

## Commands

| Command | Description |
|---------|-------------|
| `!play` / `!radio` | Start shuffled radio from current collection |
| `!play <query>` | Search and play first matching track |
| `!play <number>` | Play a track from last search results |
| `!stop` | Stop playback and disconnect |
| `!skip` / `!next` | Skip to next track |
| `!np` | Show current track info |
| `!stats` | Show radio stats |
| `!search <query>` | Search tracks by name, directory, or author |
| `!flip` / `!switch` / `!toggle` / `!przelacz` | Rotate through all available collections |
| `!status` / `!mode` / `!collection` | Show current collection and queue info |
| `!hvsc` / `!c64` / `!sid` | Switch to **Commodore 64 SID** collection |
| `!asma` | Switch to **Atari SAP** collection |
| `!ay` / `!spectrum` | Switch to **ZX Spectrum AY** collection |
| `!ym` / `!st` | Switch to **Atari ST YM** collection |
| `!mod` / `!modarchive` | Switch to **ModArchive tracker modules** collection |
| `!snes` / `!spc` | Switch to **SNES SPC** collection |
| `!tiny` | Switch to **Tiny Music modules** collection |
| `!favorites` / `!favs` / `!playlista` | Show your reaction-based favorites playlist |
| `!play subsong <number>` | Play a specific subsong from the current track (SID/SAP only) |

### Favorites System

React with **any emoji** to a Now Playing embed to save the track to your favorites. React again to remove it (toggle). Data persists in `favorites.json`.

## Collections

| Collection | Format | Tracks | Source | 
|------------|--------|--------|--------|
| **ASMA** | `.sap` | 6 335 | Local `archiwum/asma/` |
| **HVSC** | `.sid` | 60 811 | Local `archiwum/hvsc/C64Music/` |
| **AY** | `.ay` | 43 480 | Local `archiwum/ay/` |
| **YM** | `.ym` | 23 000+ | Local `archiwum/ym/` |
| **ModArchive** | `.mod`, `.xm`, `.s3m`, `.it` | 120 000+ | Local `archiwum/modarchive_textfiles/` |
| **SNES SPC** | `.spc` | 40 000+ | Local `archiwum/snes_spc/` (RSN mirror) |
| **Tiny Music** | `.mod`, `.xm`, `.s3m`, `.it` | varies | Local `archiwum/tiny/` |

All archives are served from local disk — no external HTTP calls during playback.

## Quick Start

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv audacious audacious-plugins ffmpeg pipewire-pulse gstreamer1.0-plugins-good gstreamer1.0-plugins-bad sidplayfp

git clone git@github.com:wiiii653/robbo-obibok-ulimate-chiptune-bot.git
cd robbo-obibok-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Fedora

```bash
sudo dnf install -y python3 python3-virtualenv audacious audacious-plugins ffmpeg pipewire-utils gstreamer1-plugins-good gstreamer1-plugins-bad-free gstreamer1-plugins-bad-freeworld sidplayfp

git clone git@github.com:wiiii653/robbo-obibok-ulimate-chiptune-bot.git
cd robbo-obibok-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Arch Linux

```bash
sudo pacman -S python python-virtualenv audacious audacious-plugins ffmpeg pipewire gst-plugins-good gst-plugins-bad sidplayfp

git clone git@github.com:wiiii653/robbo-obibok-ulimate-chiptune-bot.git
cd robbo-obibok-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
cd robbo-obibok-ulimate-chiptune-bot
source venv/bin/activate

# Set your bot token
export DISCORD_BOT_TOKEN="your-token-here"

# Run via the shared launcher
./run_bot.sh

# Run with strict compatibility mode
ROBBO_STRICT_COMPAT=1 ./run_bot.sh
```

Launcher test commands:

```bash
# Focused launcher smoke suite
./test_launchers.sh

# Equivalent Make target
make test-launchers
```

Development checks:

```bash
make test
make typecheck
make test-integration
```

The type-check target installs development-only dependencies from `requirements-dev.txt`.
Integration tests use the real Discord SDK and FFmpeg. Set `DISCORD_INTEGRATION_TOKEN`
to enable API authentication and `RUN_LIVE_AUDIO_INTEGRATION=1` to check local
PulseAudio/Audacious services.

Logged launcher path:

```bash
# Canonical logged launcher module
./venv/bin/python3 robbo_obibok_logged_launcher.py

# Compatibility entrypoint kept for existing scripts
./venv/bin/python3 run_bot_logged.py
```

> **Note for C64 SID playback:** GStreamer `siddec` plugin is bundled with `gstreamer1.0-plugins-bad`. If SIDs don't play, verify with: `gst-inspect-1.0 siddec`

## Invite the Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application → **OAuth2 → URL Generator**
3. Scopes: `bot`, `applications.commands`
4. Permissions: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`
5. Use the generated URL to invite the bot to your server

## Systemd Service (Linux)

Run as a background service:

```bash
# Copy a service file
mkdir -p ~/.config/systemd/user
cp robbo-obibok.service ~/.config/systemd/user/
# or
cp robbo-obibok-strict.service ~/.config/systemd/user/

# Store token securely
echo "YOUR_TOKEN_HERE" > ~/.robbo-token
chmod 600 ~/.robbo-token

# Enable and start
systemctl --user daemon-reload
systemctl --user enable robbo-obibok
systemctl --user start robbo-obibok

# Or use the strict service explicitly
systemctl --user enable robbo-obibok-strict
systemctl --user start robbo-obibok-strict

# Check logs
journalctl --user -u robbo-obibok -f
```

## Building Local Indexes

After cloning, build the local track indexes for the local archive collections:

```bash
make build-indexes

# or run the builders directly
python build_asma_index.py   # indexes all .sap files in archiwum/asma/
python build_hvsc_index.py   # indexes all .sid files in archiwum/hvsc/C64Music/
python build_ay_index.py     # indexes all .ay files in archiwum/ay/
python build_ym_index.py     # indexes all .ym files in archiwum/ym/
python build_tiny_index.py   # indexes all tiny-module files in archiwum/tiny/
python build_snes_index.py   # indexes all .spc files in archiwum/snes_spc/
```

These generate `*_cache_local.json` files for instant startup — no crawling at runtime.

## Audio Effects

The bot enables Audacious's **Compressor** effect plugin at startup for consistent loudness across collections (particularly important when switching between SID, SAP, MOD, and other formats with differing volume levels).

The compressor is configured via Audacious's user config (`~/.config/audacious/config`):
```ini
[compressor]
center=0.4
range=0.35
```

To verify the compressor is active: `audtool plugin-is-enabled compressor`
To adjust the settings: edit `~/.config/audacious/config` and restart the bot.

## Troubleshooting

| Symptom | Likely Fix |
|---------|-----------|
| `RuntimeError: PyNaCl library needed` | `pip install pynacl` |
| Bot doesn't respond to commands | Enable **Message Content Intent** in Discord Developer Portal |
| Bot joins VC but no sound (SAP) | Audacious not running — restart bot, or run `audacious --headless` manually |
| Bot joins VC but no sound (SID/AY/YM) | `gst-inspect-1.0 siddec` — if missing, install `gstreamer1.0-plugins-bad` |
| Two collections play at once | Update to latest code — `stop_all_players()` fix prevents audio bleed |
| Crawl seems stuck | All collections are local now — run build scripts if cache is missing |
| `!play` says "Join a voice channel" | You must be on a voice channel when issuing the command |
| Bot auto-disconnects too fast | Increase `auto.empty_timeout` in config |
| SID metadata is empty | Some SID files lack embedded headers — filename is shown as fallback |
| GME formats skip too early | Updated in latest code — GME formats use 600s timeout with song-loaded check |
|| Temp dir cleanup errors | Temp dir moved under `tmp/` in bot root — no more `/tmp/asma_bot_*` orphaned dirs |
|| Audio is too quiet or uneven | Compressor plugin is enabled at startup — verify with `audtool plugin-is-enabled compressor` |

## Configuration

Edit `config.yaml`:

```yaml
command_prefix: "!"
asma:
  base_url: "https://asma.atari.org/asma/"
  top_dirs:
    - "Composers/"
    - "Games/"
    - "Groups/"
    - "Misc/"
    - "Unknown/"
  crawl_timeout: 15
  cache_ttl: 24
hvsc:
  base_url: "https://www.hvsc.c64.org/download/C64Music/"
  songlengths_url: "https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/Songlengths.txt"
  cache_ttl: 168
  enabled: false
ay:
  base_url: "https://web.archive.org/web/2023/ayarchive/..."
  cache_ttl: 168
ym:
  base_url: "https://...ym archive..."
  cache_ttl: 168
modarchive:
  base_url: "https://api.modarchive.org/"
  cache_ttl: 168
snes:
  base_url: "https://...rsn mirror..."
  cache_ttl: 168
audio:
  sink_name: "robbo_bot"
  sample_rate: 48000
  channels: 2
  format: "s16le"
playback:
  loop: true
  shuffle: true
  crossfade: 0
auto:
  start_channel: ""
  empty_timeout: 60
```

## File Structure

```
robbo-obibok/
├── robbo-obibok.py            # Default launcher facade
├── robbo-obibok-strict.py     # Strict launcher facade
├── robbo_obibok_runtime.py    # Importable runtime facade
├── robbo_obibok_launcher.py   # Shared process launcher
├── robbo_obibok_logged_launcher.py # Logging-oriented launcher
├── config.yaml                # Configuration file
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── .gitignore                 # Git ignore rules
├── build_asma_index.py        # ASMA local index builder
├── build_hvsc_index.py        # HVSC local index builder
├── build_ay_index.py          # AY local index builder
├── build_ym_index.py          # YM local index builder
├── build_tiny_index.py        # Tiny local index builder
├── build_snes_index.py        # SNES local index builder
├── download_modarchive_bulk.py # ModArchive bulk downloader
├── tmp/                       # Temp directory for subsong WAVs (generated)
├── archiwum/                  # Local archives (see Collections table)
│   ├── asma/                  # Atari SAP files
│   ├── hvsc/                  # C64 SID files
│   ├── ay/                    # ZX Spectrum AY files
│   ├── ym/                    # Atari ST YM files
│   ├── tiny/                  # Tiny Music modules
│   ├── snes_spc/              # SNES SPC files
│   └── modarchive_textfiles/  # ModArchive tracker modules
├── queues/                    # Persisted queues per guild (generated)
├── favorites.json             # Reaction-based favorites (generated)
├── asma_cache_local.json      # ASMA local track index (generated)
├── hvsc_cache_local.json      # HVSC local track index (generated)
└── *.cache.json               # Other collection cache files (generated)
```
