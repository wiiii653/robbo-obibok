"""Static collection configuration and flip ordering."""

from __future__ import annotations

from typing import Callable

from .collection_specs import CollectionSpec

FLIP_ORDER = ["hvsc", "asma", "modarchive", "ay", "ym", "tiny", "spc"]
FLIP_SEQ = ["🟣HVSC", "🟢ASMA", "🟠Mod", "🔵AY", "🎹YM", "🎵Tiny", "🔴SNES"]


def build_collections(
    *,
    load_asma_local_cache: Callable[[], list[str] | None],
    load_hvsc_local_cache: Callable[[], list[str] | None],
    load_modarchive_cache: Callable[[], list[str] | None],
    load_ay_cache: Callable[[], list[str] | None],
    load_ym_cache: Callable[[], list[str] | None],
    load_tiny_cache: Callable[[], list[str] | None],
    load_snes_cache: Callable[[], list[str] | None],
) -> dict[str, CollectionSpec]:
    return {
        "hvsc": CollectionSpec(
            label="HVSC",
            flip_tag="🟣HVSC",
            load_func=load_hvsc_local_cache,
            fallback_func=None,
            already_msg="📀 **Already in C64 SID mode.** Use `!play` to start!",
            load_msg="🔄 **Loading C64 SID collection (60,000+ tracks)...**",
            flip_load_msg="🔄 Loading C64 SID collection (60,000+ tracks)...",
            error_msg="❌ Failed to load HVSC local cache. Run `python build_hvsc_index.py` first.",
            ready_msg="📀 **C64 SID collection ready — {count} tracks!**",
            flip_ready_msg="🟣 **Switched to C64 SID (HVSC) — {count} tracks!**",
            flip_fail_msg="❌ Could not load HVSC. Try `!hvsc` manually.",
            log_msg="HVSC: collection switched, %d tracks loaded",
        ),
        "asma": CollectionSpec(
            label="ASMA",
            flip_tag="🟢ASMA",
            load_func=load_asma_local_cache,
            fallback_func=None,
            already_msg=None,
            load_msg=None,
            error_msg=None,
            ready_msg="🟢 **Switched to ASMA Atari SAP — {count} tracks!**",
            ready_empty_msg="🟢 **Switched to ASMA Atari SAP.** Use `!play` to start.",
            flip_ready_msg="🟢 **Switched to Atari SAP (ASMA)!**",
            flip_ready_empty_msg="🟢 **Switched to Atari SAP (ASMA).**",
            log_msg="ASMA: collection switched",
            log_args=False,
            allow_empty=True,
        ),
        "modarchive": CollectionSpec(
            label="ModArchive",
            flip_tag="🟠Mod",
            load_func=load_modarchive_cache,
            fallback_func=None,
            already_msg="🟠 **Already in ModArchive mode.** Use `!play` to start!",
            load_msg="🟠 **Loading ModArchive collection (100,000+ modules)...**",
            error_msg="❌ ModArchive cache not found. Run `build_modarchive_index.py` first!\nThe index builder is running in the background — wait a few minutes and try again.",
            ready_msg="🟠 **ModArchive collection ready — {count} modules!**\nFastTracker / ProTracker / ScreamTracker / Impulse Tracker — all formats!",
            flip_ready_msg="🟠 **Switched to ModArchive — {count} modules!**",
            flip_fail_msg="🟠 **ModArchive cache not ready.** Staying on {prev}.",
            log_msg="ModArchive: collection switched, %d tracks loaded",
        ),
        "ay": CollectionSpec(
            label="AY",
            flip_tag="🔵AY",
            load_func=load_ay_cache,
            fallback_func=None,
            already_msg="🔵 **Already in ZX Spectrum AY mode.** Use `!play` to start!",
            load_msg="🔵 **Loading local AY archive (4,500+ tracks)...**",
            error_msg="❌ AY cache not found. Run `build_ay_index.py` first!",
            ready_msg="🔵 **ZX Spectrum AY archive ready — {count} tracks!**\nAY-3-8910 chiptunes — AYGOR / Ironfist / Tr_Songs / SoLOCPC / Bulba",
            flip_ready_msg="🔵 **Switched to ZX Spectrum AY — {count} tracks!**",
            flip_fail_msg="🔵 **AY cache not ready.** Staying on {prev}.",
            log_msg="AY: collection switched, %d tracks loaded",
        ),
        "ym": CollectionSpec(
            label="YM",
            flip_tag="🎹YM",
            load_func=load_ym_cache,
            fallback_func=None,
            already_msg="🎹 **Already in Atari ST YM mode.** Use `!play` to start!",
            load_msg="🎹 **Loading local YM archive (7,200+ Atari ST chiptunes)...**",
            error_msg="❌ YM cache not found. Run `build_ym_index.py` first!",
            ready_msg="🎹 **Atari ST YM archive ready — {count} tracks!**\nYM2149 chiptunes — Mad Max / Scavenger / Big Alec / David Whittaker / Jochen Hippel",
            flip_ready_msg="🎹 **Switched to Atari ST YM — {count} tracks!**",
            flip_fail_msg="🎹 **YM cache not ready.** Staying on {prev}.",
            log_msg="YM: collection switched, %d tracks loaded",
        ),
        "tiny": CollectionSpec(
            label="Tiny",
            flip_tag="🎵Tiny",
            load_func=load_tiny_cache,
            fallback_func=None,
            already_msg="🎵 **Already in Tiny Music mode.** Use `!play` to start!",
            load_msg="🎵 **Loading Tiny Music archive (418 curated demoscene modules)...**",
            error_msg="❌ Tiny Music cache not found. Run `build_tiny_index.py` first!",
            ready_msg="🎵 **Tiny Music archive ready — {count} modules!**\nCurated demoscene — MOD / XM / IT / S3M / MED / DMF",
            flip_ready_msg="🎵 **Switched to Tiny Music — {count} modules!**",
            flip_fail_msg="🎵 **Tiny cache not ready.** Staying on {prev}.",
            log_msg="Tiny: collection switched, %d tracks loaded",
        ),
        "spc": CollectionSpec(
            label="SNES",
            flip_tag="🔴SNES",
            load_func=load_snes_cache,
            fallback_func=None,
            already_msg="🔴 **Already in SNES SPC mode.** Use `!play` to start!",
            load_msg="🔴 **Loading SNES SPC collection (Super Nintendo chiptunes)...**",
            error_msg="❌ SNES SPC cache not found. Run `build_snes_index.py` first!",
            ready_msg="🔴 **SNES SPC collection ready — {count} games!**\nSuper Nintendo chiptunes via SNESmusic.org — download & play on demand",
            flip_ready_msg="🔴 **Switched to SNES SPC — {count} games!**",
            flip_fail_msg="🔴 **SNES cache not ready.** Staying on {prev}.",
            log_msg="SNES: collection switched, %d game sets loaded",
        ),
    }
