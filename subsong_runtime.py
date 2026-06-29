"""Subsong detection and conversion helpers."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class SubsongRuntime:
    temp_dir: str
    logger: Any
    cache: dict[str, list[float]] = field(default_factory=dict)

    def get_subsongs(self, filepath: str) -> list[float]:
        if filepath in self.cache:
            return self.cache[filepath]

        durations: list[float] = []
        for sub in range(0, 20):
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-subsong",
                        str(sub),
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_entries",
                        "format=duration",
                        filepath,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if not result.stdout.strip():
                    break
                data = json.loads(result.stdout)
                duration = data.get("format", {}).get("duration")
                if duration is None:
                    break
                durations.append(float(duration))
            except Exception:
                break

        self.cache[filepath] = durations
        return durations

    def has_subsongs(self, filepath: str) -> bool:
        return len(self.get_subsongs(filepath)) > 1

    def convert_subsong(self, filepath: str, subsong: int, output_path: str) -> bool:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-subsong", str(subsong), "-i", filepath, "-ac", "1", "-ar", "48000", "-f", "wav", output_path],
                capture_output=True,
                timeout=60,
            )
            return os.path.exists(output_path) and os.path.getsize(output_path) > 100
        except Exception:
            return False

    def subsong_temp_path(self, filepath: str, subsong: int) -> str:
        basename = os.path.basename(filepath).rsplit(".", 1)[0]
        safe = "".join(char if char.isalnum() or char in " _-" else "_" for char in basename)
        return os.path.join(self.temp_dir, f"subsong_{safe}_{subsong}.wav")

    async def play_subsong(
        self,
        ctx,
        state,
        subsong: int,
        audacious_stop: Callable[[], None],
        audacious_play: Callable[[str], None],
        setup_monitor_source: Callable[[Any], None],
    ) -> bool:
        if not state.subsong_path:
            return False

        orig_path = state.subsong_path
        wav_path = self.subsong_temp_path(orig_path, subsong)
        ok = await asyncio.get_event_loop().run_in_executor(None, self.convert_subsong, orig_path, subsong, wav_path)
        if not ok:
            self.logger.error("Subsong %d conversion failed for %s", subsong, orig_path)
            return False

        state.set_subsong_wav(subsong, wav_path)
        state.set_current_subsong(subsong)

        await asyncio.get_event_loop().run_in_executor(None, audacious_stop)
        await asyncio.get_event_loop().run_in_executor(None, audacious_play, wav_path)
        state.set_current_path(wav_path)
        setup_monitor_source(state)
        return True

    def cleanup_subsong_temp_wavs(self, state) -> None:
        for wav in state.subsong_wavs:
            if wav and os.path.exists(wav):
                try:
                    os.remove(wav)
                except OSError:
                    pass
        state.reset_subsong_state()
