"""Playback asset helpers for local archive resolution, SAP downloads, and YM decoding."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from hashlib import md5
from pathlib import Path
from typing import Awaitable, Callable

import aiohttp
from download_safety import read_response_limited, resolve_existing_path

MAX_SAP_DOWNLOAD_BYTES = 16 * 1024 * 1024


@dataclass(slots=True)
class PlaybackAssetRuntime:
    asma_base: str
    asma_dir: str
    hvsc_base: str
    hvsc_dir: str
    ym_temp_dir: str
    logger: logging.Logger
    build_temp_path: Callable[[str], str]
    get_shared_session: Callable[[], Awaitable[aiohttp.ClientSession]]
    ym_cache_max_size: int = 200 * 1024 * 1024
    ym_cache_max_entries: int = 50
    _ym_last_wav_path: str | None = None

    def set_ym_last_wav_path(self, path: str | None) -> None:
        self._ym_last_wav_path = path

    def resolve_local_path(self, url: str) -> str | None:
        if url.startswith(self.asma_base):
            rel = url[len(self.asma_base):]
            local = resolve_existing_path(self.asma_dir, rel)
            if local:
                self.logger.info("Local ASMA path: %s", local)
                return local
        if url.startswith(self.hvsc_base):
            rel = url[len(self.hvsc_base):]
            local = resolve_existing_path(self.hvsc_dir, rel)
            if local:
                self.logger.info("Local HVSC path: %s", local)
                return local
        return None

    async def download_sap(self, url: str, retries: int = 2) -> str:
        filepath = self.build_temp_path(url)
        last_err: BaseException | None = None
        session = await self.get_shared_session()
        for attempt in range(retries + 1):
            try:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await read_response_limited(resp, max_bytes=MAX_SAP_DOWNLOAD_BYTES)
                await asyncio.to_thread(Path(filepath).write_bytes, data)
                return filepath
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_err = exc
                if attempt < retries:
                    await asyncio.sleep(1)
        if last_err is None:
            raise RuntimeError(f"SAP download failed without an exception: {url}")
        raise last_err

    def ym_to_wav(self, ym_path: str) -> str:
        os.makedirs(self.ym_temp_dir, exist_ok=True)
        work_dir = os.path.join(self.ym_temp_dir, md5(ym_path.encode()).hexdigest()[:12])
        os.makedirs(work_dir, exist_ok=True)
        wav_path = os.path.join(work_dir, "decoded.wav")
        if os.path.exists(wav_path):
            return wav_path

        extract_ok = False
        try:
            extract_result = subprocess.run(
                ["7z", "x", "-y", ym_path, f"-o{work_dir}"],
                capture_output=True,
                timeout=15,
            )
            extract_ok = extract_result.returncode == 0
        except Exception:
            pass

        raw_ym = ym_path
        if extract_ok:
            raw_candidates = [name for name in os.listdir(work_dir) if name.upper().endswith(".YM")]
            if raw_candidates:
                raw_ym = os.path.join(work_dir, raw_candidates[0])

        self.logger.info("YM→WAV: converting %s -> %s", os.path.basename(raw_ym), wav_path)
        result = subprocess.run(
            ["ym2wav", raw_ym, wav_path],
            capture_output=True,
            timeout=300,
            text=True,
        )
        for line in result.stdout.splitlines():
            self.logger.info("ym2wav: %s", line)
        for line in result.stderr.splitlines():
            self.logger.warning("ym2wav err: %s", line)

        if result.returncode != 0 or not os.path.exists(wav_path):
            raise RuntimeError(f"ym2wav failed (exit={result.returncode}) for {ym_path}")

        self.logger.info("YM→WAV: done — %d bytes -> %d bytes", os.path.getsize(ym_path), os.path.getsize(wav_path))
        self._ym_cache_enforce_limits()
        return wav_path

    def ym_cleanup(self) -> None:
        if self._ym_last_wav_path and os.path.exists(self._ym_last_wav_path):
            try:
                parent = os.path.dirname(self._ym_last_wav_path)
                os.remove(self._ym_last_wav_path)
                for name in os.listdir(parent):
                    if name == os.path.basename(self._ym_last_wav_path):
                        continue
                    try:
                        os.remove(os.path.join(parent, name))
                    except Exception:
                        pass
                self.logger.info("YM cleanup: removed %s", parent)
            except Exception as exc:
                self.logger.warning("YM cleanup error: %s", exc)
        self._ym_last_wav_path = None

    def _ym_cache_enforce_limits(self) -> None:
        if not os.path.isdir(self.ym_temp_dir):
            return
        entries = []
        for name in os.listdir(self.ym_temp_dir):
            directory = os.path.join(self.ym_temp_dir, name)
            if not os.path.isdir(directory):
                continue
            try:
                mtime = os.path.getmtime(directory)
                size = sum(
                    os.path.getsize(os.path.join(directory, child))
                    for child in os.listdir(directory)
                    if os.path.isfile(os.path.join(directory, child))
                )
                entries.append((mtime, size, directory))
            except OSError:
                pass
        entries.sort(key=lambda item: item[0])
        total_size = sum(item[1] for item in entries)
        while entries and (total_size > self.ym_cache_max_size or len(entries) > self.ym_cache_max_entries):
            _mtime, size, directory = entries.pop(0)
            shutil.rmtree(directory, ignore_errors=True)
            total_size -= size
            self.logger.info("YM cache LRU evict: %s (%dKB)", os.path.basename(directory), size // 1024)
