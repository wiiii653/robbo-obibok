#!/usr/bin/env python3
"""Build ASMA local index — scans archiwum/asma/ for .sap files.

Output: asma_cache_local.json with relative paths, file sizes, and categories.

Usage:
    python build_asma_index.py

The generated cache is used by robbo in local-only mode (no internet crawling).
"""

import json
import os
from pathlib import Path

ARCHIVIUM = Path(__file__).resolve().parent / "archiwum" / "asma"
OUTPUT = Path(__file__).resolve().parent / "asma_cache_local.json"

TOP_DIRS = ["Composers", "Games", "Groups", "Misc", "Unknown"]


def main():
    entries = []
    total = 0
    for subdir in TOP_DIRS:
        d = ARCHIVIUM / subdir
        if not d.exists():
            print(f"[SKIP] {subdir}/ — directory not found")
            continue
        files = sorted(d.rglob("*.sap"))
        # Also check for .SAP (uppercase)
        files += sorted(d.rglob("*.SAP"))
        count = 0
        for f in files:
            rel = str(f.relative_to(ARCHIVIUM))
            size = os.path.getsize(f)
            entries.append({"path": rel, "size": size, "collection": subdir})
            count += 1
        print(f"[OK] {subdir}/: {count} .sap files")
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
