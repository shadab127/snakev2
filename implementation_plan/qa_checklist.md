# QA Checklist — SnakeV2

> Run through each item manually. Check off when verified on reference hardware (1280×800, software rendering path).

---

## 1. Gameplay

- [ ] **Start screen**: Title, menu items (Play, Settings, Quit) visible. Arrow keys / mouse navigate. Enter / click activates.
- [ ] **Play start**: Pressing Play transitions (fade to black → fade in). Game state shows PLAYING.
- [ ] **Snake movement**: Snake moves continuously on hex grid. Turning is responsive (LEFT / RIGHT or A / D).
- [ ] **Apple eating**: Moving the head onto the apple increments score by 10. Apple respawns on a random empty hex.
- [ ] **Speed ramp**: Score increases cause snake to move faster. Speed indicator dots in HUD fill up.
- [ ] **Self-collision**: Touching own body triggers death animation (snake collapses, screen shakes, particles burst).
- [ ] **Wrap-around**: Snake wraps at grid edges. Path and camera snap cleanly.
- [ ] **Pause**: SPACE pauses. Pause menu shows Resume / Settings / Restart / Quit.
- [ ] **Game Over**: Death animation plays. Score counts up with "NEW RECORD" bounce. Restart / Title Screen available.
- [ ] **High score tracking**: High score displays on UI and Game Over screen. Persists across sessions (check by restarting game).
- [ ] **Score pop**: Score panel shows pop animation when scoring.

## 2. Physics / Particles

- [ ] **Particle gravity**: Particles fall with gravity, bounce on ground, fade out.
- [ ] **Apple burst**: Eating apple spawns ~30 colored glow + spark particles.
- [ ] **Death burst**: Snake death spawns ~40 red/orange/green particles.
- [ ] **Movement dust**: Direction changes spawn 3 small dust puffs.
- [ ] **Ambient motes**: Fireflies / floating motes drift around the scene.
- [ ] **Particle overflow**: Spamming many particles does not crash (pool recycles).

## 3. Graphics

- [ ] **Hex grid**: 225 tiles rendered with correct hexagonal axial layout. Tiles have 3D extrusion (sides visible).
- [ ] **Tile variation**: Color variation, cracks, moss, grass blades, flowers, rocks per tile.
- [ ] **Lighting**: Sunlight direction rotates over time. Tiles are lit with ambient + diffuse. Day/night cycle visible.
- [ ] **Shadows**: Snake and apple cast soft drop shadows on tiles.
- [ ] **Ambient occlusion**: Tiles near snake or edges have darker corners.
- [ ] **Snake body**: Smooth, spherical segments with color gradient from head to tail. Spline-smoothed body.
- [ ] **Snake head**: Larger, with eyes (white + iris + pupil + reflection), blinking, tongue (flickering).
- [ ] **Eat bulge**: Bulge travels down the snake body after eating.
- [ ] **Apple**: 3D apple sprite with stem, leaf (animated), glow, bobbing motion.
- [ ] **Apple glow**: Pulsing emissive glow around apple.
- [ ] **Post-processing**: Bloom, tone mapping, god rays, vignette, film grain toggle in settings.
- [ ] **Sky**: Gradient sky with stars, sun disc, clouds, birds.
- [ ] **Water**: Animated reflective water below the grid with wave distortion.
- [ ] **Camera**: Isometric camera follows snake smoothly with spring physics. Banks on turns, punches on eat, pulls out on death.
- [ ] **Fog**: Distance fog blends tiles into the horizon.
- [ ] **Minimap**: Bottom-right minimap shows hex grid, snake path, apple position.

## 4. Audio

- [ ] **Music**: Ambient day/night music crossfades based on time of day.
- [ ] **Eat SFX**: High-pitched chime when eating apple.
- [ ] **Score chime**: Arpeggio every 50 points.
- [ ] **Slither**: Subtle sound on each direction change (cooldown-sensitive).
- [ ] **Death SFX**: Descending tone + noise burst on death.
- [ ] **UI click**: Click sound on menu navigation (Enter / click).
- [ ] **Mute**: M key toggles mute. Audio state persists visually.
- [ ] **Volume settings**: Music, SFX, Ambience volumes adjustable in Settings and persist.

## 5. UI / Menus

- [ ] **Score panel**: Top-left shows animated score + speed dots + high score.
- [ ] **Pause overlay**: Semi-transparent dark overlay with menu.
- [ ] **Game Over overlay**: Dark overlay with score count-up, new record bounce, menu.
- [ ] **Settings screen**: Music, SFX, Ambience sliders (LEFT/RIGHT adjust). Toggle: Bloom, Tone Map, God Rays, Vignette, Film Grain, Show FPS.
- [ ] **Fade transitions**: All state changes use smooth fade-to-black → fade-in.
- [ ] **Mouse support**: All menus navigable by mouse (hover highlights, click activates).
- [ ] **Keyboard support**: Arrow / WASD navigation, Enter / Space activate, Escape goes back.
- [ ] **FPS counter**: F1 toggles debug overlay showing FPS and stage timings.
- [ ] **Screenshot**: F12 saves screenshot to PNG.

## 6. Settings Persistence

- [ ] **Save on change**: Adjusting settings updates the saved file.
- [ ] **Load on start**: Settings and high score are restored from save file.
- [ ] **Corruption safety**: If save file is corrupt/missing, defaults are used (no crash).

## 7. Performance

- [ ] **60 FPS target**: Maintains ~60 FPS on reference hardware in software mode.
- [ ] **Tile cache**: Tile cache rebuilds only when needed (camera moves, game state changes).
- [ ] **Dirty rects**: Only changed regions are updated; no full-screen redraw every frame.
- [ ] **Particle limit**: Particle pool capped at MAX_PARTICLES (500); no memory leak.
- [ ] **No lag spikes**: Start, pause, death, settings transitions are smooth.

## 8. Edge Cases

- [ ] **Rapid input**: Spamming direction keys does not cause double-move or self-collision.
- [ ] **Window resize**: Window can be resized (SCALED flag). Game adapts.
- [ ] **Alt+Tab / focus loss**: Game pauses or continues gracefully.
- [ ] **Long play sessions**: Running for 10+ minutes: no crash, no memory growth.
- [ ] **Score overflow**: Very high scores (999+) display correctly.
- [ ] **Empty grid**: Spawning apple when only 1 hex remains (if ever possible) — no crash.

---

**Tester:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_  **Date:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

**Notes / Bugs Found:**

1.
2.
3.
