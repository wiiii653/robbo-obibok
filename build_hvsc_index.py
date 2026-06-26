#!/usr/bin/env python3
"""Build HVSC local index — scans archiwum/hvsc/C64Music/ for .sid files.

Output: hvsc_cache_local.json with relative paths, file sizes, and categories.

Usage:
    python build_hvsc_index.py

The generated cache is used by robbo in local-only mode (no internet download).
Supports HVSC with 60k+ SID tracks fully local.
"""

import json
import os
from pathlib import Path

ARCHIVIUM = Path(__file__).resolve().parent / "archiwum" / "hvsc" / "C64Music"
OUTPUT = Path(__file__).resolve().parent / "hvsc_cache_local.json"

# Only scan these content directories (skip disk images, docs, etc.)
CONTENT_DIRS = ["DEMOS", "GAMES", "MUSICIANS"]


def main():
    entries = []
    total = 0
    for subdir in CONTENT_DIRS:
        d = ARCHIVIUM / subdir
        if not d.exists():
            print(f"[SKIP] {subdir}/ — directory not found")
            continue
        files = sorted(d.rglob("*.sid"))
        # Also check for .SID (uppercase) — some files may use uppercase
        files += sorted(d.rglob("*.SID"))
        # Deduplicate while preserving order
        seen = set()
        unique_files = []
        for f in files:
            p = str(f)
            if p not in seen:
                seen.add(p)
                unique_files.append(f)
        count = 0
        for f in unique_files:
            rel = str(f.relative_to(ARCHIVIUM))
            size = os.path.getsize(f)
            entries.append({"path": rel, "size": size, "collection": subdir})
            count += 1
        print(f"[OK] {subdir}/: {count} .sid files")
        total += count

    cache = {
        "version": 1,
        "total": total,
        "tracks": entries,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    print(f"\n[DONE] Saved {total} tracks to {OUTPUT}")


if __name__ == "__main__":
    main()
