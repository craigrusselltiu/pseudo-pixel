---
name: pseudo-pixel
description: Turn a 2D character reference image into pixel-art spritesheets (idle, walk, attack, ...) by building a low-poly 3D model, rig and pose-to-pose animations in Blender and rendering them small with toon shading, the Dead Cells workflow. Use when the user wants sprites or spritesheets of a character, wants to add or change animations of an existing pseudo-pixel character, or wants to change how its sheets are rendered (size, fps, palette, outline).
---

# pseudo-pixel

You build and maintain characters with Blender Python scripts, review the renders by looking at them,
and render spritesheets. Blender does all the rendering. You do the modelling, rigging and animation.

## Tools

`pp.py` sits at the root of the pseudo-pixel repository (two folders above this file). Run it with
any Python 3. It finds Blender through the `BLENDER` environment variable, `PATH`, or the default
install location (Blender 5.2 or newer).

```
python pp.py new     <char_dir> <reference_image>   # new character folder + character.json
python pp.py run     <char_dir> <script.py>         # run a script against the .blend, then save it
python pp.py inspect <char_dir>                     # the .blend's current state as JSON
python pp.py preview <char_dir> --turnaround        # model next to the reference, 4 angles
python pp.py preview <char_dir> --anim <name>       # contact sheets for an animation
python pp.py render  <char_dir> [<name> ...]        # spritesheets + JSON in <char_dir>/out
```

Scripts run inside Blender and can import the helpers: `rig` (skeletons), `build` (parts),
`anim` (actions). Read the reference before writing a script of that kind:

- [references/modelling.md](references/modelling.md): reading the reference, `build.part`, review.
- [references/rig.md](references/rig.md): bone names, axes, rotation signs.
- [references/animation.md](references/animation.md): keys, timing, loops, review.

## Rules

1. **The .blend is the source of truth.** The user may have edited it by hand. Build it from scratch
   only when creating the character (or when the user asks). Every later change is a new, small
   script that edits the existing .blend.
2. **Inspect before every edit.** Run `pp.py inspect` and work from what it reports, not from your
   memory of earlier scripts.
3. **Number your scripts** in `<char_dir>/scripts/`: `001_build_model.py`, `002_anim_idle.py`,
   `003_bigger_helmet.py`, ... Write each one there, then `pp.py run` it. Never edit a script that
   has already run: write a new one. The folder is a log of what was done.
4. **Look at every preview** before moving on. Compare against the reference and the checks
   `pp.py` prints. Up to 3 review rounds per step, then stop and tell the user what still differs.
5. **Render settings live in `character.json`**, not in the .blend. Changing them only needs
   `pp.py render`. Changing `fps` also needs re-timed actions (see animation.md).
6. Keep every part over 1.5 px thick, keep keys on whole frames, and never move the root to travel
   (use root motion).

## Workflows

### New character from a reference

1. `python pp.py new characters/<name> <reference>`. Edit `character.json`: `frame`,
   `pixels_per_unit` (the character's height in pixels divided by its height in units), `fps`,
   and the animation list, for example `"idle": {"loop": true}` and `"attack": {"frame": [80, 56]}`.
   Defaults: 48x48 frames, 20 px per unit, 12 fps, 3 tone steps, inner outlines, despeckle.
2. Study the reference (modelling.md, section 1). Write `scripts/001_build_model.py`: the rig
   (`rig.humanoid(...)` with measured proportions, or `rig.custom(...)`), extra bones, then parts.
3. `pp.py run`, then `pp.py preview --turnaround`. Review against the reference and fix with new
   scripts.
4. For each animation, write `scripts/NNN_anim_<name>.py` with `anim.action(...)`, run it, then
   `pp.py preview --anim <name>`. Review the silhouettes and timing, and fix. Make the first idle
   pose match the reference's pose.
5. `pp.py render`. Report the sheets in `out/`, frame counts and any warnings.

### Add an animation

`inspect` -> add it to `character.json` -> new `NNN_anim_<name>.py` -> run -> preview -> review ->
`render <name>`. The model and the other actions stay as they are.

### Change the model or an animation ("bigger helmet", "more windup")

`inspect` -> new script that changes only what was asked (`build.part()` with the same name
replaces a part; `anim.action(name)` rewrites an action, so start from its keys in the `inspect`
output) -> run -> preview -> review -> re-render the affected sheets.

### Change render settings ("64x64", "Sweetie 16 palette", "no outline")

Edit `character.json` (`output`, or one animation's entry to override it there) -> `render`. Don't
touch the .blend.

### Change fps

New script: `import anim; anim.retime(old_fps, new_fps)`, set `fps` in `character.json`, run,
preview every animation, fix any holds that changed too much, render.

### Reuse an animation from another character

Both characters must share bone names. New script:
`anim.import_action("../knight/knight.blend", "walk")` (optionally a new name as the third argument),
add the animation to `character.json`, then preview and adjust keys that depend on proportions
(lunges, bobs).

### The user edited the .blend and asks to re-render

Render only. Don't run scripts against the .blend.

## character.json

```json
{
  "name": "knight",
  "reference": "reference.png",
  "rig": "humanoid",
  "output": {
    "frame": [48, 48], "pixels_per_unit": 20, "anchor": "bottom-center", "fps": 12,
    "shading_steps": 3, "light": [-1, -1, 1],
    "palette": null, "outline": {"color": "#1a1c2c", "mode": "inner"}, "despeckle": true,
    "columns": null, "expand_holds": false
  },
  "animations": {
    "idle": {"loop": true},
    "attack": {"loop": false, "frame": [80, 56]}
  }
}
```

`palette` is a list of hex colours or a `.hex`/`.gpl` file next to `character.json`. `outline.mode`
is `outer` or `inner` (also between overlapping parts). The README's table lists every key.

## Output

`out/<name>.png` is a spritesheet (one row, or `columns` per row). `out/<name>.json` is in Aseprite's
array format: frame rectangles, per-frame `duration` in ms (held poses become longer frames), a frame
tag, and `rootMotion` offsets in pixels (y down) when the animation moves the root. Engines' Aseprite
importers read it directly.
