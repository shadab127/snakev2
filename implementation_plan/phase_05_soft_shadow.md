# Phase 05 — Soft Shadow

Read `implementation_plan/README.md` first. Requires phase 04 (shadow follows
the final body shape).

**Problem:** The body shadow is drawn as per-sample dark quads directly on the
scene; where quads overlap the darkness doubles, producing hard-edged dark
patches and a square blotch behind the head — "looks cheap".

## Do
1. Draw all shadow quads onto ONE separate transparent surface at full
   opacity first, then blit that surface once onto the scene at
   `SHADOW_ALPHA`. Overlaps inside the surface can no longer double-darken.
2. Reuse one cached surface (fill with transparent each frame); size it to
   the shadow's screen bounding box, not the whole screen, to keep it cheap.
3. Soften the edge: blit the shadow surface through a small blur — acceptable
   cheap approach: draw the quads at slightly reduced size onto the surface,
   then `pygame.transform.smoothscale` down 2× and back up. Behind a config
   flag `SHADOW_SOFT = True`.
4. Head shadow: same treatment, no special-case square — the head's shadow is
   just the first, slightly wider samples of the strip.
5. Add checker check `shadow_softness`: in a straight-run frame, along a line
   crossing the shadow edge, the luma gradient must be gradual (no single-pixel
   jump > 60 luma) and no shadow pixel may be more than
   `SHADOW_ALPHA + 15` darker than the unshadowed tile beside it. Must FAIL
   before, PASS after.

## Do NOT
- Do not touch body rendering, tiles, water, camera, speed.
- Do not use per-pixel Python loops; surface ops only.

## Files
`main.py` (`_draw_continuous_shadow`), `config.py`, `dev/check_frames.py` (one check)

## Done when
- `shadow_softness` PASSes; checker exit 0 except later-phase checks; tests
  green; FPS check still passes.
- Screenshot saved: one soft, even shadow under the body — no dark patches,
  no square behind the head.
