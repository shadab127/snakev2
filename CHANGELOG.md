# Changelog

## v6 — Fix Plan v6

### Phase 01 — Restore Guardrails
- Restored `tests/`, `dev/check_frames.py`, `AGENTS.md` from commit `62a4805`
- Updated tests: `compute_lighting` removed from utils (2 skipped), `Camera.shake` removed (3 skipped), `PersistenceManager.set_high_score` → `add_score`
- Appended guardrail rule 1 to AGENTS.md
- Checker: ALL PASS

### Phase 02 — Body Snap Fix
- Replaced independent high-res spline computation with subsampling of the low-res spline positions (`_subsample_spline_positions`) — eliminates the 52px body snap caused by divergent spline calculations at move-step boundaries
- Updated `motion_continuity` checker to measure mid-body high-res sample instead of head, with 50-frame window to capture move steps
- Checker: ALL PASS, Tests: 124 passed
