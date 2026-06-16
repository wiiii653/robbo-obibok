```
██████╗  ██████╗ ██████╗ ██████╗  ██████╗ 
██╔══██╗██╔═══██╗██╔══██╗██╔══██╗██╔═══██╗
██████╔╝██║   ██║██████╔╝██████╔╝██║   ██║
██╔══██╗██║   ██║██╔══██╗██╔══██╗██║   ██║
██║  ██║╚██████╔╝██████╔╝██████╔╝╚██████╔╝
╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝  ╚═════╝
· · · · · · · · · · · · · · · · · · · · · ·
 ██████╗ ██████╗ ██╗██████╗  ██████╗ ████████╗
██╔═══██╗██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██║   ██║██████╔╝██║██████╔╝██║   ██║   ██║   
██║   ██║██╔══██╗██║██╔══██╗██║   ██║   ██║   
╚██████╔╝██████╔╝██║██████╔╝╚██████╔╝   ██║   
 ╚═════╝ ╚═════╝ ╚═╝╚═════╝  ╚═════╝    ╚═╝ 
```

# Robbo Obibot — The Ultimate Atari Chiptune Bot

Named after a fusion of the 1989 Polish Atari classic *Robbo* and the avant-garde jazz band *Robotobibok*, this specialized Discord bot streams vintage retro chipmusic. Blending intricate technical grooves with retro charm, Robbo Obibot emulates Atari `.sap` files from the [ASMA archive](https://asma.atari.org/) directly into your voice channel.

**Join a voice channel, type `!radio`, and let the POKEY chips play.**

## Features

- 🎵 **6400+ chiptunes** — crawls the entire ASMA archive (Composers, Games, Groups, Misc, Unknown)
- 🔀 **Shuffle loop** — never hear the same track twice in a row
- 🎼 **SAP metadata** — shows track name, composer, and song count from `.sap` headers
- ⏭️ **Skip**, **Stop**, **Now Playing**, **Stats**, **Search**
- 🔄 **Auto-advance** — moves to next track when current ends
- 💾 **Queue persistence** — saves/restores queue across restarts
- 📻 **Auto-start** — starts playing when someone joins a configured voice channel
- 🌙 **Auto-stop** — disconnects after channel is empty for a timeout
- 🏥 **Watchdog** — auto-restarts Audacious and PulseAudio sink if they crash
- ⚙️ **Configurable** via `config.yaml`

## Commands

| Command | Description |
|---------|-------------|
| `!play` / `!radio` | Start shuffled radio from all ASMA tracks |
| `!stop` | Stop playback and disconnect |
| `!skip` / `!next` | Skip to next track |
| `!np` | Show current track info (name, composer, position) |
| `!stats` | Show radio stats (total tracks, queue position, loop status) |
| `!search <query>` | Search tracks by name or author |
| `!refresh` | Re-crawl ASMA and rebuild playlist |

## Installation

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-venv audacious audacious-plugins ffmpeg pipewire-pulse

git clone git@github.com:wiiii653/robbo-obibot-ulimate-chiptune-bot.git
cd robbo-obibot-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Fedora

```bash
sudo dnf install -y python3 python3-virtualenv audacious audacious-plugins ffmpeg pipewire-utils

git clone git@github.com:wiiii653/robbo-obibot-ulimate-chiptune-bot.git
cd robbo-obibot-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Arch Linux

```bash
sudo pacman -S python python-virtualenv audacious audacious-plugins ffmpeg pipewire

git clone git@github.com:wiiii653/robbo-obibot-ulimate-chiptune-bot.git
cd robbo-obibot-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Windows (Native)

Robbo requires **Audacious** and **PulseAudio** which are Linux-native. Two options:

**Option A — WSL 2 (recommended):**

```powershell
# In PowerShell as Administrator:
wsl --install -d Ubuntu
```

Then inside WSL, follow the Ubuntu guide above.

**Option B — PulseAudio on Windows + WSL:**

1. Install [PulseAudio for Windows](https://www.freedesktop.org/wiki/Software/PulseAudio/Ports/Windows/Support/)
2. Run `pulseaudio.exe`
3. In WSL:
   ```bash
   export PULSE_SERVER=tcp:$(hostname).local
   ```
4. Follow the Ubuntu guide inside WSL.

### macOS

Not supported. Audacious and PulseAudio are Linux-only. Consider running in a Linux VM or using Docker.

## Running

```bash
# Set your bot token
export DISCORD_BOT_TOKEN="your-token-here"

# Run
python3 asma-bot.py
```

## Invite the Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application → **OAuth2 → URL Generator**
3. Scopes: `bot`, `applications.commands`
4. Permissions: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`
5. Use the generated URL to invite the bot

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
  crawl_timeout: 15    # seconds per HTTP request
  cache_ttl: 24        # hours before re-crawl
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
  start_channel: ""       # voice channel name to auto-start (empty = disabled)
  empty_timeout: 60       # seconds of empty channel before disconnect (0 = disabled)
```

## Systemd Service (Linux)

Run as a background service:

```bash
# Copy service file
cp asma-bot.service ~/.config/systemd/user/
mkdir -p ~/.config/systemd/user

# Store token securely
echo "YOUR_TOKEN_HERE" > ~/.asma-bot-token
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
| Crawl seems stuck | Check `config.yaml` → `crawl_timeout` and `cache_ttl` |
| `!play` says "Join a voice channel" | You must be on a voice channel when issuing the command |
| Bot auto-disconnects too fast | Increase `auto.empty_timeout` in config |

## File Structure

```
robbo-obibot/
├── asma-bot.py         # Main bot code
├── config.yaml         # Configuration file
├── requirements.txt    # Python dependencies
├── asma-bot.service    # Systemd service file
├── run_robbo.sh        # Quick-start script
├── asma_cache.json     # Cached track list (generated)
├── queues/             # Persisted queues per guild (generated)
└── README.md           # This file
```

## License

MIT
