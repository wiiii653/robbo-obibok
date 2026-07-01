#!/usr/bin/env python3
"""Extract ModArchive 2007 snapshot into flat module files.

Outer zips under modarchive_textfiles/ contain inner zips (name.zip),
which contain the actual module file. This script extracts every module
to archiwum/modarchive/extracted/ with a unique name (id_filename.ext).

After extraction, the outer+inner zips can be deleted (~30GB saved).
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

ARCHIVE_DIR = Path(__file__).resolve().parent / "archiwum"
SNAPSHOT_DIR = ARCHIVE_DIR / "modarchive_textfiles" / "modarchive_2007_official_snapshot_120000_modules"
ADDENDUM_DIR = ARCHIVE_DIR / "modarchive_textfiles" / "modarchive_2007_official_snapshot_addendum1"
OUTPUT_DIR = ARCHIVE_DIR / "modarchive" / "extracted"
CACHE_FILE = Path(__file__).resolve().parent / "modarchive_cache.json"

# Which directories to process
ZIP_SOURCES = [
    ("main", SNAPSHOT_DIR),
    ("addendum1", ADDENDUM_DIR),
]

# Track already-used filenames to avoid collisions
_used_names: set[str] = set()


def safe_filename(module_id: int, original_name: str) -> str:
    """Build a unique filename: {id}_{sanitized_name}."""
    # Sanitize: keep only safe chars, limit length
    name = original_name.strip()
    name = re.sub(r'[^\w\.\-\(\) ]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name[:120]  # keep it reasonable
    candidate = f"{module_id}_{name}"
    if candidate not in _used_names:
        _used_names.add(candidate)
        return candidate
    # collision - append counter
    for i in range(1, 100):
        candidate = f"{module_id}_{i}_{name}"
        if candidate not in _used_names:
            _used_names.add(candidate)
            return candidate
    # ultimate fallback
    candidate = f"{module_id}_{hash(name) & 0xFFFFFFFF}_{name[:40]}"
    _used_names.add(candidate)
    return candidate


def extract_modules_from_outer_zip(outer_path: Path, output_dir: Path) -> int:
    """Extract all modules from one outer zip (which contains inner zips)."""
    count = 0
    try:
        with zipfile.ZipFile(str(outer_path), 'r') as outer:
            inner_names = [n for n in outer.namelist() if n.lower().endswith('.zip')]
            for inner_name in inner_names:
                try:
                    # Read inner zip in memory
                    inner_data = outer.read(inner_name)
                    with zipfile.ZipFile(io.BytesIO(inner_data)) as inner:
                        module_names = [m for m in inner.namelist() if not m.endswith('/')]
                        for module_name in module_names:
                            # Extract module data
                            module_data = inner.read(module_name)
                            # Build safe filename: try to extract module ID from inner zip name
                            mod_id_match = re.match(r'(\d+)_?', Path(inner_name).stem)
                            mod_id = int(mod_id_match.group(1)) if mod_id_match else hash(inner_name) & 0x7FFFFFFF
                            safe_name = safe_filename(mod_id, module_name if module_name != 'Unknown' else inner_name.replace('.zip', '.mod'))
                            out_path = output_dir / safe_name
                            if not out_path.exists():
                                out_path.write_bytes(module_data)
                            count += 1
                except Exception as e:
                    print(f"  [WARN] Failed to extract {inner_name} from {outer_path.name}: {e}", file=sys.stderr)
                    continue
    except Exception as e:
        print(f"  [ERROR] Failed to read {outer_path}: {e}", file=sys.stderr)
    return count


def main():
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    total_modules = 0
    total_zips = 0

    for source_name, source_dir in ZIP_SOURCES:
        if not source_dir.is_dir():
            print(f"[SKIP] {source_name}: {source_dir} not found")
            continue

        # Collect all outer zip files
        outer_zips = sorted(source_dir.rglob('*.zip'))
        print(f"[{source_name}] Found {len(outer_zips)} outer zip files in {source_dir}")

        for i, outer_path in enumerate(outer_zips):
            if i % 50 == 0 and i > 0:
                print(f"  [{source_name}] {i}/{len(outer_zips)} zips processed, {total_modules} modules so far")

            count = extract_modules_from_outer_zip(outer_path, output_dir)
            if count > 0:
                total_modules += count
                total_zips += 1

    print(f"\n✅ Done: {total_modules} modules extracted, {total_zips} outer zips processed")
    print(f"   Output: {output_dir}")

    # Quick stats
    total_size = sum(f.stat().st_size for f in output_dir.iterdir() if f.is_file())
    print(f"   Total size: {total_size / 1024 / 1024:.1f} MB, files: {len(list(output_dir.iterdir()))}")


if __name__ == "__main__":
    main()
