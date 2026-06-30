"""Audio process control helpers separated from playback monitoring policy."""

from __future__ import annotations

import subprocess
import time
from typing import Callable, Iterable

from app_state import PlaylistState


COLLECTION_VOLUMES = {
    "hvsc": 120,
    "asma": 100,
    "modarchive": 100,
    "ay": 100,
    "ym": 100,
    "tiny": 100,
    "spc": 100,
}

_audacious_ready = False


def setup_virtual_sink(sink_name: str) -> None:
    result = subprocess.run(["pactl", "list", "sinks", "short"], capture_output=True, text=True)
    if sink_name not in result.stdout:
        subprocess.run(
            [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={sink_name}",
                "sink_properties=device.description=ASMA_Bot",
            ],
            check=False,
        )


def ensure_audacious(logger) -> None:
    global _audacious_ready
    if _audacious_ready:
        result = subprocess.run(["pgrep", "-x", "audacious"], capture_output=True)
        if result.returncode == 0:
            ready = subprocess.run(["audtool", "version"], capture_output=True, timeout=2)
            if ready.returncode == 0:
                return
            logger.warning("Audacious process alive but audtool unresponsive — restarting")
            subprocess.run(["pkill", "-x", "audacious"], capture_output=True)
        _audacious_ready = False
    subprocess.Popen(["audacious", "--headless"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        ready = subprocess.run(["audtool", "version"], capture_output=True, timeout=2)
        if ready.returncode == 0:
            _audacious_ready = True
            return
        time.sleep(1)
    logger.warning("Audacious D-Bus not ready after 20s, continuing anyway")


def setup_audacious_sid_config(logger) -> None:
    subprocess.run(["audtool", "config-set", "SID Player:playMaxTimeEnable", "TRUE"], capture_output=True)
    subprocess.run(["audtool", "config-set", "SID Player:playMaxTime", "180"], capture_output=True)
    subprocess.run(["audtool", "config-set", "SID Player:playMaxTimeUnknown", "TRUE"], capture_output=True)
    logger.info("Audacious SID plugin config set")

    # Enable the Compressor effect plugin for consistent loudness across collections.
    # Defaults come from ~/.config/audacious/config (center=0.4, range=0.35).
    subprocess.run(["audtool", "plugin-enable", "compressor", "TRUE"], capture_output=True)
    logger.info("Audacious Compressor plugin enabled")


def set_volume_for_collection(mode: str, sink_name: str, logger) -> None:
    vol = COLLECTION_VOLUMES.get(mode, 100)
    subprocess.run(["pactl", "set-sink-volume", sink_name, f"{vol}%"], capture_output=True)
    logger.info("Volume set to %d%% for collection %s", vol, mode)


def move_playback_to_sink(sink_name: str) -> None:
    result = subprocess.run(
        ["pactl", "list", "sink-inputs", "short"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields and fields[0].isdigit():
            subprocess.run(
                ["pactl", "move-sink-input", fields[0], sink_name],
                capture_output=True,
            )


def audacious_play(filepath: str, sink_name: str, logger) -> bool:
    """Start Audacious playback. Returns True if playback started."""
    ensure_audacious(logger)
    subprocess.run(["audtool", "playlist-clear"], capture_output=True)
    subprocess.run(["audtool", "playlist-addurl", filepath], capture_output=True)
    for attempt in range(3):
        subprocess.run(["audtool", "playback-play"], capture_output=True)
        time.sleep(0.5)
        result = subprocess.run(["audtool", "playback-playing"], capture_output=True)
        if result.returncode == 0:
            break
        logger.warning("audacious_play: attempt %d failed, retrying...", attempt + 1)
    else:
        logger.error("audacious_play: all 3 attempts failed for %s, clearing playlist", filepath)
        subprocess.run(["audtool", "playlist-clear"], capture_output=True)
        return False
    move_playback_to_sink(sink_name)
    return True


def audacious_stop() -> None:
    subprocess.run(["audtool", "playback-stop"], capture_output=True)
    subprocess.run(["audtool", "playlist-clear"], capture_output=True)


def audacious_kill() -> None:
    subprocess.run(["audtool", "playback-stop"], capture_output=True)
    subprocess.run(["pkill", "-x", "audacious"], capture_output=True)


def audacious_song() -> str:
    result = subprocess.run(["audtool", "current-song"], capture_output=True, text=True)
    return result.stdout.strip()


def is_playing() -> bool:
    result = subprocess.run(["audtool", "playback-playing"], capture_output=True)
    return result.returncode == 0


def stop_all_players(
    guild_states: Iterable[PlaylistState],
    cleanup_subsong_temp_wavs: Callable[[PlaylistState], None],
) -> None:
    audacious_stop()
    for state in guild_states:
        cleanup_subsong_temp_wavs(state)


def audtool_output_length() -> int:
    result = subprocess.run(["audtool", "current-song-output-length-seconds"], capture_output=True, text=True)
    try:
        return int(result.stdout.strip())
    except (ValueError, OSError):
        return -1


def audtool_song_length() -> int:
    result = subprocess.run(["audtool", "current-song-length-seconds"], capture_output=True, text=True)
    try:
        return int(result.stdout.strip())
    except (ValueError, OSError):
        return -1
