#!/usr/bin/env python3
"""
ModArchive Full Index Builder
=============================
Scrapes modarchive.org browse pages (A-Z) and builds a JSON cache
of module IDs with their filenames and download URLs.

Usage:
    python build_modarchive_index.py
    # resumes automatically if modarchive_cache_partial.json exists

Output:
    modarchive_cache.json            — final cache (list of {id, name, url})
    modarchive_cache_partial.json    — progress checkpoint (auto-removed on finish)
"""

import asyncio
import json
import logging
import os
import re
import time

import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("modarchive-indexer")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load config.yaml for ModArchive URLs (fallback to hardcoded defaults)
try:
    import yaml
    cfg_path = os.path.join(ROOT_DIR, "config.yaml")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            _cfg = yaml.safe_load(f) or {}
        ma = _cfg.get("modarchive", {})
        BASE_URL = ma.get("base_url", "https://modarchive.org/index.php")
        DOWNLOAD_BASE = ma.get("download_url", "https://api.modarchive.org/downloads.php")
        cache_file = ma.get("cache_file", "modarchive_cache.json")
    else:
        raise FileNotFoundError
except Exception:
    BASE_URL = "https://modarchive.org/index.php"
    DOWNLOAD_BASE = "https://api.modarchive.org/downloads.php"
    cache_file = "modarchive_cache.json"

FINAL_CACHE = os.path.join(ROOT_DIR, cache_file)
PARTIAL_CACHE = os.path.join(ROOT_DIR, cache_file.replace(".json", "_partial.json"))

# Letters to scan
LETTERS = [chr(i) for i in range(ord("A"), ord("Z") + 1)]

# Concurrency
CONCURRENT = 8
DELAY_PER_BATCH = 0.5
MAX_RETRIES = 3

USER_AGENT = "Mozilla/5.0 (compatible; BorutaBot/1.0; modarchive-radio)"


# ── Helpers ──────────────────────────────────────────────────────────

def load_partial() -> tuple[dict[str, list], list[dict]]:
    completed: dict[str, list] = {}
    modules: list[dict] = []
    if os.path.exists(PARTIAL_CACHE):
        try:
            with open(PARTIAL_CACHE) as f:
                data = json.load(f)
            modules = data.get("modules", [])
            completed = data.get("completed", {})
            log.info("Loaded partial: %d modules, %d letters in progress",
                      len(modules), len(completed))
        except Exception as e:
            log.warning("Could not load partial cache: %s", e)
    return completed, modules


def save_partial(completed: dict[str, list], modules: list[dict]):
    data = {
        "completed": completed,
        "modules": modules,
        "timestamp": time.time(),
        "count": len(modules),
    }
    tmp = PARTIAL_CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, PARTIAL_CACHE)


def save_final(modules: list[dict]):
    tmp = FINAL_CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(modules, f, indent=2)
    os.replace(tmp, FINAL_CACHE)
    log.info("✅ Final cache written: %d modules -> %s", len(modules), FINAL_CACHE)


def extract_module_ids(html: str) -> list[dict]:
    modules = []
    for m in re.finditer(r'downloads\.php\?moduleid=(\d+)#([^"\'&\s]+)', html):
        modules.append({
            "id": int(m.group(1)),
            "name": m.group(2),
            "url": f"{DOWNLOAD_BASE}?moduleid={int(m.group(1))}",
        })
    return modules


def count_pages(html: str) -> int:
    pages = re.findall(r'page=(\d+)#mods', html)
    if pages:
        return max(int(p) for p in pages)
    return 1 if extract_module_ids(html) else 0


# ── Core Indexer ─────────────────────────────────────────────────────

