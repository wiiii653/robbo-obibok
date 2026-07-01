#!/usr/bin/env python3
"""Build SPC collection index from SNESmusic.org.

Scrapes game listings A-Z, extracts set IDs, then visits each
set profile to grab the spcNow download parameter and metadata.
Caches everything to snes_cache.json.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

# ── Configuration ──────────────────────────────────────────────────
SNES_BASE = "https://snesmusic.org/v2/"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snes_cache.json")
REQUEST_DELAY = 0.3  # seconds between requests to be polite
USER_AGENT = "Mozilla/5.0 (compatible; HermesBot/1.0; +https://github.com/nousresearch/hermes)"

# ── Scraping Helpers ───────────────────────────────────────────────

def fetch(url: str) -> str:
    """Fetch a URL and return HTML text."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_game_list(html: str) -> list[dict]:
    """Extract game entries (name + set_id) from a game listing page."""
    games = []
    # Pattern: <b><a href='profile.php?profile=set&amp;selected=XXXXX'>Name</a></b>
    # Also need to catch the <br /> after each entry
    # Using regex because the HTML is fairly consistent
    pattern = (
        r"<b><a\s+href='profile\.php\?profile=set&amp;selected=(\d+)'>([^<]+)</a></b>"
    )
    for match in re.finditer(pattern, html):
        set_id = match.group(1)
        name = match.group(2)
        games.append({"set_id": set_id, "name": name})
    return games


def parse_profile(html: str, set_id: str) -> dict | None:
    """Extract spcNow, composer, track count from a set profile page."""
    result = {"set_id": set_id}

    # Does it have a download link?
    dl_match = re.search(r"download\.php\?spcNow=([a-zA-Z0-9_]+)", html)
    if not dl_match:
        return None  # No SPC available for this set

    result["spc_now"] = dl_match.group(1)

    # Track count and file size
    info_match = re.search(
        r"(\d+)\s+tracks?,\s*(\d+)\s*kb", html, re.IGNORECASE
    )
    if info_match:
        result["tracks"] = int(info_match.group(1))
        result["size_kb"] = int(info_match.group(2))

    # Game title (page title)
    title_match = re.search(r"<title>Game profile:\s*([^<]+)\s*~", html)
    if title_match:
        result["game_title"] = title_match.group(1).strip()

    # Composers
    composers = []
    # Pattern: Composer: <a href='...'>Name</a> or Composers: <a ...>Name</a>, <a ...>Name2</a>
    comp_section = re.search(
        r"Composers?:\s*((?:<a[^>]*>[^<]+</a>[,;& ]*\s*)+)", html, re.IGNORECASE
    )
    if comp_section:
        comp_matches = re.findall(r"<a[^>]*>([^<]+)</a>", comp_section.group(1))
        composers = [c.strip() for c in comp_matches if c.strip()]
    # Fallback: also try plain text after "Composer(s):" if no <a> tags found
    if not composers:
        plain_comp = re.search(
            r"Composers?:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s*[,;/]\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)*)", html
        )
        if plain_comp:
            composers = [c.strip() for c in re.split(r"\s*[,;]/s*", plain_comp.group(1)) if c.strip()]
    result["composers"] = composers

    # Publisher / Developer
    pub_match = re.search(r"Publisher:\s*<a[^>]*>([^<]+)</a>", html)
    if pub_match:
        result["publisher"] = pub_match.group(1).strip()

    # RSN filename (from content-disposition or infer from spcNow)
    result["rsn_url"] = f"{SNES_BASE}download.php?spcNow={result['spc_now']}"

    return result


def paginate_games(char: str) -> list[dict]:
    """Get all games for a given character (letter or 'n1-9') across all pages."""
    all_games = []
    offset = 0
    while True:
        url = f"{SNES_BASE}select.php?view=games&char={char}&limit={offset}"
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  ⚠️  Failed to fetch {url}: {e}")
            break

        games = parse_game_list(html)
        if not games:
            break

        all_games.extend(games)
        print(f"  {char} @ {offset}: +{len(games)} games (total {len(all_games)})", end="\r")

        # Check if there's a next page
        if f"limit={offset + 30}" not in html:
            break
        offset += 30
        time.sleep(REQUEST_DELAY)

    print(f"  {char}: {len(all_games)} games total")
    return all_games


# ── Main ───────────────────────────────────────────────────────────

def main():
    print("🌲 SNESmusic.org Index Builder")
    print("=" * 50)

    # Step 1: Scrape game listings
    print("\n📋 Step 1: Scraping game listings...")
    all_games = []
    chars = ["n1-9"] + [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    for char in chars:
        games = paginate_games(char)
        all_games.extend(games)
        time.sleep(REQUEST_DELAY)

    print(f"\n✅ Total game entries: {len(all_games)}")

    # Step 2: Scrape each set profile for spcNow + metadata
    print("\n📋 Step 2: Scraping set profiles for SPC metadata...")
    sets = {}
    failed = 0
    for i, game in enumerate(all_games):
        sid = game["set_id"]
        if sid in sets:
            # Already scraped this set (same game, different region)
            continue

        url = f"{SNES_BASE}profile.php?profile=set&selected={sid}"
        try:
            html = fetch(url)
            info = parse_profile(html, sid)
            if info:
                sets[sid] = info
                if info.get("tracks"):
                    prog = f"[{i + 1}/{len(all_games)}] {info.get('game_title', '?')[:40]:40s} {info.get('tracks', '?')}t"
                else:
                    prog = f"[{i + 1}/{len(all_games)}] {game['name'][:40]:40s} (no SPC)"
                print(f"  {prog}", end="\r")
            else:
                failed += 1
                prog = f"[{i + 1}/{len(all_games)}] {game['name'][:40]:40s} ❌ no SPC"
                print(f"  {prog}", end="\r")
        except Exception as e:
            failed += 1
            print(f"\n  ⚠️  Failed set_id={sid} ({game['name']}): {e}")

        time.sleep(REQUEST_DELAY)

    print(f"\n✅ Sets with SPC: {len(sets)} / {len(all_games)} unique sets")

    # Step 3: Build track list
    print("\n📋 Step 3: Building track index...")
    track_list = []
    for sid, info in sets.items():
        if not info.get("spc_now"):
            continue
        track_list.append({
            "set_id": sid,
            "spc_now": info["spc_now"],
            "name": info.get("game_title", info.get("name", "Unknown")),
            "composers": info.get("composers", []),
            "publisher": info.get("publisher", ""),
            "tracks": info.get("tracks", 0),
            "size_kb": info.get("size_kb", 0),
            "rsn_url": info["rsn_url"],
        })

    # Sort by name
    track_list.sort(key=lambda t: t["name"].lower())

    # Save to cache
    cache = {
        "version": 1,
        "built": time.time(),
        "total_sets": len(track_list),
        "tracks": track_list,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    total_tracks = sum(t["tracks"] for t in track_list)
    total_size = sum(t["size_kb"] for t in track_list)
    print(f"\n📦 Saved to {CACHE_FILE}")
    print(f"   {len(track_list)} game sets")
    print(f"   ~{total_tracks} individual SPC tracks")
    print(f"   ~{total_size} KB total download size")
    print("\n🌲 Done! 🎵")


if __name__ == "__main__":
    main()
