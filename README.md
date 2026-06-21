```
__________      ___.  ___.            ________ ___.   ._____.           __    
\______   \ ____\_ |__\_ |__   ____   \_____  \\_ |__ |__\_ |__   ____ |  | __
 |       _//  _ \| __ \| __ \ /  _ \   /   |   \| __ \|  || __ \ /  _ \|  |/ /
 |    |   (  <_> ) \_\ \ \_\ (  <_> ) /    |    \ \_\ \  || \_\ (  <_> )    < 
 |____|_  /\____/|___  /___  /\____/  \_______  /___  /__||___  /\____/|__|_ \
        \/           \/    \/                 \/    \/        \/            \/
                                                                              
```

# Robbo Obibok — The Ultimate Chiptune Bot

Named after a fusion of the 1989 Polish Atari classic *Robbo* and the avant-garde jazz band *Robotobibok*, this specialized Discord bot streams vintage retro chipmusic. Six collections, one bot — **the biggest chiptune radio on Discord.**

**Join a voice channel, `!play`, and let the chips fall where they may.**

## Features

### 🎵 Six Collections (and growing)

| # | Collection | Tracks | Source | Command |
|---|-----------|--------|--------|---------|
| 🟢 | **Atari SAP (ASMA)** | ~6 300 | asma.atari.org | `!asma` |
| 🟣 | **C64 SID (HVSC)** | ~60 500 | hvsc.c64.org | `!hvsc` / `!c64` |
| 🟠 | **Tracker Modules (ModArchive)** | ~175 000 | modarchive.org | `!mod` |
| 🔵 | **ZX Spectrum AY** | ~4 500 | local `archiwum/ay/` | `!ay` / `!zx` |
| 🎵 | **Tiny Music** | ~418 | local `archiwum/tiny/` | `!tiny` |
| 🔴 | **SNES SPC** | ~60 000 tracks, 2 612 games | snesmusic.org | `!snes` / `!spc` |

Switch between them with `!flip`, check all counts with `!status`.

### 🎮 Playback & Control

- 🔀 **Shuffle loop** — never hear the same track twice in a row
- 🎼 **Rich metadata** — track name, composer, copyright from headers
- ❤️ **Favorites playlist** — react to any Now Playing embed to save/remove tracks, play with `!favplay`
- ⛔ **Blacklist** — ban tracks you never want to hear again with `!blk`
- 🔊 **Per‑collection volume normalization** — SID at 120%, SAP/AY/Tiny at 100%
- ⏭️ **Skip**, **Stop**, **Jump**, **Queue**, **History**, **Now Playing**, **Search**
- 🔄 **Auto-advance** — moves to next track when current ends
- 🔁 **Loop mode** — toggle with `!loop`
- 💾 **Queue persistence** — survives restarts
- 🔍 **SNES search** — `!snes search <game name or composer>` finds games by title or artist
- 📻 **Auto-start** — starts playing when someone joins a configured voice channel
- 🌙 **Auto-stop** — disconnects after channel is empty for a timeout
- 🏥 **Watchdog** — auto-restarts players and PulseAudio sink if they crash
- ⚙️ **Configurable** via `config.yaml`

## Commands

### Playback

| Command | Description |
|---------|-------------|
| `!play` / `!radio` / `!start` | Start shuffled radio from current collection |
| `!play <query>` | Search and play first matching track |
| `!play <number>` | Play a track from last search results |
| `!stop` | Stop playback and disconnect |
| `!skip` / `!next` | Skip to next track |
| `!jump <n>` | Jump to the n‑th track in the queue |
| `!np` | Show current track info (with elapsed / total duration) |
| `!queue` / `!q` | Show the next 10 tracks in the queue |
| `!history` | Show the last 10 played tracks |
| `!clear` | Clear the queue and disconnect |
| `!volume` | Show current volume |
| `!volume <0-200>` | Set playback volume |
| `!loop` / `!repeat` | Toggle playlist loop mode |
| `!sleep <minutes>` | Auto‑stop after N minutes (max 360) |
| `!radi` | 😈 |
| `!ocko` | Random ASCII owl |

### Collections