async def fetch_page(session: aiohttp.ClientSession, letter: str, page: int) -> str | None:
    params = {"request": "view_by_list", "query": letter, "page": page}
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.get(BASE_URL, params=params, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    log.warning("Page %s-%d: HTTP %d, retry %d/%d", letter, page, resp.status, attempt, MAX_RETRIES)
                    await asyncio.sleep(2 ** attempt)
                    continue
                text = await resp.text()
                if len(text) > 500 and "Invalid" not in text:
                    return text
                log.warning("Page %s-%d: suspicious (%d bytes), retry %d/%d", letter, page, len(text), attempt, MAX_RETRIES)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.warning("Page %s-%d: %s, retry %d/%d", letter, page, e, attempt, MAX_RETRIES)
        if attempt < MAX_RETRIES:
            await asyncio.sleep(2 ** attempt)
    return None


async def process_letter(session: aiohttp.ClientSession, sem: asyncio.Semaphore,
                         letter: str, completed: dict[str, list],
                         modules: list[dict]) -> tuple[int, int]:
    """Process all pages for a letter. Returns (new_modules_added, total_pages)."""

    # --- 1. Fetch page 1 to get total page count + modules ---
    page1 = await fetch_page(session, letter, 1)
    if page1 is None:
        log.warning("Letter %s: page 1 failed, skipping", letter)
        return 0, 0

    total_pages = count_pages(page1)
    if total_pages == 0:
        log.info("Letter %s: no modules found", letter)
        return 0, 0

    log.info("Letter %s: %d pages, ~%d+ modules", letter, total_pages, len(extract_module_ids(page1)))

    # --- 2. Determine which pages we still need ---
    done_for_letter = set(completed.get(letter, []))
    if done_for_letter:
        log.info("  Already done: %d/%d pages", len(done_for_letter), total_pages)

    # Process page 1
    if 1 not in done_for_letter:
        mods = extract_module_ids(page1)
        modules.extend(mods)
        completed.setdefault(letter, []).append(1)
        done_for_letter.add(1)

    new_count = len(extract_module_ids(page1))
    pages_processed = 1

    # --- 3. Process remaining pages in concurrent batches ---
    remaining_pages = [p for p in range(2, total_pages + 1) if p not in done_for_letter]
    batch_size = CONCURRENT
    checkpoint_counter = 0

    for i in range(0, len(remaining_pages), batch_size):
        batch = remaining_pages[i:i + batch_size]

        # Fetch batch concurrently
        async def fetch_one(pg):
            async with sem:
                return pg, await fetch_page(session, letter, pg)

        results = await asyncio.gather(*[fetch_one(p) for p in batch])

        # Small delay between batches to be polite
        await asyncio.sleep(DELAY_PER_BATCH)

        for pg, html in results:
            if html is None:
                continue
            mods = extract_module_ids(html)
            if mods:
                modules.extend(mods)
                new_count += len(mods)
            completed.setdefault(letter, []).append(pg)
            pages_processed += 1

        checkpoint_counter += len(batch)
        if checkpoint_counter >= 100:
            save_partial(completed, modules)
            log.info("  %s: %d/%d pages, %d new, %d total",
                     letter, pages_processed, total_pages, new_count, len(modules))
            checkpoint_counter = 0

    save_partial(completed, modules)
    log.info("✅ Letter %s done: %d pages processed, %d new modules (total: %d)",
             letter, pages_processed, new_count, len(modules))
    return new_count, total_pages


async def main():
    completed, modules = load_partial()

    connector = aiohttp.TCPConnector(limit=CONCURRENT, limit_per_host=CONCURRENT)
    sem = asyncio.Semaphore(CONCURRENT)

    start_ts = time.time()

    async with aiohttp.ClientSession(connector=connector) as session:
        for letter in LETTERS:
            # Skip if letter fully completed
            done = set(completed.get(letter, []))
            if done:
                # We don't know total_pages yet, but if more than 0 pages done, still need to process
                pass
            await process_letter(session, sem, letter, completed, modules)

    elapsed = time.time() - start_ts

    # Deduplicate
    seen = set()
    unique = []
    for m in modules:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)
    modules = unique

    save_final(modules)

    # Cleanup partial
    if os.path.exists(PARTIAL_CACHE):
        os.remove(PARTIAL_CACHE)

    log.info("🎉 DONE: %d unique modules in %.1f minutes",
             len(modules), elapsed / 60)


if __name__ == "__main__":
    asyncio.run(main())
