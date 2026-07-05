# Phase 03 — Sky, Sun, Water World-Anchoring

Read `implementation_plan/README.md` first. Requires phase 02.

**Goal:** The backdrop behaves like a world, not wallpaper: when the camera
turns, the sun, sky gradient, and water move together consistently with the
camera's heading.

## Verified Problems
- The sun disc is blitted at a fixed screen x (a sine of time), ignoring camera
  heading — turn the camera 180° and the sun doesn't move.
- Water is drawn as camera-projected strips but the sun's water reflection is
  blitted at the sun's *screen* position — they disagree after any turn.
- The sky gradient is a static full-screen background with no horizon tied to
  the camera pitch/heading.

## Scope
- Give the sun a **world-space direction** (azimuth from the existing day-cycle
  time). Its screen position each frame comes from projecting that direction
  through the camera (clamped/hidden when behind the camera — phase 02 gives the
  tools). God rays and the water reflection derive from the same world sun.
- Sky: horizon line follows the camera (it already roughly does via tile
  coverage); the gradient band and stars must rotate/shift coherently with yaw —
  at minimum, parallax-shift the star/cloud layers by heading so a 180° turn
  visibly changes the sky.
- Water: keep polygons bounded (phase 02), color follows the sky as today; the
  sun glint sits where the world sun direction says, fading when the sun is
  behind the camera.
- Add a checker assertion: capture two gameplay frames facing opposite
  directions; the sun's detected screen position (brightest sky cluster) must
  differ or be absent in one — proving world anchoring.

## Out of Scope
- Camera motion feel (04). Snake (05–06). New weather/effects.

## Files
`main.py` (sky/sun/water composition), `resources.py`, `config.py`,
`dev/check_frames.py` (the one assertion above)

## Acceptance Criteria
- Turning 180° visibly moves the sun/glint/stars coherently; screenshots facing
  both directions committed under `dev/screenshots/`.
- No wedge regressions: full checker (incl. phase-01/02 checks) passes except
  the pre-existing luma reds owned by phase 07.
- FPS check passes; tests green.