| Command | Switches to |
|---------|-------------|
| `!asma` | **Atari SAP** (ASMA) |
| `!hvsc` / `!c64` / `!sid` | **Commodore 64 SID** (HVSC) |
| `!mod` / `!modarchive` / `!tracker` | **Tracker modules** (ModArchive) |
| `!ay` / `!zx` | **ZX Spectrum AY** |
| `!tiny` | **Tiny Music** (curated demoscene modules) |
| `!snes` / `!spc` / `!nintendo` | **SNES SPC** (Super Nintendo) |
| `!snes search <term>` | Search SNES games by name or composer |
| `!flip` / `!switch` / `!toggle` | Cycle: HVSC → ASMA → ModArchive → AY → Tiny → SNES → HVSC (shows sequence) |

### Info & Management

| Command | Description |
|---------|-------------|
| `!status` / `!mode` / `!collection` / `!all` | Show **all six collections** with track counts + current mode |
| `!search <query>` | Search tracks by name, directory, or author |
| `!refresh` | Re‑crawl archive and rebuild playlist |
| `!reindex` | Re‑fetch metadata for search index |
| `!favorites` / `!favs` / `!playlist` | Show your reaction‑based favorites |
| `!favplay` / `!fp` | Play all (or a specific) favorited tracks |
| `!blk` | Blacklist the current playing track (toggle) |
| `!blk <number>` | Blacklist a track by queue number |
| `!blks` / `!blklist` | Show your blacklisted tracks |
| `!blkrm <number>` | Remove a track from blacklist |
| `!export` | Dump the full playlist as a code block |
| `!stats` | Show radio statistics |

### Favorites System

React with **any emoji** to a **Now Playing embed** (both the auto‑sent one and the one from `!np`) to save the track to your favorites. React again to remove it (toggle). Use `!favplay` to play all favorited tracks shuffled, or `!favplay N` to play a specific one. Data persists in `favorites.json`.

**Tip:** The auto‑play embed that appears when a track starts is already tracked — just react to it. If you missed it, type `!np` and react to that embed instead.

### Blacklist System

Is a track so bad it makes your ears bleed? Type **`!blk`** while it's playing to banish it to the shadow realm. It's a toggle — `!blk` again to un‑blacklist.

- `!blk` — blacklist/un‑blacklist the currently playing track (toggle)
- `!blk <number>` — blacklist a track by its position in the queue
- `!blks` — list all your blacklisted tracks
- `!blkrm <number>` — remove a track from the list by number

Blacklisted tracks are **automatically filtered out** when you start `!play` or `!favplay` (shuffle‑all mode). If you blacklist a track that's currently playing, the bot skips it immediately. Data persists in `blacklist.json`, separate per user.

### Collection Switching

When you switch collections with `!flip`, `!asma`, `!hvsc` or any collection command **while in a voice channel**, playback restarts automatically with the new collection. No manual `!play` needed.

## Quick Start

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv audacious audacious-plugins ffmpeg pipewire-pulse sidplayfp libopenmpt-dev unrar

git clone git@github.com:wiiii653/robbo-obibot-ulimate-chiptune-bot.git
cd robbo-obibot-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.yaml config.yaml  # edit to taste
cp .env.example .env        # add DISCORD_BOT_TOKEN
```

### Arch Linux

```bash
sudo pacman -S python python-virtualenv audacious audacious-plugins ffmpeg pipewire gst-plugins-good gst-plugins-bad sidplayfp libopenmpt unrar
# Same clone + venv steps as above
```

## Running

### Manual

```bash
cd robbo-obibot-ulimate-chiptune-bot
source venv/bin/activate
export DISCORD_BOT_TOKEN="your-token-here"
./venv/bin/python3 robbo-obibok.py
```

### Systemd (recommended)

```bash
# Copy service file
sudo cp robbo-obibok.service /etc/systemd/system/

# Make sure .env exists with DISCORD_BOT_TOKEN
echo 'DISCORD_BOT_TOKEN=your-token-here' > .env

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now robbo-obibok.service

# Check status
sudo systemctl status robbo-obibok.service

