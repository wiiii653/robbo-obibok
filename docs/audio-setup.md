# Audio Setup — Robbo Obibok

## Required Audio Services

Playback requires **Audacious** with a **virtual audio sink** managed by
**PipeWire** or **PulseAudio**. The bot connects to Discord's voice API
and routes Audacious output through the virtual sink into the voice
channel.

### Quick preflight check

```bash
# 1. Is the audio service running?
pactl info >/dev/null 2>&1 && echo "OK" || echo "PipeWire/PulseAudio not running"

# 2. Is Audacious installed?
audtool version >/dev/null 2>&1 && echo "OK" || echo "Audacious not installed"

# 3. Does the virtual sink exist?
pactl list sinks short | grep -q ASMA_Bot && echo "Sink exists" || echo "Sink will be created at startup"
```

### Virtual sink

The bot creates a **null sink** named `ASMA_Bot` at startup if it does not
already exist. This sink appears as a playable audio device that Discord's
voice client can capture.

```bash
# Manual creation (same command the bot runs):
pactl load-module module-null-sink \
  sink_name=ASMA_Bot \
  sink_properties=device.description=ASMA_Bot

# List all sinks:
pactl list sinks short
```

### Audacious configuration

Audacious runs in `--headless` mode (no GUI). The bot starts it
automatically. The SID plugin is configured with:

- `playMaxTimeEnable` = TRUE
- `playMaxTime` = 180 seconds
- `playMaxTimeUnknown` = TRUE

The Compressor effect plugin is enabled for consistent loudness across
collections (defaults: center=0.4, range=0.35).

## Format-Specific Tools

| Tool   | Purpose                     | Required for              |
|--------|-----------------------------|---------------------------|
| ffmpeg | Audio capture / transcoding | Stream playback (URLs)    |
| ffprobe | Module subsong inspection   | MOD archive               |
| 7z     | Archive extraction          | YM collections            |
| unrar  | Archive extraction          | SNES RSN archives         |

These are **not** checked at startup. The bot tolerates their absence
until a format that needs them is accessed.

## Troubleshooting

### `RuntimeError: Missing required external tools`

The bot checks for `audacious`, `audtool`, and `pactl` before connecting
to Discord. Install the missing package(s) and restart.

```bash
# Debian/Ubuntu
sudo apt install audacious pulseaudio-utils ffmpeg p7zip-full unrar

# Arch Linux
sudo pacman -S audacious pulseaudio ffmpeg p7zip unrar
```

### Audacious D-Bus timeout

If `audtool version` does not respond within 20 seconds the bot logs a
warning and continues. This usually means Audacious started but its D-Bus
interface is slow. Restarting the bot usually resolves it.

### No audio in voice channel

1. Verify the virtual sink exists: `pactl list sinks short | grep ASMA_Bot`
2. Verify Audacious is playing: `audtool playback-playing`
3. Check that the sink is not muted: `pactl list sinks | grep -A5 ASMA_Bot`
4. Restart the bot: it re-creates the sink and reconnects Discord voice.
