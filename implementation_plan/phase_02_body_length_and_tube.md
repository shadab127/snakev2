# Phase 02 — Correct Body Length, One Tube Instead of Beads

Read `implementation_plan/README.md` first. Requires phase 01.

**Problem:** Two bugs make the body wrong (see `symptom_long_turn.png`):
- **Length bug:** spline samples are spread over the entire `path_history`
  (up to `MAX_PATH_LENGTH` cells) instead of exactly the snake's length. A
  13-segment snake draws as ~25 beads stretched across the map, and the tail
  visually lags cells behind where it logically is.
- **Bead look:** the body is drawn as a row of scaled sphere sprites; each
  sphere's shading makes every sample read as a separate ball.

## Scope
1. Length: the drawn body must cover exactly the snake's logical length —
   trim/parameterize the spline so its arc length equals
   (number of segments) × (one cell spacing), starting at the interpolated
   head from phase 01. The drawn tail ends where the logical tail is;
   `path_history` may keep extra points internally but they must not be drawn.
2. Tube look: keep sampling dense, but shade the body as one form:
   flat-ish filled cross-sections (or strip quads) using the head→tail
   `SNAKE_COLORS` gradient with the existing sun-diffuse factor, plus a single
   lighter top-highlight stripe running along the body. No per-sample specular
   ball highlight — that is what creates beads.
3. The tail tapers to a rounded tip; the neck meets the head sprite with no
   visible seam or size jump.
4. Add checker check `body_length`: with a known snake length, project the
   drawn head and drawn tail-tip world positions; their world distance must be
   within ±20% of (segments × cell spacing). Must FAIL before (measured today:
   ~2× too long), PASS after.

## Do NOT
- Do not touch the head sprite, apple, tiles, water, sky, shadow.
- Do not change `path_history` maintenance in game logic (wrap rebuild etc.).

## Files
`main.py`, `utils.py` (spline sampling), `resources.py` (only if removing the
per-sample sphere sprite path), `config.py`, `dev/check_frames.py` (one check).

## Done when
- `body_length` PASSes; full checker exits 0; tests green.
- Screenshots (straight + mid-turn) saved: one smooth tapered tube of the
  correct length, no beads, no seam at the neck. Compare against
  `symptom_long_turn.png` — the improvement must be obvious.
