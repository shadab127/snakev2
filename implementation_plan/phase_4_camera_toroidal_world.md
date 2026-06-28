# Phase 4 — Camera System + Toroidal World

## Overall Status

| Sub-phase | Status |
|---|---|
| **4a — Toroidal World** | ⚠️ BUGGY — `wrap_coords()` exists but produces invalid hex coordinates after wrapping |
| **4b — 3D Follow Camera** | ❌ NOT IMPLEMENTED — `Camera` class exists but uses old isometric math |

---

## 4a — Toroidal World

### Objective
Snake wraps around grid edges instead of dying when it reaches the boundary.

### Current Implementation Status

`wrap_coords()` exists at `utils.py:99-108` and is called in `move_snake()` at `main.py:325`:

```python
# main.py:325
new_head = wrap_coords(*self.next_head_pos())
```

**Bug:** The function checks `if in_bounds(q, r): return q, r` first, and only wraps out-of-bounds coordinates. But after the modulo wrap, the result may still violate `in_bounds()` due to the hexagonal vs rectangular grid mismatch:

```
Hexagonal valid region:  max(|q|,|r|,|q+r|) <= 7  (169 cells)
Parallelogram grid:      GRID_COLS × GRID_ROWS = 15×15  (225 cells)
→ ~56 cells in the corners of the parallelogram are NOT valid hex cells
```

### Root Cause Diagram

```
   Hexagon (169 cells)       Parallelogram (225 cells)
      █████████                ░░░░░░░░░░░░░░░
    █████████████            ░░░░█████████████░░░░
  █████████████████        ░░░░█████████████████░░░░
█████████████████████    ░░░░█████████████████████░░░░
  █████████████████        ░░░░█████████████████░░░░
    █████████████            ░░░░█████████████░░░░
      █████████                ░░░░░░░░░░░░░░░

Modulo wraps within the parallelogram, but corner areas
(dots) are outside the valid hexagon.
```

### Fix — Rectangular Grid (Option 1 from original plan)

Expand the playable grid to the full 15×15 parallelogram. The visual difference is minimal since the hexagonal corners were already sparse.

#### File: `utils.py`

**1a. Rewrite `all_hexes()` (line 111-121)**

Remove the `seen` dedup set and `in_bounds` filter — just yield all cells in the parallelogram:

```python
def all_hexes():
    cols = GRID_RADIUS * 2 + 1  # 15
    rows = GRID_RADIUS * 2 + 1  # 15
    for row in range(rows):
        for col in range(cols):
            q = col - (row + (row & 1)) // 2 - GRID_RADIUS
            r = row - GRID_RADIUS
            yield (q, r)
```

**1b. Simplify `wrap_coords()` (line 99-108)**

Remove the early `in_bounds()` guard — always perform the wrap (modulo of an in-range value is identity, so in-bounds coordinates are unaffected):

```python
def wrap_coords(q, r):
    col = q + (r + (r & 1)) // 2
    row = r
    col %= GRID_COLS
    row %= GRID_ROWS
    wq = col - (row + (row & 1)) // 2 - GRID_RADIUS
    wr = row - GRID_RADIUS
    return wq, wr
```

#### File: `main.py`

**1c. Remove `in_bounds()` check from `update_ambient_particles()` (line 804)**

```python
# Before:
if in_bounds(q, r):
    cx, cy = hex_to_pixel(q, r)
    ...

# After — always valid since all hexes in parallelogram are valid tiles:
cx, cy = hex_to_pixel(q, r)
...
```

**1d. Remove `in_bounds` from the import statement (line 9-13)**

```python
from utils import (perlin_noise, catmull_rom, hex_side_normal, hex_to_pixel,
                   hex_corners, all_hexes, project, lerp_color,
                   mul_color, add_color, screen_shake_offset, compute_tile_ao,
                   dot3, lerp3, tile_noise, generate_soft_shadow, _perlin_cache,
                   wrap_coords)
# Remove: in_bounds
```

