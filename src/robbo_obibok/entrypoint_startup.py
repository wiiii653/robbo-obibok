"""Startup and small persistence helpers for the entrypoint."""

from __future__ import annotations

import json
import os
import re
import shutil
from typing import Any

import yaml


def load_config(root_dir: str, logger) -> dict[str, Any]:
    """Load, merge, and validate config.yaml."""
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
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        logger.error("Failed to parse config.yaml: %s", exc)
        raise ValueError(f"Failed to parse config.yaml: {exc}") from exc
    if not isinstance(user_cfg, dict):
        raise ValueError("config.yaml must contain a mapping at the top level")
    _deep_merge(defaults, user_cfg)
    validate_config(defaults)
    return defaults


def validate_config(config: dict[str, Any]) -> None:
    """Raise ValueError with a field-specific message for invalid config."""
    _require_type(config, "command_prefix", str)
    if not config["command_prefix"]:
        raise ValueError("config.command_prefix must not be empty")

    guild_id = config.get("guild_id")
    if guild_id is not None and (
        not isinstance(guild_id, int) or isinstance(guild_id, bool) or guild_id <= 0
    ):
        raise ValueError("config.guild_id must be a positive integer")

    asma = _require_mapping(config, "asma")
    _require_type(asma, "base_url", str, prefix="asma")
    top_dirs = _require_type(asma, "top_dirs", list, prefix="asma")
    if not all(isinstance(item, str) and item for item in top_dirs):
        raise ValueError("config.asma.top_dirs must contain non-empty strings")
    _require_positive_int(asma, "crawl_timeout", prefix="asma")
    _require_positive_int(asma, "cache_ttl", prefix="asma")
    _require_positive_int(asma, "crawl_concurrency", prefix="asma")

    audio = _require_mapping(config, "audio")
    sink_name = _require_type(audio, "sink_name", str, prefix="audio")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", sink_name):
        raise ValueError("config.audio.sink_name contains unsupported characters")
    _require_positive_int(audio, "sample_rate", prefix="audio")
    channels = _require_positive_int(audio, "channels", prefix="audio")
    if channels not in (1, 2):
        raise ValueError("config.audio.channels must be 1 or 2")
    _require_type(audio, "format", str, prefix="audio")

    playback = _require_mapping(config, "playback")
    _require_type(playback, "loop", bool, prefix="playback")
    _require_type(playback, "shuffle", bool, prefix="playback")
    crossfade = _require_int(playback, "crossfade", prefix="playback")
    if crossfade < 0:
        raise ValueError("config.playback.crossfade must be zero or greater")

    auto = _require_mapping(config, "auto")
    _require_type(auto, "start_channel", str, prefix="auto")
    empty_timeout = _require_int(auto, "empty_timeout", prefix="auto")
    if empty_timeout < 0:
        raise ValueError("config.auto.empty_timeout must be zero or greater")

    for optional_mapping in ("hvsc", "modarchive", "ay", "ym", "tiny", "snes"):
        if optional_mapping in config and not isinstance(config[optional_mapping], dict):
            raise ValueError(f"config.{optional_mapping} must be a mapping")


def _require_mapping(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    return _require_type(mapping, key, dict)


def _require_type(
    mapping: dict[str, Any],
    key: str,
    expected_type: type,
    *,
    prefix: str = "",
):
    value = mapping.get(key)
    if not isinstance(value, expected_type):
        field = f"{prefix}.{key}" if prefix else key
        raise ValueError(f"config.{field} must be {expected_type.__name__}")
    return value


def _require_int(mapping: dict[str, Any], key: str, *, prefix: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"config.{prefix}.{key} must be int")
    return value


def _require_positive_int(mapping: dict[str, Any], key: str, *, prefix: str) -> int:
    value = _require_int(mapping, key, prefix=prefix)
    if value <= 0:
        raise ValueError(f"config.{prefix}.{key} must be positive")
    return value


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
        raise


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def prepare_app_environment(app_config, logger) -> None:
    """Create temp dir and clean up orphaned files from previous runs.

    .. deprecated::
        Moved from :mod:`domain_config`. Will be removed when callers
        are updated.
    """
    cleanup_orphaned_temp_dir(app_config.temp_dir, logger)
    os.makedirs(app_config.temp_dir, exist_ok=True)


def build_app_config(root_dir: str, logger):
    """Load config, derive app config, and prepare environment.

    .. deprecated::
        Moved from :mod:`domain_config`. Will be removed when callers
        are updated.
    """
    from .domain_config import derive_app_config
    config = load_config(root_dir, logger)
    app_config = derive_app_config(root_dir, config)
    prepare_app_environment(app_config, logger)
    return app_config
