```
__________      ___.  ___.            ________ ___.   ._____.           __   
\______   \ ____\_ |__\_ |__   ____   \_____  \\_ |__ |__\_ |__   _____/  |_ 
 |       _//  _ \| __ \| __ \ /  _ \   /   |   \| __ \|  || __ \ /  _ \   __\
 |    |   (  <_> ) \_\ \ \_\ (  <_> ) /    |    \ \_\ \  || \_\ (  <_> )  |  
 |____|_  /\____/|___  /___  /\____/  \_______  /___  /__||___  /\____/|__|  
        \/           \/    \/                 \/    \/        \/              
```

# Robbo Obibot — The Ultimate Chiptune Bot

Named after a fusion of the 1989 Polish Atari classic *Robbo* and the avant-garde jazz band *Robotobibok*, this specialized Discord bot streams vintage retro chipmusic. Blending intricate technical grooves with retro charm, Robbo plays both **Atari `.sap`** files from the [ASMA archive](https://asma.atari.org/) **and Commodore 64 `.sid`** files from the [High Voltage SID Collection](https://www.hvsc.c64.org/).

**Join a voice channel, type `!play`, and let the chips play.**

## Features

- 🎵 **Dual collection** — switch between **Atari SAP** (6400+) and **C64 SID** (60 000+) with `!flip`
- 🔀 **Shuffle loop** — never hear the same track twice in a row
- 🎼 **Rich metadata** — track name, composer, copyright from `.sap` and `.sid` headers
- ❤️ **Favorites playlist** — react to any Now Playing embed to save/remove tracks
- ⏭️ **Skip**, **Stop**, **Now Playing**, **Stats**, **Search**
- 🔄 **Auto-advance** — moves to next track when current ends
- 💾 **Queue persistence** — saves/restores queue across restarts
- 📻 **Auto-start** — starts playing when someone joins a configured voice channel
- 🌙 **Auto-stop** — disconnects after channel is empty for a timeout
- 🏥 **Watchdog** — auto-restarts players and PulseAudio sink if they crash
- ⚙️ **Configurable** via `config.yaml`

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
| `!refresh` | Re-crawl archive and rebuild playlist |
| `!reindex` | Re-fetch metadata for search index |
| `!hvsc` / `!c64` / `!sid` | Switch to **Commodore 64 SID** collection |
| `!asma` | Switch back to **Atari SAP** collection |
| `!flip` / `!switch` / `!toggle` / `!przelacz` | Toggle between Atari and C64 |
| `!status` / `!mode` / `!collection` | Show current collection and queue info |
| `!favorites` / `!favs` / `!playlista` | Show your reaction-based favorites playlist |

### Favorites System

React with **any emoji** to a Now Playing embed to save the track to your favorites. React again to remove it (toggle). Data persists in `favorites.json`.

## Quick Start

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv audacious audacious-plugins ffmpeg pipewire-pulse gstreamer1.0-plugins-good gstreamer1.0-plugins-bad sidplayfp

git clone git@github.com:wiiii653/asma-discord-bot.git
cd asma-discord-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Fedora

```bash
sudo dnf install -y python3 python3-virtualenv audacious audacious-plugins ffmpeg pipewire-utils gstreamer1-plugins-good gstreamer1-plugins-bad-free gstreamer1-plugins-bad-freeworld sidplayfp

git clone git@github.com:wiiii653/asma-discord-bot.git
cd asma-discord-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Arch Linux

```bash
sudo pacman -S python python-virtualenv audacious audacious-plugins ffmpeg pipewire gst-plugins-good gst-plugins-bad sidplayfp

git clone git@github.com:wiiii653/asma-discord-bot.git
cd asma-discord-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
cd asma-discord-bot
source venv/bin/activate

# Set your bot token
export DISCORD_BOT_TOKEN="your-token-here"

# Run
./venv/bin/python3 asma-bot.py
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
mkdir -p ~/.config/systemd/user
cp asma-bot.service ~/.config/systemd/user/

# Store token for systemd EnvironmentFile=
printf 'DISCORD_BOT_TOKEN=%s\n' "YOUR_TOKEN_HERE" > ~/.asma-bot-token
chmod 600 ~/.asma-bot-token

# Enable and start
systemctl --user daemon-reload
systemctl --user enable asma-bot
systemctl --user start asma-bot

# Check logs
journalctl --user -u asma-bot -f
```

## Troubleshooting

| Symptom | Likely Fix |
|---------|-----------|
| `RuntimeError: PyNaCl library needed` | `pip install pynacl` |
| Bot doesn't respond to commands | Enable **Message Content Intent** in Discord Developer Portal |
| Bot joins VC but no sound (ASMA) | Audacious not running — restart bot, or run `audacious --headless` manually |
| Bot joins VC but no sound (C64) | `gst-inspect-1.0 siddec` — if missing, install `gstreamer1.0-plugins-bad` |
| Both Atari and C64 play at once | Update to latest code — `stop_all_players()` fix prevents audio bleed |
| Crawl seems stuck | Check `config.yaml` → `crawl_timeout` and `cache_ttl` |
| `!play` says "Join a voice channel" | You must be on a voice channel when issuing the command |
| Bot auto-disconnects too fast | Increase `auto.empty_timeout` in config |
| HVSC index download fails | Check `hvsc.songlengths_url` in config — HVSC may be temporarily down |
| SID metadata is empty | Some SID files lack embedded headers — filename is shown as fallback |

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
  cache_ttl: 168          # hours before re-download (1 week)
  enabled: false           # set true to start with C64 by default
audio:
  sink_name: "asma_bot"
  sample_rate: 48000
  channels: 2
  format: "s16le"
playback:
  loop: true
  shuffle: true
  crossfade: 0
auto:
  start_channel: ""        # voice channel name to auto-start (empty = disabled)
  empty_timeout: 60        # seconds of empty channel before disconnect (0 = disabled)
```

## File Structure

```
asma-discord-bot/
├── asma-bot.py          # Main bot code
├── config.yaml          # Configuration file
├── requirements.txt     # Python dependencies
├── asma-bot.service     # Systemd service file
├── run_robbo.sh         # Quick-start script
├── asma_cache.json      # Cached ASMA track list (generated)
├── hvsc_cache.json      # Cached HVSC track list (generated)
├── favorites.json       # Reaction-based favorites (generated)
├── queues/              # Persisted queues per guild (generated)
├── metadata_cache.json  # Search metadata index (generated)
├── venv/                # Virtualenv (optional local setup)
└── README.md            # This file
```
