# Integration Test Requirements

## tests/integration/test_real_services.py

This file contains integration tests that require real services:

| Test | Requirement | Environment |
|------|-------------|-------------|
| `test_discord_token_authenticates` | `DISCORD_INTEGRATION_TOKEN` env var | Must be a valid Discord bot token |
| `test_live_audio_services_are_reachable` | `RUN_LIVE_AUDIO_INTEGRATION=1` | Requires running PulseAudio/PipeWire + locally accessible audio sink |
| `test_ffmpeg_generates_and_probes_pcm_audio` | `ffmpeg` on PATH | Runs standalone (no other services) |
| `test_real_discord_sdk_constructs_and_closes_bot` | `DISCORD_INTEGRATION_TOKEN` env var | Runs standalone (no runtime init) |

**Status (2026-06-30):**
- 2 skipped: token not configured, live audio not enabled
- 2 pass: ffmpeg and Discord SDK smoke tests (standalone)

**CI:** The `integration.yml` workflow requires `DISCORD_INTEGRATION_TOKEN` as a GitHub secret and runs `make test-integration`.

**Note:** These tests are excluded from the full offline unit suite. Run separately:
```bash
DISCORD_INTEGRATION_TOKEN=<token> make test-integration
```
