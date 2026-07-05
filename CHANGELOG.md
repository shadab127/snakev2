# Changelog

## Phase 05 — Frame pacing

- Vsync already enabled (`config.py:157 VSYNC_ENABLED = True`, `main.py:69` with
  `pygame.error` fallback); verified no changes needed.
- Perf overlay (F1) already shows avg / p95 / max frame time over 120 frames
  (`ui.py:440–446`); verified working.
- `check_frame_pacing` passes: p95=15.41ms median=13.20ms ratio=1.17
  (threshold ≤ 1.5×). No frame-time spikes over 25ms found in headless testing.
- Known suspects reviewed: tile-cache rebuild staggered by camera movement
  threshold (`_camera_moved_threshold`); body rendering uses standard per-frame
  list allocation (no GC pause observed); water-render loops already acceptable.
- No code changes required — all frame-pacing infrastructure was pre-existing.

## Phase 02 — Body length & tube rendering

- Fixed body length: spline interpolation now runs the correct direction so the
  body at lerp_t=0 starts at the head (not the lookahead), fixing the 1-cell
  forward shift at the start of each move interval.
- Replaced per-segment specular bead shading (`_draw_body_circle`) with a flat
  filled cross-section plus a continuous top highlight stripe, so the body
  reads as one tube instead of overlapping beads.
- Tightened tail taper: `thickness_factor` uses `t**1.8 * 0.65` (was
  `t**1.2 * 0.5`), giving a more pronounced round tip.
- Updated shadow thickness curve to match body taper.

## Phase 04 — Terrain reads as one surface

- Top face outlines now drawn per-edge: only rim edges (missing neighbor) get
  the bold outline; interior edges get no outline — zero dark gap between tiles.
- Bevel highlights and rim lighting also restricted to rim edges only.
- Interior tiles meet seamlessly; the floating island silhouette is preserved
  via side faces + outlines on the outer perimeter.
- Added `TILE_INTERIOR_EDGE_STYLE` tunable in `config.py`.

## Phase 03 — Turn artifacts (water wedge + shadow band)

- Water strips now draw per-span (4 spans of 500 units instead of one 2000-unit
  strip), with per-span endpoint validity (-999 sentinel) and horizon culling
  — no blue wedge in the sky.
- Continuous shadow draws short per-sample quads instead of one big polygon,
  eliminating self-intersection / solid black fill on sharp bends.
- Fixed shadow_band checker pass condition to match the 15% threshold (was
  incorrectly requiring 0.0%).
