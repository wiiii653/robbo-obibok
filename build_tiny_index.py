#!/usr/bin/env python3
"""Build Tiny Music module index — scans archiwum/tiny/ for MOD/XM/IT/S3M/MED."""

import json, os, sys

ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "archiwum", "tiny")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "tiny_cache.json")

def main():
    mods_dir = os.path.join(ARCHIVE_DIR, "mods")
    if not os.path.isdir(mods_dir):
        print(f"❌ Not found: {mods_dir}")
        sys.exit(1)

    tracks = []
    for root, dirs, files in os.walk(mods_dir):
        for f in sorted(files):
            ext = f.rsplit(".", 1)[-1].lower() if "." in f else ""
            if ext in ("mod", "xm", "it", "s3m", "med", "dmf", "mo3", "mptm"):
                full = os.path.join(root, f)
                # Store path relative to ARCHIVE_DIR
                rel = os.path.relpath(full, ARCHIVE_DIR)
                fsize = os.path.getsize(full)
                tracks.append({
                    "path": rel,
                    "name": f.rsplit(".", 1)[0],
                    "size": fsize,
                })

    data = {"tracks": tracks, "count": len(tracks), "generated": __import__("time").time()}
    with open(CACHE_FILE, "w") as fp:
        json.dump(data, fp, indent=2)

    print(f"✅ Tiny Music index: {len(tracks)} tracks ({sum(t['size'] for t in tracks) / 1024 / 1024:.0f} MB)")
    print(f"   Cache: {CACHE_FILE}")

if __name__ == "__main__":
    main()
