# ASMA Radio Bot

A Discord bot that shuffles and plays chiptunes from the [Atari SAP Music Archive](https://asma.atari.org/) using Audacious Player — a never-ending radio of 8-bit POKEY goodness.

## Architecture

```
User (Discord) → Bot → Audacious (audtool IPC) → Virtual Sink → FFmpeg → Discord Voice
```

1. **Virtual sink** (`asma_bot`) isolates bot audio from system audio
2. **Audacious headless** decodes SAP files via `audtool` IPC
3. **FFmpeg** captures the sink's monitor and pipes 48kHz stereo PCM to Discord
4. **ASMA crawler** recursively indexes all `.sap` files from the archive

## Requirements

- Python 3.10+
- [Audacious](https://audacious-media-player.org/) + plugins (includes SAP decoder)
- FFmpeg
- PulseAudio or PipeWire (with PulseAudio compatibility)
- A Discord bot token ([create one here](https://discord.com/developers/applications))

## Setup

### 1. Install system dependencies

```bash
sudo apt install audacious audacious-plugins ffmpeg
```

### 2. Create virtual environment and install Python packages

```bash
python3 -m venv venv
source venv/bin/activate
pip install discord.py requests aiohttp
```

### 3. Configure Discord bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application → go to **Bot** tab
3. Enable **Message Content Intent** (under Privileged Gateway Intents)
4. Copy the bot token

### 4. Invite bot to your server

1. Go to **OAuth2** → **URL Generator**
2. Select scopes: `bot`
3. Select permissions: `Connect`, `Speak`, `Send Messages`, `Use Voice Activity`
4. Open the generated URL and authorize the bot to your server

### 5. Run the bot

```bash
export DISCORD_BOT_TOKEN="your-token-here"
python3 asma-bot.py
```

## Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `!play` | `!radio` | Start shuffled radio from **all** ASMA tracks (6400+) |
| `!stop` | | Stop playback and disconnect |
| `!skip` | `!next` | Skip to next shuffled track |
| `!np` | | Show current track info |
| `!stats` | | Show radio statistics |
| `!refresh` | | Re-crawl ASMA and rebuild playlist |

### First run

On the first `!play` / `!radio`, the bot crawls the entire ASMA archive (~6400 tracks). This takes a minute or two. After that, the track list is cached and subsequent plays are instant.

## How It Works

1. User joins a voice channel and types `!radio`
2. Bot crawls ASMA (or loads cached list) and shuffles all tracks
3. Bot downloads the first `.sap` and plays it via Audacious
4. Audacious decodes the SAP (POKEY chip emulation) → virtual sink → FFmpeg → Discord
5. When the track ends, the bot auto-advances to the next one
6. When the playlist is exhausted, it reshuffles and loops forever
7. `!skip` jumps to the next track at any time

## Troubleshooting

**No audio in Discord**
- Check that the virtual sink was created: `pactl list sinks short | grep asma_bot`
- Verify Audacious is running: `pgrep audacious`
- Test the sink directly: `pactl set-default-sink asma_bot && paplay /usr/share/sounds/freedesktop/stereo/bell.oga`

**Bot joins but silence**
- Ensure Audacious output is routed to the `asma_bot` sink: `pactl list sink-inputs short`
- Manually move it: `pactl move-sink-input <id> asma_bot`

**"Module load failed" error**
- The `module-null-sink` may already be loaded. Check with `pactl list modules short | grep null`

**Old audtool syntax**
- If your `audtool` uses `--` prefix syntax, edit the commands in `audacious_play()` and related functions. This code uses the modern syntax (no dashes).

## License

MIT
