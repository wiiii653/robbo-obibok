# Tracker Module Volume Analysis

## Problem

XM/IT/S3M/MOD files have no standard master volume — each composer mixed
differently. The range in Tiny Music spans **22 dB RMS** (from digital clipping
at 0.0 dBFS to barely audible at -21.2 dBFS peak).

## Measurement Technique

```bash
# Decode first 30s to raw PCM, measure peak/RMS
ffmpeg -y -i "$track" -t 30 -f s16le -ac 1 -ar 44100 /tmp/raw.raw

python3 -c "
import struct, math
with open('/tmp/raw.raw','rb') as f: d=f.read()
s=struct.unpack('<' + 'h'*(len(d)//2), d)
peak = max(abs(x) for x in s)/32768.0
rms = math.sqrt(sum(x*x for x in s)/len(s))/32768.0
print(f'peak={20*math.log10(peak):.1f} dBFS  rms={20*math.log10(rms):.1f} dBFS')
"
```

For real-time playback measurement (with Audacious compressor), capture from
PulseAudio monitor:

```bash
ffmpeg -y -t 8 -f pulse -i asma_bot.monitor -f s16le -ac 1 -ar 44100 /tmp/cap.raw
```

## Before Compressor (no Audacious effect plugins)

| Track | Format | Peak (dBFS) | RMS (dBFS) | Notes |
|---|---|---|---|---|
| Gazman — King Of Style | XM | **0.0** | -11.4 | 🔴 digital clipping |
| DJ Kambota — Show Me The Way | XM | -1.4 | -16.7 | extremely loud |
| Ida — Keuteutoe... | MOD | -2.9 | -15.6 | loud |
| Dune — The Day Earth Was Born | XM | -3.9 | -19.7 | medium |
| DJ Stax — Calvin Harris Summer | XM | -5.7 | -17.8 | medium |
| U4ia — Oasis Wonderwall | XM | -6.3 | -23.1 | medium |
| FTC — News At Ten | XM | -6.7 | -17.1 | medium |
| Dubmood — 4everblue morninsky | XM | -7.9 | -24.1 | medium |
| Necros — distant lullaby | XM | -7.8 | -22.6 | medium |
| Orlingo — I Originate | XM | -10.9 | -28.4 | quiet |
| Body — Loop 01 | XM | -11.5 | -25.1 | quiet |
| Dune — Blak Scpek | S3M | -14.2 | -30.0 | very quiet |
| **Fusion Faktor — Flashlight** | **IT** | **-21.2** | **-33.9** | 🥶 barely audible |

**Range: 21.2 dB peak, 22.5 dB RMS.**

## After Compressor (center=0.4, range=0.35)

| Track | Peak (dBFS) | RMS (dBFS) | Change |
|---|---|---|---|
| Gazman — King Of Style | -5.7 | -21.0 | -5.7 dB ✅ no more clip |
| Orlingo — I Originate | -9.6 | -28.0 | +1.3 dB |
| Fusion Faktor — Flashlight | -15.7 | -26.9 | **+5.5 dB** ✅ |
| Dune — The Day Earth Was Born | -14.3 | -28.7 | -10.4 dB (quiet passage) |
| Body — Loop 01 | -15.2 | -25.0 | -3.7 dB |
| MOD (Ida) | -8.7 | -21.9 | -5.8 dB |

**Range after compressor: ~10 dB peak** (was 21 dB).

## Compressor Config

Location: `~/.config/audacious/config`

```ini
[compressor]
center=0.4
range=0.35
```

### Parameters

- `center` (0.1–1.0, default 0.5): Reference level. Signals with RMS/peak
  above `center` are attenuated; signals below are boosted.
- `range` (0.0–3.0, default 0.5):
  - **< 1**: compression (louder parts → quieter, quieter → louder)
  - **= 1**: passthrough (no effect)
  - **> 1**: expansion (louder → louder, quieter → quieter)

### How the algorithm works

(From Audacious `compressor.cc` source)

```c
static void do_ramp (float * data, int length, float peak_a, float peak_b)
{
    float center = aud_get_double ("compressor", "center");
    float range = aud_get_double ("compressor", "range");
    float a = powf (peak_a / center, range - 1);
    float b = powf (peak_b / center, range - 1);
    // linear interpolation between a and b over the chunk
}
```

The compressor measures `current_peak` over ~200ms chunks with 0.3 decay
smoothing. It applies a gain factor smoothly ramped between chunk boundaries.

### Tuning Notes

- Lower `center` → more attenuation of loud tracks, less boost of quiet ones
- Lower `range` → stronger effect (more leveling, less dynamic range preserved)
- With `center=0.4, range=0.35`: Gazman (previously 0.0 dBFS) peaks at -5.7 dBFS
- The choice between 0.4/0.35 and more aggressive 0.35/0.3 depends on taste:
  0.35/0.3 gave Gazman at -8.4 dBFS and Fusion Faktor at -16.5 dBFS — even
  tighter range but tracks sound quieter overall.

## Alternatives Considered

1. **Pre-scan + ffmpeg `volume=` filter** — deterministic per-track gain using
   EBU R128 (LUFS). Requires indexing the entire collection once. Cleaner than
   a compressor because it doesn't affect dynamics.
2. **ReplayGain in Audacious** — not available as a plugin. Would need external
   tool like `loudgain` to write tags.
3. **Lazy learning** — store per-track gain in a DB on first play. First play
   always has wrong volume.
4. **pactl set-sink-input-volume** — adjust PulseAudio stream volume per track.
   Doesn't require modifying the audio pipeline.
