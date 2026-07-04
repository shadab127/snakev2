# Phase 11 — Audio System

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** Full game audio — music, effects, and ambience — generated procedurally at
startup so the repo ships no binary assets.

**Depends on:** Phase 01. Independent of graphics/physics tracks.

## Scope
- Small audio manager module: channels for music / SFX / ambience, master + per-bus
  volume, safe no-op if the audio device fails to initialize.
- All sounds synthesized in code at startup (pygame + math is enough): eat pop,
  movement slither (soft, rate-linked to snake speed), death sting, UI click, score
  milestone chime.
- Ambient loop: gentle wind/water bed appropriate to the floating-island scene.
- Music: a simple generative ambient loop (layered tones/arpeggio) that shifts mood
  with the day cycle and intensifies slightly as the snake speeds up.
- Everything ducked appropriately: music dips briefly on death; pause mutes SFX but
  keeps quiet music.
- Volumes in `config.py`; a mute toggle key.

## Out of Scope
- Settings UI for audio (phase 12 wires it up).
- Shipping audio files.

## Likely Files
New `audio.py`, `main.py`, `config.py`

## Acceptance Criteria
- Every event listed above has a distinct, non-grating sound.
- Game runs silently but perfectly on a machine with no audio device.
- Music mood audibly changes across the day cycle and with snake speed.
- No audible clicks/pops at loop boundaries or sound starts.
