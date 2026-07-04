# Phase 09 — Post-Processing Stack

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** A cinematic final image: controlled bloom, tone mapping, and tasteful
screen effects — with an honest software fallback.

**Depends on:** Phase 07.

## Scope
- Restructure the GL post chain into an ordered, individually-toggleable stack
  (each stage on/off via `config.py`):
  1. Bloom — threshold-based so only emissives and highlights bloom (currently it
     brightens everything).
  2. Tone mapping + slight color grade for a filmic look.
  3. God rays — keep, but tie the source position to the actual sun.
  4. Vignette + very subtle film grain.
- Event-driven grading: brief warm flash on eating, desaturate-and-darken on death,
  slight cool shift on pause. Smoothly blended, never abrupt.
- Software fallback: implement cheap equivalents where feasible (vignette, flashes,
  simple glow) and cleanly skip the rest — no crashes, no half-drawn effects.
- Screenshot key that saves the final composited frame to disk.

## Out of Scope
- New scene content (sky, weather — phase 10).
- Performance work beyond keeping the budget.

## Likely Files
`shaders.py`, `gl_renderer.py`, `main.py`, `config.py`

## Acceptance Criteria
- Bloom halos appear on bright emissives only; mid-tone tiles do not glow.
- Eating/death/pause each show their grade change, smoothly in and out.
- Game looks correct and runs with ModernGL uninstalled.
- Each stage can be disabled independently via config; frame budget holds with all on.
