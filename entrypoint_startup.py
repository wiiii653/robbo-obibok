"""Startup and small persistence helpers for the entrypoint."""

from __future__ import annotations

import json
import os
import shutil
from typing import Any

import yaml


def load_config(root_dir: str, logger) -> dict[str, Any]:
    """Load config.yaml with defaults and a shallow recursive merge."""
    defaults: dict[str, Any] = {
        "command_prefix": "!",
        "asma": {
            "base_url": "https://asma.atari.org/asma/",
            "top_dirs": ["Composers/", "Games/", "Groups/", "Misc/", "Unknown/"],
            "crawl_timeout": 15,
            "cache_ttl": 24,
            "crawl_concurrency": 5,
        },
        "audio": {
            "sink_name": "asma_bot",
            "sample_rate": 48000,
            "channels": 2,
            "format": "s16le",
        },
        "playback": {
            "loop": True,
            "shuffle": True,
            "crossfade": 0,
        },
        "auto": {
            "start_channel": "",
            "empty_timeout": 60,
        },
    }
    cfg_path = os.path.join(root_dir, "config.yaml")
    if not os.path.exists(cfg_path):
        return defaults
    try:
        with open(cfg_path) as handle:
            user_cfg = yaml.safe_load(handle) or {}
        _deep_merge(defaults, user_cfg)
    except Exception as exc:
        logger.warning("Failed to load config.yaml: %s", exc)
    return defaults


def cleanup_orphaned_temp_dir(temp_dir: str, logger) -> None:
    """Remove temp dir from previous crashed sessions."""
    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info("Startup cleanup: removed temp dir")


def load_last_collection(last_collection_file: str) -> str | None:
    try:
        with open(last_collection_file) as handle:
            mode = handle.read().strip()
            if mode in ("asma", "hvsc", "modarchive", "ay", "tiny", "spc", "ym"):
                return mode
    except (FileNotFoundError, OSError):
        pass
    return None


def save_last_collection(last_collection_file: str, mode: str) -> None:
    try:
        with open(last_collection_file, "w") as handle:
            handle.write(mode)
    except OSError:
        pass


def atomic_json_write(path: str, data: dict[str, Any], logger) -> None:
    """Write JSON atomically to reduce corruption risk on crash."""
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as handle:
            json.dump(data, handle, indent=2)
        os.replace(tmp_path, path)
    except Exception as exc:
        logger.error("Failed atomic write to %s: %s", path, exc)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