**⚠️ Check:** `compute_tile_ao()` in `utils.py:156-166` also uses `in_bounds()` — but that's for AO computation, not for grid validity. Keep it there. The function checks neighbors for AO purposes, which is fine.

#### File: `ui.py`

**1e. Remove unused import `in_bounds` (line 5)**

```python
# Before:
from utils import hex_to_pixel, all_hexes, in_bounds
# After:
from utils import hex_to_pixel, all_hexes
```

### Verification (4a)

| Test | Procedure | Expected |
|---|---|---|
| Wrap right | Move snake right past x edge | Head appears on left side |
| Wrap left | Move snake left past x edge | Head appears on right side |
| Wrap top | Move snake up past y edge | Head appears on bottom |
| Wrap bottom | Move snake down past y edge | Head appears on top |
| Wrap diagonal | Move in direction 1 (0,1) past edge | Head wraps correctly |
| No crash on corner | Wrap at extreme corners | Game continues, no KeyError |
| Apple spawning | Eat apple, new apple spawns | Apple always on a valid tile |

---

## 4b — 3D Follow Camera

### Objective
Replace the fixed isometric `project()` with a full 3D view/projection pipeline that follows the snake head. The world should stay upright, and the camera should track the snake smoothly from behind and above.

### Current Implementation Status

`Camera` class exists at `camera.py:5-26` with `follow_snake()` and `project()`. The projection math is **identical** to the old isometric `utils.project()` except for offset subtraction:

```python
# camera.py:10-19 (CURRENT — isometric, NOT true 3D)
def project(self, x, y, z=0):
    wx = x - self.offset_x
    wy = y - self.offset_y
    y_rot = wy * math.cos(TILT) - z * math.sin(TILT)
    depth = -wy * math.sin(TILT) - z * math.cos(TILT)
    z_cam = depth + CAM_DIST
    factor = FOV / z_cam if z_cam > 0 else 999
    sx = wx * factor + WIDTH / 2
    sy = y_rot * factor + Y_OFFSET
    return sx, sy, z_cam
```

**Missing:**
- No 4×4 matrix pipeline (MVP: Model-View-Projection)
- No `lookAt()` / `perspective()` matrix construction
- No frustum culling (all 169+ tiles rendered every frame)
- `utils.project()` (line 124-131) still exists as dead code
- Camera follow is 2D offset-based, not 3D position-based

### Implementation — Step B: 3D Perspective Pipeline

#### B0. Prerequisites

- Phase 4a must be complete (toroidal grid fix)
- Read the existing `camera.py`, `utils.py`, `main.py` call sites, and `gl_renderer.py` tile rendering
- Have `DEBUG_USE_OLD_CAMERA` toggle ready for A/B comparison

#### B1. Add 3D camera constants to `config.py` (after line 13)

