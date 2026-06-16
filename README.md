# Robbo Obibot — Ultimate Chiptune Radio 🎛️🌲

Discord bot that turns the [ASMA Atari SAP Music Archive](https://asma.atari.org/) into an endless shuffled chiptune radio.

**Join a voice channel, type `!radio`, and let the POKEY chips play.**

## Features

- 🎵 **6400+ chiptunes** — crawls the entire ASMA archive (Composers, Games, Groups, Misc, Unknown)
- 🔀 **Shuffle loop** — never hear the same track twice in a row
- ⏭️ **Skip**, **Stop**, **Now Playing**, **Stats**
- 🔄 **Auto-advance** — moves to next track when current ends
- 💾 **Cache** — skips full crawl if cached less than 24h ago
- ⚙️ **Configurable** via `config.yaml`

## Commands

| Command | Description |
|---------|-------------|
| `!play` / `!radio` | Start shuffled radio from all ASMA tracks |
| `!stop` | Stop playback and disconnect |
| `!skip` / `!next` | Skip to next track |
| `!np` | Show current track info |
| `!stats` | Show radio stats (total tracks, queue position, loop status) |
| `!refresh` | Re-crawl ASMA and rebuild playlist |

## Quick Start (Linux)

```bash
# 1. Install system dependencies
sudo apt install -y audacious audacious-plugins ffmpeg pipewire-pulse

# 2. Clone and set up
git clone git@github.com:wiiii653/robbo-obibot-ulimate-chiptune-bot.git
cd robbo-obibot-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install discord.py[voice] pynacl davey aiohttp pyyaml requests

# 3. Copy and tweak config
cp config.yaml config.yaml   # edit to your needs

# 4. Set your bot token
export DISCORD_BOT_TOKEN="your-token-here"

# 5. Run
python3 runner.py
```

## Configuration

Copy `config.yaml` and adjust values:

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
```

## Windows Setup (via WSL)

Robbo requires **Audacious** (Linux-only) and **PipeWire/PulseAudio** for audio playback and virtual sink routing. On Windows, the recommended approach is **WSL 2 (Windows Subsystem for Linux)**:

### Step 1: Install WSL 2

```powershell
# In PowerShell as Administrator:
wsl --install -d Ubuntu
```

### Step 2: Install dependencies inside WSL

```bash
sudo apt update
sudo apt install -y audacious audacious-plugins ffmpeg pipewire-pulse pipewire-audio
```

### Step 3: Set up PulseAudio for WSL

Windows doesn't have PulseAudio natively, so you need a PulseAudio server on Windows:

**Option A — Use PulseAudio on Windows (recommended):**
1. Download [PulseAudio for Windows](https://www.freedesktop.org/wiki/Software/PulseAudio/Ports/Windows/Support/)
2. Install and run `pulseaudio.exe`
3. In WSL, tell PulseAudio to connect to Windows:
   ```bash
   export PULSE_SERVER=tcp:$(hostname).local
   ```

**Option B — Use `audio.sink` passthrough (built-in WSL audio):**
```bash
sudo apt install -y pipewire-pulse
# WSLg handles audio routing automatically
```

### Step 4: Clone and run (same as Linux)

```bash
cd ~
git clone git@github.com:wiiii653/robbo-obibot-ulimate-chiptune-bot.git
cd robbo-obibot-ulimate-chiptune-bot
python3 -m venv venv
source venv/bin/activate
pip install discord.py[voice] pynacl davey aiohttp pyyaml requests
export DISCORD_BOT_TOKEN="your-token-here"
python3 runner.py
```

### Step 5: Invite the bot to Discord

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application → **OAuth2 → URL Generator**
3. Scopes: `bot`, `applications.commands`
4. Permissions: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`
5. Use the generated URL to invite the bot

### Step 6: Play!

Join a voice channel and type:

```
!radio
```

## Troubleshooting

| Symptom | Likely Fix |
|---------|-----------|
| `RuntimeError: PyNaCl library needed` | `pip install pynacl` |
| `RuntimeError: davey library needed` | `pip install davey` |
| Bot doesn't respond to commands | Enable **Message Content Intent** in Discord Developer Portal |
| Bot joins VC but no sound | Audacious not running — restart bot, or run `audacious --headless` manually |
| Crawl seems stuck | Check `config.yaml` → `crawl_timeout` and `cache_ttl` |
| `!play` says "Join a voice channel" | You must be on a voice channel when issuing the command |

## File Structure

```
robbo-obibot/
├── asma-bot.py         # Main bot code
├── runner.py           # Wrapper with base64-encoded token
├── config.yaml         # Configuration file
├── run_robbo.sh        # Quick-start script
├── asma_cache.json     # Cached track list (generated)
└── README.md           # This file
```

## License

MIT — do what you want, but give credit to the dark forest spirit who helped you. 🌲
