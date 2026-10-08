---
name: pseudo-pixel
description: Turn a 2D character reference image into pixel-art spritesheets (idle, walk, attack, ...) by building a 3D model in Blender that matches the reference as closely as possible, rigging it, animating it as you would for a 3D game, and rendering the motion small with toon shading from the reference's own camera angle, sampled at the sprite frame rate. Use when the user wants sprites or spritesheets of a character, wants to add or change animations of an existing pseudo-pixel character, or wants to change how its sheets are rendered (size, fps, palette, outline, angle).
---

# pseudo-pixel

You build and maintain characters with Blender Python scripts, review the renders by looking at them,
and render spritesheets. Blender does all the rendering. You do the modelling, rigging and animation.

The goal is a sprite that looks like the reference: same angle, same proportions, same features and
colours. Model as closely to the reference as you can; don't simplify for the sprite size.

## Tools

`pp.py` sits at the root of the pseudo-pixel repository (two folders above this file). Run it with
any Python 3. It finds Blender through the `BLENDER` environment variable, `PATH`, or the default
install location (Blender 5.2 or newer).

```
python pp.py new     <char_dir> <reference_image>   # new character folder + character.json
python pp.py run     <char_dir> <script.py>         # run a script against the .blend, then save it
python pp.py inspect <char_dir>                     # the .blend's current state as JSON
python pp.py preview <char_dir> --compare           # the model over the reference, same scale and angle
python pp.py preview <char_dir> --turnaround        # the model from the game view and 4 sides
python pp.py preview <char_dir> --anim <name>       # contact sheets for an animation (--view E: from that view)
python pp.py render  <char_dir> [<name> ...]        # spritesheets + JSON in <char_dir>/out
python pp.py generate <char_dir> <image>          # a mesh from one image with TripoSG (optional setup)
```

Scripts run inside Blender and can import the helpers: `rig` (skeletons), `build` (parts and the
`Ref` measuring helper), `anim` (actions, including `leg_ik` to plant feet) and `library` (parts and
actions saved as JSON for reuse across characters). Read the reference before writing a script of
that kind:

- [references/modelling.md](references/modelling.md): reading the reference, the view, `build.part`, review.
- [references/rig.md](references/rig.md): bone names, axes, rotation signs.
- [references/animation.md](references/animation.md): 3D keyframing, timing, loops, review.

## Rules

1. **Characters live in `characters/<name>/`** in the workspace (the current project). Everything for
   a character, including its sheets in `out/`, stays in that folder. In the pseudo-pixel repository
   itself `characters/` is git-ignored.
2. **The .blend is the source of truth.** The user may have edited it by hand. Build it from scratch
   only when creating the character (or when the user asks). Every later change is a new, small
   script that edits the existing .blend.
3. **Inspect before every edit.** Run `pp.py inspect` and work from what it reports, not from your
   memory of earlier scripts.
4. **Number your scripts** in `<char_dir>/scripts/`: `001_build_model.py`, `002_anim_idle.py`,
   `003_bigger_helmet.py`, ... Write each one there, then `pp.py run` it. Never edit a script that
   has already run: write a new one. The folder is a log of what was done.
5. **Look at every preview** before moving on, and be strict: compare against the reference, not
   against "good enough for a sprite". Up to 5 review rounds per step, then stop and tell the user
   what still differs.
6. **Render settings live in `character.json`**, not in the .blend. Changing them (size, fps,
   palette, angle) only needs `pp.py render`.
7. **Render from the reference's angle.** Set `views` and `elevation` so the game view matches the
   reference (a reference facing the camera gives sprites facing the camera), unless the user asks
   for another angle.
8. Keep every part over 1.5 px thick in the game view, keep keys on whole timeline frames, and never
   move the root to travel (use root motion).
9. **Human checkpoints.** Until the user says they trust the workflow and can skip them, stop for
   their approval at three points of every new character or remodel: the generated or built shape,
   the colours, and the finished animations before rendering sprites. Show the previews, say what
   you checked and what still differs from the reference, and wait. Edits to an existing character
   stop once, before rendering.

## Workflows

### New character from a generated model

