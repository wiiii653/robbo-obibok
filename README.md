```
__________      ___.  ___.            ________ ___.   ._____.           __   
\______   \ ____\_ |__\_ |__   ____   \_____  \\\_ |__ |__\_ |__   _____/  |_ 
 |       _//  _ \| __ \| __ \ /  _ \   /   |   \| __ \|  || __ \ /  _ \   __\
 |    |   (  <_> ) \_\ \ \_\ (  <_> ) /    |    \ \_\ \  || \_\ (  <_> )  |  
 |____|_  /\____/|___  /___  /\____/  \_______  /___  /__||___  /\____/|__|  
        \/           \/    \/                 \/    \/        \/              
```

# Robbo Obibot — The Ultimate Chiptune Bot

Named after a fusion of the 1989 Polish Atari classic *Robbo* and the avant-garde jazz band *Robotobibok*, this specialized Discord bot streams vintage retro chipmusic. Plays **Atari `.sap`** files from the [ASMA archive](https://asma.atari.org/), **Commodore 64 `.sid`** files from the [High Voltage SID Collection](https://www.hvsc.c64.org/), and **Amiga `.mod`/`.xm`/`.s3m`/`.it`** modules from [ModArchive](https://modarchive.org/).

**Join a voice channel, type `!play`, and let the chips play.**

## Features

- 🎵 **Triple collection** — switch between **Atari SAP** (6400+), **C64 SID** (60 000+), and **ModArchive** (175 000+ modules) with `!flip`
- 🔀 **Shuffle loop** — never hear the same track twice in a row
- 🎼 **Rich metadata** — track name, composer, copyright from `.sap`, `.sid` and module headers
- ❤️ **Favorites playlist** — react to any Now Playing embed to save/remove tracks, play them with `!favplay`
- 🔊 **Volume control** — per‑collection normalization (SID 150%, SAP 100%, MOD 100%), manual override with `!volume`
- ⏭️ **Skip**, **Stop**, **Jump**, **Queue**, **History**, **Now Playing**, **Search**
- 🔄 **Auto-advance** — moves to next track when current ends
- 🔁 **Loop mode** — toggle playlist reshuffle with `!loop`
- 💾 **Queue persistence** — saves/restores queue across restarts
- 📻 **Auto-start** — starts playing when someone joins a configured voice channel
- 🌙 **Auto-stop** — disconnects after channel is empty for a timeout
- 🏥 **Watchdog** — auto-restarts players and PulseAudio sink if they crash
- ⚙️ **Configurable** via `config.yaml`

## Commands

| Command | Description |
|---------|-------------|
| `!play` / `!radio` / `!uruchom` | Start shuffled radio from current collection |
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
| `!radi` | NI MA RADI 😈 (easter egg) |
| `!ocko` | Random ASCII owl |
| `!export` | Dump the full playlist as a code block |
| `!stats` | Show radio statistics |
| `!search <query>` | Search tracks by name, directory, or author |
| `!refresh` | Re‑crawl archive and rebuild playlist |
| `!reindex` | Re‑fetch metadata for search index |
| `!asma` | Switch to **Atari SAP** collection |
| `!hvsc` / `!c64` / `!sid` | Switch to **Commodore 64 SID** collection |
| `!mod` / `!modarchive` / `!tracker` / `!modules` | Switch to **ModArchive** collection |
| `!flip` / `!switch` / `!toggle` / `!przelacz` | Toggle HVSC → ASMA → ModArchive → HVSC … |
| `!status` / `!mode` / `!collection` | Show current collection and queue info |
| `!favorites` / `!favs` / `!playlista` | Show your reaction‑based favorites |
| `!favplay` / `!fp` | Play all (or a specific) favorited tracks |

### Favorites System

React with **any emoji** to a **Now Playing embed** (both the auto‑sent one and the one from `!np`) to save the track to your favorites.  
React again to remove it (toggle).  
Use `!favplay` to play all favorited tracks shuffled, or `!favplay N` to play a specific one.  
Data persists in `favorites.json`.

**Tip:** The auto‑play embed that appears when a track starts is already tracked — just react to it.  
If you missed it, type `!np` and react to that embed instead.

### Collection Switching

When you switch collections with `!flip`, `!asma`, `!hvsc` or `!mod` **while in a voice channel**, playback restarts automatically with the new collection.  
No manual `!play` needed.

## Quick Start

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv audacious audacious-plugins ffmpeg pipewire-pulse gstreamer1.0-plugins-good gstreamer1.0-plugins-bad sidplayfp libopenmpt-dev

git clone git@github.com:wiiii653/asma-discord-bot.git
cd asma-discord-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Fedora

```bash
sudo dnf install -y python3 python3-virtualenv audacious audacious-plugins ffmpeg pipewire-utils gstreamer1-plugins-good gstreamer1-plugins-bad-free gstreamer1-plugins-bad-freeworld sidplayfp libopenmpt

git clone git@github.com:wiiii653/asma-discord-bot.git
cd asma-discord-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Arch Linux

```bash
sudo pacman -S python python-virtualenv audacious audacious-plugins ffmpeg pipewire gst-plugins-good gst-plugins-bad sidplayfp libopenmpt

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

> **Note for C64 SID playback:** Audacious uses `sid.so` input plugin (bundled with `audacious-plugins`) which relies on `libsidplayfp`.  
> **Note for ModArchive playback:** Audacious uses `openmpt.so` input plugin for MOD/XM/S3M/IT files (bundled with `audacious-plugins`).

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
| Bot joins VC but no sound | Audacious not running — restart bot, or run `audacious --headless` manually |
| SID doesn't play / no SID plugin | Verify `ls /usr/lib/*/audacious/Input/sid.so` — install `audacious-plugins` with sidplayfp |
| MOD doesn't play / no openmpt plugin | Verify `ls /usr/lib/*/audacious/Input/openmpt.so` — install `libopenmpt` and `audacious-plugins` |
| Both Atari and C64 play at once | Update to latest code — `stop_all_players()` fix prevents audio bleed |
| Crawl seems stuck | Check `config.yaml` → `crawl_timeout` and `cache_ttl` |
| `!play` says "Join a voice channel" | You must be on a voice channel when issuing the command |
| Bot auto-disconnects too fast | Increase `auto.empty_timeout` in config |
| HVSC index download fails | Check `hvsc.songlengths_url` in config — HVSC may be temporarily down |
| SID metadata is empty | Some SID files lack embedded headers — filename is shown as fallback |
| SAP plays but no "Now Playing" embed | Bot was still starting up — use `!np` to see the current track |
| Duplicate bot responses | PID lock prevents this normally — if it happens, `pkill -f asma-bot.py` and restart |

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
modarchive:
  base_url: "https://modarchive.org/"
  download_url: "https://modarchive.org/download.php"
  cache_ttl: 168
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
├── asma-bot.py              # Main bot code
├── config.yaml              # Configuration file
├── requirements.txt         # Python dependencies
├── asma-bot.service         # Systemd service file
├── run_robbo.sh             # Quick-start script
├── runner.py                # Token-injecting launcher (base64 token)
├── build_modarchive_index.py# ModArchive index builder (A–Z scan)
├── asma_cache.json          # Cached ASMA track list (generated)
├── hvsc_cache.json          # Cached HVSC track list (generated)
├── modarchive_cache.json    # Cached ModArchive track list (generated, ~22 MB)
├── favorites.json           # Reaction-based favorites (generated)
├── queues/                  # Persisted queues per guild (generated)
├── metadata_cache.json      # Search metadata index (generated)
├── extras/                  # Extra utilities
├── tests/                   # Test scripts
├── venv/                    # Virtualenv (optional local setup)
└── README.md                # This file
```
