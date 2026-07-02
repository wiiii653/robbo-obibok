# Changelog

## [0.1.0] — 2026-07-02

### Added
- KGen (Keygen Music) collection — 4843 demoscene keygen modules
- !kgen / !keygen / !k commands with lazy-loaded collection
- Auto-reconnect to voice on restart if humans present
- Universal subsong playback for Tiny Music modules
- Local archive support for ASMA and HVSC
- Blacklist system — !blk, !blks, !blkrm
- !favsave / !favload — persistent playlist storage
- PlaybackLease — single-guild playback enforcement
- TaskManager — centralized asyncio task lifecycle
- Audacious Compressor auto-enable at startup

### Changed
- Rebrand: Robbo Obibot → Robbo Obibok
- Refactor: monolithic bot → layered hexagonal architecture
- Refactor: 8-phase structural cleanup (entrypoint, state, launcher)
- Rebaked: !help compact format with aliases
- Collapsed: 50+ source files → 62 organized modules
- Moved: logs to var/, cache configurable, paths documented

### Fixed
- classify_track_route: check current_mode == "kgen" before extension routing
- Stale pre_downloaded race condition (!favplay played wrong track)
- audacious_play retry up to 3x on failure
- Race condition in _after_stream_end — source_id prevents stale callbacks
- Race condition in active_streams cleanup (KeyError on first flip)
- Per-track timeout from GME/OpenMPT reported length
- SID auto-advance, ModArchive search, !next AlreadyPlayingAudio
- root_dir resolution when module is in src/<package>/
- Collection counts: AY 43k→4.5k, YM 23k→7.2k, SNES ~60k→2.6k game sets

### Removed
- AGENTS.md from public repo (internal Hermes reference only)
- mypy dependency (not used in project)
- run_bot_logged.py (bot runs via systemd)
- Duplicate archiwum entry in .gitignore
- playlists/48.json from tracking

## [0.0.9] — 2026-06-20

### Added
- Atari ST YM collection (7,266 tracks)
- Tiny Music — curated demoscene module archive (418→548 tracks)
- SNES SPC collection via snesmusic.org
- !playlists command with author, date, track count

### Fixed
- Hardware: per-track timeout from actual length
- SID playback: uniform 300s → dynamic per Songlengths.md5

## [0.0.8] — 2026-06-15

### Added
- Local AY archive support + !ay command
- Audacious for AY playback (GME)
- Compressor auto-enable at startup

### Fixed
- AY track skipping — use is_playing_mode() for detection
- Kill old monitor_task before new collection switch
- Lower HVSC volume from 150% → 120%

## [0.0.7] — 2026-06-10

### Added
- !volume, !queue/!q, !sleep commands
- !loop/!repeat, !history, !jump, !clear commands
- !favplay/!fp — play favorites
- Normalization of volume per-collection
- PID lock against duplicate bot instances

### Fixed
- 9 bugs in collection switching — full state machine rewrite
- !next — AlreadyPlayingAudio error
- Graceful shutdown with systemd

## [0.0.6] — 2026-06-05

### Added
- ModArchive full collection (Amiga tracker modules)
- C64 SID support via GStreamer (HVSC collection)
- Reaction-based favorites playlist
- !flip to toggle between collections

### Fixed
- Kill both players before switching collections
- Cleanup orphan GStreamer/Audacious on start
- ModArchive search functionality

## [0.0.5] — 2026-06-01

### Added
- ASMA Radio mode: full playlist shuffle, loop, skip, crawl + cache
- Multi-guild support with async embeds
- Auto-play after collection switch
- Config-driven bot with config.yaml
- Systemd service

### Fixed
- Infinite crawl loop via Parent Directory link
- FFmpeg restart loop with MonitorAudioSource
- 3-second grace period against premature track skip
- Stereo PCM for Discord compatibility

## [0.0.1] — 2026-05-25

### Added
- Initial release: basic ASMA SAP playback
- Discord bot skeleton with command prefix
