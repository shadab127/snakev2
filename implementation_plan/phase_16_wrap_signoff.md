# Phase 16 - Full Sign-Off

Requires: Phase 15.

## Goal

Prove that the performance, graphics, and world-flip work hold together in real
gameplay.

## Do

1. Run all unit tests, frame checks, cold/warm cache benchmarks, long-snake
   benchmarks, and transition benchmarks.
2. Test all six directions, all corners, repeated wraps, rapid turns, food,
   pause, death, restart, and maximum speed on a real display.
3. Run software and GL checks where GL is available.
4. Review pre-dive, submerged, mid-flip, emergence, and post-flip captures.
5. Record p50/p95/p99 frame times, backend, quality preset, hardware, and any
   remaining limitations in release notes.

## Files

`dev/check_frames.py`, `tests/`, `CHANGELOG.md`, and release documentation.

## Done When

All automated checks pass, the Phase 01 frame budget holds during the hardest
transition scenario, and a human confirms that wrapping feels smooth, readable,
and fun.

## Do Not

- Do not waive a failed transition test because normal movement looks correct.
- Do not call the effect complete without real-display testing.
