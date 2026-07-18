# Phase 06 - Renderer and Quality Selection

Requires: Phase 05.

## Goal

Make backend choice predictable and give slow machines measured quality options.

## Do

1. Make `--no-gl` skip GL context creation entirely.
2. Keep the current CPU/GPU readback renderer out of the default performance
   path until it can present directly without full-frame transfers.
3. Permanently fall back to software after a GL render failure and report one
   concise diagnostic.
4. Add named quality presets for water, post-processing, grass, shadow, minimap,
   and particles.
5. Keep gameplay, collision, and wrap physics identical across all presets.

## Files

`main.py`, `gl_renderer.py`, `config.py`, `persistence.py`, `ui.py`, and tests.

## Done When

Renderer startup/fallback behavior is tested, default quality meets the Phase
01 target on the reference machine, and quality changes affect only visuals.

## Do Not

- Do not silently disable effects without exposing the chosen preset.
- Do not change the simulation rate for a low-quality preset.
