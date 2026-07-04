# Phase 15 — Packaging & Release

Before starting: read `AGENTS.md` and `implementation_plan/README.md`.

**Goal:** The game installs and launches like a real product, with docs to match.

**Depends on:** Phase 14.

## Scope
- Proper Python packaging (`pyproject.toml`): pinned dependencies, `moderngl` as an
  optional extra, a console entry point (e.g. `snakev2` launches the game), works
  with a plain `pip install`.
- Standalone executable build for macOS (current platform) via PyInstaller or
  equivalent, with a one-command build script; document how the same script would be
  run for Windows/Linux.
- Startup hardening: friendly error dialog/message (not a traceback) for missing
  display, missing dependencies, or GL init failure; `--windowed/--fullscreen`,
  `--no-gl`, and `--version` flags.
- App identity: window icon (generated in code), proper window title, version number
  sourced from one place.
- Rewrite `README` for players (screenshots section, controls, install, build) and
  update `AGENTS.md` for the final architecture; final `CHANGELOG.md` release entry.

## Out of Scope
- Code signing, notarization, app-store distribution, auto-updates.

## Likely Files
New `pyproject.toml` + build script, `main.py`, `README.md`, `AGENTS.md`, `CHANGELOG.md`

## Acceptance Criteria
- Fresh virtualenv: `pip install .` then the console command launches the game.
- Built standalone app launches on a machine (or account) without Python dev tools.
- Each hardening flag works; forced GL failure shows the friendly path, not a crash.
- README accurately reflects the shipped game.
