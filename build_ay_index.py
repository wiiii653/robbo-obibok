#!/usr/bin/env python3
"""Szybki skaner lokalnego archiwum AY — buduje listę ścieżek (wzorem hvsc_cache.json / asma_cache.json)."""

import json
import os
from pathlib import Path

ARCHIVIUM = Path(__file__).resolve().parent / "archiwum" / "ay"
OUTPUT = Path(__file__).resolve().parent / "ay_cache.json"

SUBDIRS = {
    "aygor": "AYGOR — Original AY compositions",
    "ironfist": "Ironfist's AY Collection — Game rips",
    "tr_songs": "Tr_Songs v6.7 — ZX Spectrum Tracker Music",
    "solo_cpc": "SoLOCPC — Amstrad CPC AY Collection",
    "ts_music": "Turbo Sound Music Collection v3.1",
    "bulba": "Bulba's AY rebuilt collection",
}

def main():
    entries = []
    total = 0
    for subdir, desc in SUBDIRS.items():
        d = ARCHIVIUM / subdir
        if not d.exists():
            print(f"[SKIP] {subdir} — brak katalogu")
            continue
        files = sorted(d.rglob("*.ay"))
        count = 0
        for f in files:
            rel = str(f.relative_to(ARCHIVIUM))
            size = os.path.getsize(f)
            entries.append({"path": rel, "size": size, "collection": subdir})
            count += 1
        print(f"[OK] {subdir}: {count} .ay plików — {desc}")
        total += count

    cache = {
        "version": 2,
        "total": total,
        "tracks": entries,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    print(f"\n[DONE] Zapisano {total} tracków do {OUTPUT}")

if __name__ == "__main__":
    main()