# View logs
journalctl -u robbo-obibok.service -f
# Or tail the log file
tail -f bot_output.log
```

The bot restarts automatically on failure (`Restart=on-failure`) and on server reboot (`WantedBy=multi-user.target`).

### Building the SNES index

The SNES SPC collection (2 612 games, ~60 000 tracks) requires a one-time index build:

```bash
./venv/bin/python3 build_snes_index.py
```

This scrapes snesmusic.org (takes ~15 minutes, polite 0.3s delay between requests). The resulting `snes_cache.json` is ~650 KB.

## Audio Requirements

- **PipeWire** or **PulseAudio** running under the same user
- Audacious **must** be installed with all plugin bundles (`audacious-plugins`)
- The bot creates a virtual sink called `asma_bot` to route audio to Discord
- **C64 SID:** `sid.so` input plugin (via `libsidplayfp`)
- **Tracker modules:** `openmpt.so` input plugin (via `libopenmpt`)
- **SPC/NSF/GBS:** `console.so` input plugin (via `libgme` — Game Music Emu)
- **ZX Spectrum AY:** `console.so` input plugin (via `libgme`)
- **SNES SPC:** `console.so` input plugin (via `libgme`)

## Troubleshooting

| Symptom | Likely Fix |
|---------|-----------|
| `RuntimeError: PyNaCl library needed` | `pip install pynacl` |
| Bot doesn't respond to commands | Enable **Message Content Intent** in Discord Developer Portal |
| Bot joins VC but no sound (titles show) | `XDG_RUNTIME_DIR` missing under systemd — add `Environment=XDG_RUNTIME_DIR=/run/user/1000` to service file |
| Audacious fails to play (pa_context_connect) | Check `XDG_RUNTIME_DIR` is set; restart the service |
| SNES download fails | `unrar` must be installed (`sudo apt install unrar`) |
| SID doesn't play / no SID plugin | `ls /usr/lib/*/audacious/Input/sid.so` — install `audacious-plugins` with sidplayfp |
| MOD doesn't play / no openmpt plugin | `ls /usr/lib/*/audacious/Input/openmpt.so` — install `libopenmpt` |
| SPC doesn't play / no console plugin | `ls /usr/lib/*/audacious/Input/console.so` — install `libgme` (Game Music Emu) |
| Both Atari and C64 play at once | Update to latest code — `stop_all_players()` fix prevents audio bleed |
| Crawl seems stuck | Check `config.yaml` → `crawl_timeout` and `cache_ttl` |
| `!play` says "Join a voice channel" | You must be on a voice channel when issuing the command |
| Bot auto-disconnects too fast | Increase `auto.empty_timeout` in config |
| HVSC index download fails | Check `hvsc.songlengths_url` in config — HVSC may be temporarily down |
| SID metadata is empty | Some SID files lack embedded headers — filename is shown as fallback |
| SAP plays but no "Now Playing" embed | Bot was still starting up — use `!np` to see the current track |
| Duplicate bot responses | PID lock prevents this — if it happens, `sudo systemctl restart robbo-obibok.service` |

## Invite the Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application → **OAuth2 → URL Generator**
3. Scopes: `bot`, `applications.commands`
4. Permissions: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`
5. Use the generated URL to invite the bot to your server

## File Structure

```
robbo-obibot-ulimate-chiptune-bot/
├── robbo-obibok.py              # Main bot code (2850+ lines)
├── config.yaml                  # Configuration
├── requirements.txt             # Python dependencies
├── robbo-obibok.service         # Systemd unit (auto-start on boot)
├── run_bot.sh                   # Quick-start wrapper (loads .env)
├── build_snes_index.py          # SNESmusic.org cache builder
├── build_modarchive_index.py    # ModArchive index builder
├── build_ay_index.py            # AY archive index builder
├── build_tiny_index.py          # Tiny Music index builder
├── asma_cache.json              # ASMA track list cache
├── ay_cache.json                # AY track list cache
├── tiny_cache.json              # Tiny Music track list cache
├── hvsc_cache.json              # HVSC (C64 SID) track list cache
├── modarchive_cache.json        # ModArchive cache (~22 MB, 175k modules)
├── snes_cache.json              # SNESmusic.org game list (2 612 games)
├── favorites.json               # Reaction-based favorites
├── blacklist.json                # Per-user blacklisted tracks
├── metadata_cache.json          # Search metadata index
├── queues/                      # Persisted queues per guild
├── archiwum/ay/                 # Local AY files
├── archiwum/tiny/               # Local tiny music modules
├── archiwum/spc/                # Downloaded SNES SPC files (on-demand)
├── extras/                      # Extra utilities
├── tests/                       # Test scripts
└── README.md                    # This file
```

## Configuration

See `config.yaml`. Key sections:

```yaml
hvsc:
  enabled: true           # C64 as default collection
asma:
  base_url: "https://asma.atari.org/asma/"
modarchive:
  download_url: "https://api.modarchive.org/downloads.php"
audio:
  sink_name: "asma_bot"   # PipeWire/PulseAudio null-sink
auto:
  start_channel: "ASMA Radio"  # Voice channel that triggers auto-start
  empty_timeout: 60            # Seconds before auto-disconnect
```

Full example in the repository.