When the image-to-3D generator is set up (README) and the user wants it, or gives a model sheet
(front, side and rear views, ideally a T-pose):

1. Make a transparent-background version of the front view and run
   `python pp.py generate <char_dir> <image>`. Write `scripts/001_model.py`: `model.import_mesh`
   (height from the sheet, aligned to its silhouettes) and `model.smooth_normals`. Preview with
   `pp.py preview --turnaround`. **Checkpoint 1: the shape.** Show the user the turnaround and stop
   until they approve it (or ask for another seed or image).
2. Rig it: a skeleton fitted to the mesh with humanoid bone names (`rig.add_bones`,
   `rig.add_foot_ik`) and `model.auto_weights` (check that its count of unweighted vertices is near
   0, then keep hoods and torsos off the arm bones, and tails off everything but the tail bones).
   A T-pose rest means the arms hang at the sides with `upper_arm` Z about -75.
3. Paint it after rigging, so painting knows the parts: `model.paint(body, B, palette, bake=False,
   regions=..., facing=0.05)` with a flat palette sampled from the sheet and, for every body region,
   the colours it may use; paint the head (and anything else the side and rear sheets draw
   differently) from the front sheet only (modelling.md, section 6). Preview with
   `--compare --turnaround`. **Checkpoint 2: the colours.** Show the user both previews and stop until
   they approve.
4. Animate as below, preview every animation (`--view` for each direction of an 8-direction
   character) and review it yourself first. **Checkpoint 3: the motion.** Show the user the
   `previews/<name>_hires.png` contact sheets and tell them the .blend can be opened in Blender to
   scrub the actions; stop until they approve, then `pp.py render`.

Generated meshes also need `"supersample": 4` in `output` to stay clean at sprite size.

### New character from a reference

1. `python pp.py new characters/<name> <reference>`.
2. Read the reference's angle and scale (modelling.md, section 1) and fill in `character.json`:
   `views: [yaw]` and `elevation` to match the reference's camera, `reference_scale` (the ground
   pixel, the top pixel and the character's height in units), `pixels_per_unit` so the character
   fills about 85% of the frame height (`0.85 * frame height / height in units`), and the
   animation list, for example `"idle": {"loop": true}`. Defaults: 64x64 frames, 12 fps, 4 tones
   with dithering and hue-shifted shadows, inner outlines, despeckle. Give an animation its own
   `frame` if it reaches outside, and move `anchor` up from the bottom when the camera looks down
   (parts toward the camera then draw below the ground point).
3. Study the reference (modelling.md, section 1). Write `scripts/001_build_model.py`: the rig
   (`rig.humanoid(...)` with measured proportions, or `rig.custom(...)`), `rig.add_foot_ik()` for
   legged characters, extra bones, then every part (soft parts with `smooth=2`).
4. `pp.py run`, then `pp.py preview --compare --turnaround`. Fix every difference from the
   reference with new scripts. Once the idle exists, `--compare` shows its first pose, which should
   match the reference's pose. **Checkpoints 1 and 2: the shape and the colours** (built together
   here, as each part has its colour). Show the user both previews and stop until they approve.
5. Fuse the soft parts into game-ready skins, one per region that moves together, each limited to
   its region's bones (`build.smooth_skin(name, parts, voxel=..., relax=..., faces=..., bones=...)`,
   modelling.md section 3). Preview again.
6. For each animation, write `scripts/NNN_anim_<name>.py` with `anim.action(...)`, animated as for a
   3D game with weight, overlap and planted feet (animation.md), run it, then
   `pp.py preview --anim <name>`. Review the motion and fix: it should feel alive, not just move.
   **Checkpoint 3: the motion.** Show the user the `previews/<name>_hires.png` contact sheets (and
   say the .blend can be opened in Blender to scrub the actions); stop until they approve.
7. `pp.py render`, then `pp.py view` to play them. Report the sheets in `out/`, frame counts and any
   warnings.

### Add an animation

`inspect` -> add it to `character.json` -> new `NNN_anim_<name>.py` -> run -> preview -> review ->
`render <name>`. The model and the other actions stay as they are.

### Change the model or an animation ("bigger helmet", "more windup")