Introduce new constants alongside (don't remove old ones yet):

```python
# === 3D Follow Camera ===
CAM_3D_DIST = 280           # Distance behind snake head (world units)
CAM_3D_HEIGHT = 130         # Height above snake head
CAM_3D_LOOKAHEAD = 40       # How far ahead of head to look
CAM_3D_FOV = 45             # Vertical field of view (degrees)
CAM_3D_FOV_RAD = math.radians(CAM_3D_FOV)
CAM_3D_NEAR = 10            # Near clip plane
CAM_3D_FAR = 2000           # Far clip plane
CAM_3D_LERP = 0.08          # Camera smooth-follow speed

# Camera clipping for frustum
TILE_CLIP_MARGIN = 100      # Pixels beyond screen edges to still render

# Debug
DEBUG_OLD_CAMERA = False    # Set True to use old isometric math for comparison
```

#### B2. Implement `Matrix4` class in `camera.py`

Add a self-contained 4×4 matrix utility. Column-major storage (OpenGL convention):

```python
class Matrix4:
    """4×4 column-major matrix utilities for the MVP pipeline."""

    @staticmethod
    def identity():
        """Return identity matrix as list of 16 floats."""
        return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]

    @staticmethod
    def multiply(a, b):
        """Return a * b (matrix multiply, both 16-element lists)."""
        res = [0]*16
        for i in range(4):
            for j in range(4):
                res[j*4+i] = sum(a[k*4+i] * b[j*4+k] for k in range(4))
        return res

    @staticmethod
    def perspective(fov_y, aspect, near, far):
        """Perspective projection matrix (fov_y in radians)."""
        f = 1.0 / math.tan(fov_y / 2)
        d = near - far
        return [
            f/aspect, 0, 0, 0,
            0, f, 0, 0,
            0, 0, (far+near)/d, -1,
            0, 0, 2*far*near/d, 0
        ]

    @staticmethod
    def look_at(eye, target, up):
        """View matrix from eye→target with up vector.
        All args are (x, y, z) tuples.
        """
        # Forward (z-axis of view space)
        f = (eye[0]-target[0], eye[1]-target[1], eye[2]-target[2])
        fl = math.hypot(*f)
        if fl < 1e-10: return Matrix4.identity()
        f = (f[0]/fl, f[1]/fl, f[2]/fl)

        # Right (x-axis)
        s = (up[1]*f[2] - up[2]*f[1],
             up[2]*f[0] - up[0]*f[2],
             up[0]*f[1] - up[1]*f[0])
        sl = math.hypot(*s)
        if sl < 1e-10: return Matrix4.identity()
        s = (s[0]/sl, s[1]/sl, s[2]/sl)

        # Up (y-axis)
        u = (s[1]*f[2] - s[2]*f[1],
             s[2]*f[0] - s[0]*f[2],
             s[0]*f[1] - s[1]*f[0])

        return [
            s[0], u[0], f[0], 0,
            s[1], u[1], f[1], 0,
            s[2], u[2], f[2], 0,
            -s[0]*eye[0]-s[1]*eye[1]-s[2]*eye[2],
            -u[0]*eye[0]-u[1]*eye[1]-u[2]*eye[2],
            -f[0]*eye[0]-f[1]*eye[1]-f[2]*eye[2],
            1
        ]

    @staticmethod
    def transform(m, x, y, z, w=1.0):
        """Multiply 4-element vector (x,y,z,w) by matrix m.
        Returns (x', y', z', w').
        """
        return (
            m[0]*x + m[4]*y + m[8]*z  + m[12]*w,
            m[1]*x + m[5]*y + m[9]*z  + m[13]*w,
            m[2]*x + m[6]*y + m[10]*z + m[14]*w,
            m[3]*x + m[7]*y + m[11]*z + m[15]*w
        )
```

#### B3. Rewrite `Camera` class

Replace the entire `camera.py` content:

```python
import math
from config import *

class Camera:
    def __init__(self):
        # 3D camera state
        self.eye = [0.0, -CAM_3D_DIST, CAM_3D_HEIGHT]
        self.target = [0.0, 0.0, 0.0]
        self.up = (0.0, 0.0, 1.0)

        # Matrices
        self.view_matrix = Matrix4.identity()
        self.proj_matrix = Matrix4.identity()
        self.vp_matrix = Matrix4.identity()

        # Viewport dimensions
        self.vp_x = 0
        self.vp_y = 0
        self.vp_w = WIDTH
        self.vp_h = HEIGHT

    def follow_snake(self, head_q, head_r, direction_idx):
        from utils import hex_to_pixel
        hx, hy = hex_to_pixel(head_q, head_r)
        dx, dy = DIR_VECTORS[direction_idx]
        hz = 2.0  # head vertical offset

        # Camera position: behind and above the snake head
        desired_eye = [
            hx - dx * CAM_3D_DIST,
            hy - dy * CAM_3D_DIST,
            hz + CAM_3D_HEIGHT
        ]
        # Look-at target: slightly ahead of the head
        desired_target = [
            hx + dx * CAM_3D_LOOKAHEAD,
            hy + dy * CAM_3D_LOOKAHEAD,
            hz
        ]

        # Smooth interpolation
        lerp_speed = CAM_3D_LERP
        self.eye[0] += (desired_eye[0] - self.eye[0]) * lerp_speed
        self.eye[1] += (desired_eye[1] - self.eye[1]) * lerp_speed
        self.eye[2] += (desired_eye[2] - self.eye[2]) * lerp_speed
        self.target[0] += (desired_target[0] - self.target[0]) * lerp_speed
        self.target[1] += (desired_target[1] - self.target[1]) * lerp_speed
        self.target[2] += (desired_target[2] - self.target[2]) * lerp_speed

        # Rebuild matrices
        self.view_matrix = Matrix4.look_at(
            (self.eye[0], self.eye[1], self.eye[2]),
            (self.target[0], self.target[1], self.target[2]),
            self.up
        )
        self.proj_matrix = Matrix4.perspective(
            CAM_3D_FOV_RAD, WIDTH / HEIGHT, CAM_3D_NEAR, CAM_3D_FAR
        )
        self.vp_matrix = Matrix4.multiply(self.view_matrix, self.proj_matrix)

    def project(self, x, y, z=0):
        # Debug fallback: use old isometric math for A/B comparison
        if DEBUG_OLD_CAMERA:
            return self._project_old(x, y, z)

        # MVP transform: world → clip space
        cx, cy, cz, cw = Matrix4.transform(self.vp_matrix, x, y, z, 1.0)

        # Avoid division by zero (points behind camera)
        if cw <= 1e-10:
            return (-999, -999, 99999)

        # Perspective divide → NDC [-1, 1]
        nx = cx / cw
        ny = cy / cw
        nz = cz / cw

        # Viewport transform → screen pixels
        sx = nx * self.vp_w * 0.5 + self.vp_w * 0.5 + self.vp_x
        sy = -ny * self.vp_h * 0.5 + self.vp_h * 0.5 + self.vp_y

        # Return screen position + view-space depth (for fog & sorting)
        # nz is in NDC [-1,1]; remap to [0, far] for depth
        depth = (nz * 0.5 + 0.5) * CAM_3D_FAR
        return (sx, sy, depth)

    def _project_old(self, x, y, z=0):
        """Old isometric projection retained for A/B comparison during dev."""
        wx = x - self.offset_x
        wy = y - self.offset_y
        y_rot = wy * math.cos(TILT) - z * math.sin(TILT)
        depth = -wy * math.sin(TILT) - z * math.cos(TILT)
        z_cam = depth + CAM_DIST
        factor = FOV / z_cam if z_cam > 0 else 999
        sx = wx * factor + WIDTH / 2
        sy = y_rot * factor + Y_OFFSET
        return sx, sy, z_cam
```

**⚠️ Important:** The old camera used `self.offset_x/y` — these no longer exist. The debug fallback `_project_old()` references them but they won't be updated. It is for **A/B comparison only** during initial testing, not for gameplay. Remove `DEBUG_OLD_CAMERA` and `_project_old` before finalizing.

#### B4. Update `follow_snake()` call site (`main.py:411`)

The current call passes only `(head_position)`:

```python
# main.py:411 (CURRENT)
self.camera.follow_snake(self.snake[0])
```

Add direction parameter:

```python
# main.py:411 (NEW)
self.camera.follow_snake(self.snake[0], self.direction)
```

Also change the initial follow in `reset()` if applicable (track `self.direction` at reset time).

#### B5. Frustum Culling

In `_build_tile_cache()` (`main.py:166-174`) and `render_tiles_to_fbo()` (`gl_renderer.py:138-139`), add a culling check:

**`main.py:168`** (inside `_build_tile_cache`):

```python
tile_items = []
for q, r in all_hexes():
    cx, cy = hex_to_pixel(q, r)
    sx, sy, depth = self.camera.project(cx, cy, 0)
    # Frustum culling: skip if far behind camera or far off-screen
    if depth > CAM_3D_FAR * 0.95 or depth < 0:
        continue
    if sx < -TILE_CLIP_MARGIN or sx > WIDTH + TILE_CLIP_MARGIN:
        continue
    if sy < -TILE_CLIP_MARGIN or sy > HEIGHT + TILE_CLIP_MARGIN:
        continue
    tile_items.append((depth, q, r))
```

**`gl_renderer.py:138-139`** — same logic before creating the tile VBO.

#### B6. Fog Calibration

Current fog formula (`main.py:226, 499`):
```python
fog_t = max(0, min(1, (z_cam - 320) / 500))
```

New depth values range from `0` (at camera) to `CAM_3D_FAR` (2000) at the far plane. Calibrate:

```python
FOG_NEAR = 100    # fog starts at this depth
FOG_FAR = 800     # fog is fully opaque at this depth
fog_t = max(0, min(1, (depth - FOG_NEAR) / (FOG_FAR - FOG_NEAR)))
```

Add `FOG_NEAR` and `FOG_FAR` to `config.py`.

#### B7. Water Culling

Current water draws 50 strips from `x=-1000` to `x=+1000` at varying `y` positions. Under perspective, most strips are off-screen. Add culling (`main.py:858`):

```python
for wi in range(-25, 25):
    wy = wi * 16
    z_w = -TILE_HEIGHT - 20
    # Culling: skip if the strip's center-projected position is off-screen
    sx_center, sy_center, sd = self.camera.project(0, wy, z_w)
    if sd > CAM_3D_FAR * 0.95 or sd < 0:
        continue
    if sx_center < -200 or sx_center > WIDTH + 200:
        continue
    if sy_center < -200 or sy_center > HEIGHT + 200:
        continue
    # ... render strip as before ...
```

#### B8. Clean up `utils.project()`

After all call sites are verified to use `self.camera.project()`:

1. Remove `utils.py:124-131` (the `project()` function)
2. Update `main.py:9-13` import — remove `project` from the import list
3. Update `particle.py:5` — remove the `_fallback_project` import and fallback code in `Particle.draw()`:

```python
# particle.py:50-54 becomes simply:
def draw(self, surf, game=None):
    sx, sy, depth = game.camera.project(self.x, self.y, self.z)
    # ... rest of draw ...
```

#### B9. GL Renderer Compatibility

The GL renderer passes screen-space coordinates to the vertex shader. Since `Camera.project()` now produces perspective-projected screen coords, **no shader changes are needed**. The vertex data arriving at the GPU is already in pixel space.

**One caveat:** The depth value used for fog in `render_tiles_to_fbo()` (`gl_renderer.py:174`) must use the new depth metric. Change:

```python
# gl_renderer.py:174 — fog_depth must use the new depth from project()
fog_depth = game.camera.project(cx, cy, 0)[2]
```

This already works because `project()` returns `(sx, sy, depth)` uniformly.

### Call Site Reference Table

All 26 locations that must be visually verified:

| # | Location | Line(s) | What it does | Perspective impact |
|---|---|---|---|---|
| 1 | `main.py:_compute_dirty_rects` | 100 | Apple screen bounds | Low — just a rect |
| 2 | `main.py:_compute_dirty_rects` | 112 | Snake segment bounds | Low — just a rect |
| 3 | `main.py:_compute_dirty_rects` | 116 | Particle bounds | Low — just a rect |
| 4 | `main.py:_build_ground` | 130 | Ground under tiles | Medium — parallax shift |
| 5 | `main.py:_build_tile_cache` | 168 | Tile depth sorting | Medium — depth ordering must remain correct |
| 6 | `main.py:_draw_tile_decorations` | 181 | Tile top face vertices | **High** — tile geometry |
| 7 | `main.py:_draw_tile_decorations` | 226 | Fog per tile | Medium — recalibrate |
| 8 | `main.py:_draw_tile_decorations` | 279-280 | Grass blades | Medium — grass position |
| 9 | `main.py:draw_tile` | 434-435 | Full tile (top+sides) | **High** — core visuals |
| 10 | `main.py:draw_tile` | 499 | Tile fog | Medium — recalibrate |
| 11 | `main.py:draw_tile` | 575-576 | Grass in draw_tile | Medium |
| 12 | `main.py:draw_shadow` | 584 | Shadow under objects | Low |
| 13 | `main.py:draw_snake_segment` | 626 | Snake body position | **High** |
| 14 | `main.py:draw_snake_segment` | 653 | Body connection circles | Medium |
| 15 | `main.py:draw_snake_segment` | 667 | Tongue forward direction | Low |
| 16 | `main.py:draw_apple` | 745 | Apple body position | **High** |
| 17 | `main.py:draw_apple` | 753 | Apple stem top | Low |
| 18 | `main.py:render` (water) | 863-864 | Water strip endpoints | **High** — visible change |
| 19 | `main.py:render` (depth sort) | 918 | Apple depth for sorting | Medium |
| 20 | `main.py:render` (depth sort) | 923 | Snake depth for sorting | Medium |
| 21 | `main.py:render` (glow) | 963 | Apple glow position | Low |
| 22 | `particle.py:Particle.draw` | 52 | Particle screen position | Low |

### Execution Order (for implementation)

```
Step 1: 4a fix (toroidal grid) — all_hexes, wrap_coords, import cleanup
Step 2: Add 3D camera constants to config.py
Step 3: Implement Matrix4 class in camera.py
Step 4: Rewrite Camera class (follow_snake + project with MVP)
Step 5: Update follow_snake call site (main.py:411) — add direction param
Step 6: Add frustum culling to _build_tile_cache and gl_renderer
Step 7: Add water culling
Step 8: Calibrate fog constants
Step 9: Set DEBUG_OLD_CAMERA=True, run and compare old vs new visuals
Step 10: Remove DEBUG_OLD_CAMERA, cleanup _project_old, utils.project()
Step 11: Final visual pass — verify all 26 call sites
```

### Verification (4b)

| Test | Procedure | Expected |
|---|---|---|
| Camera follows head | Move snake in any direction | Camera smoothly tracks behind head |
| World stays upright | Turn snake in circles | World doesn't tilt or roll |
| Tiles culled correctly | Note FPS with vs without culling | Fewer tiles rendered, same visual result |
| Perspective visible | Look at far tiles | Tiles shrink with distance (perspective) |
| GL renderer works | Run with `moderngl` installed | Same visuals as software renderer |
| Water visible | Check water at screen bottom | Water fades into distance naturally |
| Fog looks correct | Look at far edge of grid | Tiles fade smoothly into fog color |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Gimbal lock** — up vector aligns with look direction | Low | High (camera inverts) | Ensure `(0,0,1)` up and camera never looks straight down; clamp eye y-distance |
| **Tiles clip through camera** — camera too close to ground | Medium | High | Clamp minimum eye height at `TILE_HEIGHT * 2` |
| **Water fills half the screen** — perspective makes near strips huge | Medium | Medium | Frustum culling on water strips + reduce strip count |
| **Depth sorting order changes** — wrong draw order | Medium | High | Verify `_build_depth_buckets` ordering with new depth values |
| **Direction change mid-lerp** — camera snaps when snake turns | Medium | Low | Lerp prevents snaps; verify smoothness at high speed |
| **GL shaders break** — different coordinate convention | Low | Medium | Keep GL in screen-space; no shader changes needed |
| **Performance regression** — matrix multiply per tile | Low (169 tiles) | Low | `vp_matrix` is computed once per frame; per-tile transform is cheap |
