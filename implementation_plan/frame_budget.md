# Frame Budget — Phase 19 Recovery

**Target:** 60 FPS → **16.67 ms** total per frame.  
**Measured on:** Reference hardware (integrated GPU, Python 3.x, software rendering path, 1280×800).

## Measured Post-Recovery (Phase 19)

### Default settings (all effects ON)
| Metric | Value |
|---|---|
| Overall FPS | **37 FPS** (27.0 ms/frame) |
| Tiles | 0.53 ms (2%) |
| Snake | 0.77 ms (3%) |
| Particles | 0.06 ms (<1%) |
| Post-processing | 4.02 ms (15%) |
| UI | 2.09 ms (8%) |

### Post-processing OFF (bloom, tone map, god rays, film grain, vignette disabled)
| Metric | Value |
|---|---|
| Overall FPS | **77 FPS** (13.0 ms/frame) |
| Tiles | 0.50 ms (4%) |
| Snake | 0.75 ms (6%) |
| Particles | 0.05 ms (<1%) |
| Post-processing | 0.10 ms (<1%) |
| UI | 2.00 ms (15%) |

## Per-Stage Budget Targets (Post-Recovery)

| Stage | Budget (ms) | % of Frame | Actual (post-on) | Notes |
|---|---|---|---|---|
| **Sky/Water/Background** | ≤ 0.5 | 3% | ~0.3 | Pre-computed, cached |
| **Ground** | ≤ 0.3 | 2% | ~0.2 | Gated by camera movement threshold (3.5u) |
| **Tiles (build + draw)** | ≤ 2.0 | 12% | ~0.5 | Static data pre-computed, cached until camera moves |
| **Snake** | ≤ 1.0 | 6% | ~0.8 | 3–20 segments + spline interpolation |
| **Apple** | ≤ 0.3 | 2% | ~0.1 | Glow sprite cached |
| **Particles** | ≤ 1.0 | 6% | ~0.06 | ≤ 500 particles |
| **Post-processing** | ≤ 5.0 | 30% | ~4.0 | Numpy-based bloom+tone (no per-pixel loops) |
| **UI / Overlays** | ≤ 2.5 | 15% | ~2.1 | Score, minimap, pause/game-over |
| **Simulation** | ≤ 3.0 | 18% | ~1.5 | Fixed-timestep at 180 Hz |
| **Headroom** | ≥ 1.0 | 6% | — | Tight; post-on still 10ms over 60 FPS target |

## Key Optimizations Applied

1. **Numpy-based bloom + tone map** — single pass using `surfarray.pixels3d()` eliminates per-pixel `get_at`/`set_at` loops (71× speedup, 349ms → 4.9ms)
2. **Tile cache gated** — rebuild skipped when camera moves < 3.5 units (tiles from ~17ms → ~0.5ms)
3. **Ground cache gated** — same 3.5-unit threshold for ground polygons
4. **Film grain precomputed** — single noise surface scrolled 3px/frame, no per-frame allocation
5. **Water reduced** — 24 rows (was 50), no third wave harmonic
6. **Sky uses fill(rect)** — instead of draw.line() per row (5× faster)
7. **Non-numpy fallback removed** — per-pixel Python loops eliminated; effects skipped if numpy unavailable

## Target

60 FPS (16.67 ms) with post-processing ON. Currently 37 FPS (27 ms) — post-processing (~4ms) and UI (~2ms) are the main remaining bottlenecks. Achieving 60 FPS with all effects on requires reducing total frame time by ~10 ms.