`inspect` -> new script that changes only what was asked (`build.part()` with the same name
replaces a part; `anim.action(name)` rewrites an action, so start from its keys in the `inspect`
output) -> run -> preview -> review -> re-render the affected sheets.

### Change render settings ("128x128", "Sweetie 16 palette", "no outline", "side view", "8 fps")

Edit `character.json` (`output`, or one animation's entry to override it there) -> `render`. Don't
touch the .blend. The fps only changes how often the motion is sampled; the animation's speed stays
the same.

### Make an animation faster or slower

New script: `import anim; anim.retime(0.75, ["attack"])` (under 1 is faster), run, preview, render.

### Reuse an animation from another character

Both characters must share bone names. New script:
`anim.import_action("../knight/knight.blend", "walk")` (optionally a new name as the third argument),
add the animation to `character.json`, then preview and adjust keys that depend on proportions
(lunges, bobs).

### Save to or use the library

A workspace can keep a `library/` folder next to `characters/`. Save with
`library.save_parts("../../library/parts/<name>.json", [part names])` or
`library.save_action("../../library/actions/<name>.json", "<action>")`, and load into another character
with `library.load_parts(path, scale=...)` or `library.load_action(path, "<new name>")`. Parts land
relative to their bones, so they fit different proportions; preview afterwards.

### The user edited the .blend and asks to re-render

Render only. Don't run scripts against the .blend.

## character.json

```json
{
  "name": "knight",
  "reference": "reference.png",
  "reference_scale": {"ground": [630, 1170], "top": 185, "height": 2.2},
  "rig": "humanoid",
  "output": {
    "frame": [64, 64], "pixels_per_unit": 24, "anchor": "bottom-center", "fps": 12,
    "views": [70], "elevation": 8,
    "shading_steps": 4, "dither": 0.35, "hue_shift": 0.5, "light": [-1, -1, 1],
    "palette": null, "outline": {"color": "#1a1c2c", "mode": "inner"}, "despeckle": true,
    "columns": null, "merge_holds": false, "normals": false
  },
  "animations": {
    "idle": {"loop": true},
    "attack": {"loop": false, "frame": [96, 64]}
  }
}
```

`views` are camera angles in degrees around the character: 0 sees its right side (facing screen
right), 90 its front, 180 its left side (facing screen left), 270 its back; 70 is a three-quarter view
turned slightly to screen right. The first is the game view; more than one writes `<name>_<angle>`
sheets, and `{name: angle}` names them: 8-direction sprites are `{"S": 90, "SE": 45, "E": 0, "NE": 315,
"N": 270, "NW": 225, "W": 180, "SW": 135}` (`idle_S`, ...). Review each direction with
`pp.py preview --anim <name> --view E`. `elevation` raises the camera to look down. `light` is relative to the camera (+x screen
right, -y toward the camera, +z up). `palette` is a list of hex colours or a `.hex`/`.gpl` file next
to `character.json`. `dither` (0-1) mixes neighbouring tones with an ordered pattern; `hue_shift`
(0-1) makes shadows cooler and light warmer. `outline.mode` is `outer` or `inner` (also between
overlapping parts).
`merge_holds: true` merges identical consecutive frames into one longer frame. `supersample: 4`
renders 4x4 samples per pixel and keeps the dominant colour, with hysteresis from frame to frame, so
pixels stop flickering as the model moves; use it for generated or detailed meshes. `normals: true` adds
a normal-map sheet for lighting sprites in the engine. The README's table lists every key.

## Output

`out/<name>.png` is a spritesheet: one frame per `1 / fps` seconds of animation, in one row (or
`columns` per row), so a 2 s idle at 12 fps in 64x64 frames is a 1536x64 sheet. `out/<name>.json` is
in Aseprite's array format: frame rectangles, per-frame `duration` in ms, a frame tag, and
`rootMotion` offsets in pixels (y down) when the animation moves the root. With `normals`,
`out/<name>_n.png` has the same layout (OpenGL convention: x right, y up, z toward the viewer) and the
JSON names it in `meta.normalMap`. Engines' Aseprite importers read it directly.
