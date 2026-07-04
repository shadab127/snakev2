# Frame Budget — Phase 02 Baseline

**Target:** 60 FPS → **16.67 ms** total per frame.  
**Measured on:** Reference hardware (integrated GPU, Python 3.x, software rendering path).

## Per-Stage Budget Targets

| Stage | Budget (ms) | % of Frame | Notes |
|---|---|---|---|
| **Sky/Water/Background** | ≤ 0.5 | 3% | Mostly static blits; water ~25 quads |
| **Ground** | ≤ 0.3 | 2% | 225 hex polygons, per-frame projection |
| **Tiles (build + draw)** | ≤ 4.0 | 24% | Pre-computed static data, only projection per frame |
| **Snake** | ≤ 1.0 | 6% | 3–20 segments + head + eye/tongue detail |
| **Apple** | ≤ 0.3 | 2% | Single sprite + glow + leaf |
| **Particles** | ≤ 1.0 | 6% | ≤ 500 particles, glow/spark rendering |
| **Post-processing** | ≤ 2.5 | 15% | Bloom (downscale x2, blur x2, upscale), sun rays, fog |
| **UI / Overlays** | ≤ 0.5 | 3% | Score panel, minimap, pause/game-over overlays |
| **Dirty-rect / Flip** | ≤ 0.5 | 3% | Rect merge + display.update |
| **Simulation** | ≤ 3.0 | 18% | Fixed-timestep accumulator, physics, audio |
| **Headroom** | ≥ 3.0 | 18% | Reserve for Phase 03 (physics) and Phase 04 (graphics) |

## Measured Baseline (Pre-Phase 02)

These are approximate values from the known bottleneck:

| Stage | Measured (ms) | Status |
|---|---|---|
| Tile cache rebuild | ~4.4 | **HOT — optimized in Phase 02** |
| Per-tile noise/color computation | ~2.0 | Eliminated by pre-compute |
| Ground + projection | ~0.4 | Acceptable |
| Snake + head | ~0.5 | Acceptable |
| Particles | ~0.8 | Acceptable |
| Bloom (software) | ~2.0 | Acceptable |
| UI + minimap | ~0.3 | Acceptable |

## Key Optimizations Applied (Phase 02)

1. **Static tile data pre-computed** at startup → world-space corners, base colors, grass blades cached
2. **`all_hexes()` result cached** → avoids generator recreation
3. **Early return in `_build_tile_cache`** → skip rebuild when cache valid
4. **Separated `_build_ground`** → ground rebuilds every frame (camera-dependent), tile cache has own validity
5. **Removed forced full-redraw every 60 frames** → dirty-rect system runs uninterrupted
6. **Pre-computed ground polygon world-space data** → avoid `hex_corners` per tile

## Degradation Budget

Each subsequent phase may consume up to **3 ms** of the current headroom.  
If any phase pushes a stage over its budget, that phase must optimize before merging.
