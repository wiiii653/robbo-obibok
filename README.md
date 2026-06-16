# ASMA Discord Bot

A Discord bot that plays Atari SAP music from the [Atari SAP Music Archive](https://asma.atari.org/) using Audacious Player.

## Architecture

```
User (Discord) → Bot → Audacious (audtool IPC) → Virtual Sink → FFmpeg → Discord Voice
```

1. **Virtual sink** (`asma_bot`) isolates bot audio from system audio
2. **Audacious headless** decodes SAP files via `audtool` IPC
3. **FFmpeg** captures the sink's monitor and pipes 48kHz stereo PCM to Discord

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
pip install discord.py requests
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

| Command | Description |
|---------|-------------|
| `!play <url>` | Play a SAP file from ASMA |
| `!stop` | Stop playback and disconnect |

### Example

```
!play https://asma.atari.org/asma/Composers/SuperJet_Spade/Acidjazzed_Evening.sap
```

## How It Works

1. User posts an ASMA URL in Discord
2. Bot downloads the `.sap` file to a temp directory
3. Bot clears Audacious playlist, adds the file, and starts playback
4. Audacious decodes the SAP (POKEY chip emulation) and outputs to a virtual PulseAudio/PipeWire sink
5. FFmpeg captures the sink's monitor and streams raw PCM to Discord
6. Bot auto-disconnects when playback finishes

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

## License

MIT
