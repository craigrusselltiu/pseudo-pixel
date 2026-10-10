---
name: pseudo-pixel
description: Turn a reference image of a character, creature, vehicle or prop into pixel-art spritesheets (idle, run, attack, drive, ...) by generating a 3D model of it (TripoSG), rigging and colouring it, turning it into a PS1-style low-poly model, animating it as for a 3D game, and rendering the motion small from 8 directions with dithered toon shading. Use when the user wants sprites or spritesheets of anything, wants to add or change animations of an existing pseudo-pixel character, or wants to change how its sheets are rendered (size, fps, palette, outline, angle).
---

# pseudo-pixel

You make sprites of whatever the reference shows (a character, a creature, a vehicle, a prop) with
Blender Python scripts, review the renders by looking at them, and render spritesheets. Blender does
all the rendering. You do the rigging, colouring and animation. Everything below says "character" for
whatever the subject is.

The pipeline: **reference image -> generated 3D mesh (TripoSG) -> rig -> colour -> PS1 low-poly model ->
animations -> spritesheets.** The sprites should look like the reference from its own side, with every
other side believable: same proportions, features and colours, as a faceted low-poly model with
flat-coloured triangles (as PS1 games were).

## Tools

`pp.py` sits at the root of the pseudo-pixel repository (two folders above this file). Run it with any
Python 3. It finds Blender through the `BLENDER` environment variable, `PATH`, or the default install
location (Blender 5.2 or newer).

```
python pp.py new      <char_dir> <reference_image>  # new character folder + character.json (PS1 look)
python pp.py generate <char_dir> [--seed N]         # cut out the reference, measure it, TripoSG -> model/generated.glb
python pp.py run      <char_dir> <script.py>        # run a script against the .blend, then save it
python pp.py inspect  <char_dir>                    # the .blend's current state as JSON
python pp.py preview  <char_dir> --compare          # the model over the reference, same scale and angle
python pp.py preview  <char_dir> --turnaround       # the model from every view, large and at sprite size
python pp.py preview  <char_dir> --anim <name>      # contact sheets for an animation (--view E: from that view)
python pp.py render   <char_dir> [<name> ...]       # spritesheets + JSON in <char_dir>/out
python pp.py view                                   # play every rendered sheet in the browser
```

Scripts run inside Blender and can import the helpers: `model` (import, rig fitting, weights, paint,
props, low poly), `rig` (skeletons), `anim` (actions, `leg_ik`, `aim`), `build` (parts and `Ref`) and
`library` (parts and actions saved as JSON). Read the reference before writing a script of that kind:

- [references/generated.md](references/generated.md): the pipeline step by step, with code.
- [references/rig.md](references/rig.md): bone names, axes, rotation signs.
- [references/animation.md](references/animation.md): 3D keyframing, timing, loops, review.
- [references/modelling.md](references/modelling.md): parts, `paint` and `flatten` in detail, building
  from parts.
- [references/render.md](references/render.md): every `character.json` render setting.

## Rules

1. **Characters live in `characters/<name>/`** in the workspace (the current project). Everything for
   a character, including its sheets in `out/`, stays in that folder.
2. **The .blend is the source of truth.** The user may have edited it by hand. Build it from scratch
   only when creating the character (or when the user asks). Every later change is a new, small
   script that edits the existing .blend.
3. **Inspect before every edit.** Run `pp.py inspect` and work from what it reports, not from your
   memory of earlier scripts.
4. **Number your scripts** in `<char_dir>/scripts/`: `001_model.py`, `002_rig.py`, `003_paint.py`, ...
   Write each one there, then `pp.py run` it. Never edit a script that has already run: write a new
   one. The folder is a log of what was done.
5. **Look at every preview** before moving on, and be strict: compare against the reference, from all 8
   views, at sprite size, and list every difference before fixing any. Up to 5 review rounds per step,
   then stop and tell the user what still differs.
6. **Render settings live in `character.json`**, not in the .blend. Changing them (size, fps, palette,
   angle) only needs `pp.py render`.
7. **Stay general.** Measure positions on the mesh and the reference (`model.centre`, `model.front`,
   `B.k`) rather than guessing numbers, and use the helpers for what they cover. Per-character fixes
   are small scripts in the character's folder; never change the tool for one character.
8. Keep every part over 1.5 px thick at sprite size, keys on whole timeline frames, and never move the
   root to travel (use root motion).
9. **Human checkpoints.** Until the user says they trust the workflow and can skip them, stop for
   their approval at three points of every new character: the generated shape, the colours (on the
   low-poly model, from all 8 views), and the finished animations before rendering sprites. Show the previews, say what
   you checked and what still differs from the reference, and wait. Edits to an existing character
   stop once, before rendering.

## Workflows

### New character (or creature, vehicle, prop)

Follow [references/generated.md](references/generated.md):

1. `pp.py new`, `pp.py generate`, set `reference_scale.height`, and add the animations the user asked
   for to `character.json` (for example `"idle": {"loop": true}`).
2. `001_model.py`: `model.import_mesh`. Preview `--compare --turnaround`. **Checkpoint 1: the shape.**
3. `002_rig.py`: bones for what moves, placed on the mesh with `model.front` and `model.centre`;
   `rig.add_foot_ik` for legs; `model.auto_weights` (0 unweighted); `model.limb_weights` for limbs fused
   to the body; rigid parts weighted 100% to their bone. Pose-test the weights.
4. Colour: palette, `model.flatten`, `model.paint`, then review all 8 views and fix every wrong patch
   with measured `model.color_faces` rules (and `model.stripes` for rings), each fix a complete new
   paint script, until every view is right.
5. Parts the generator mushed (weapons, tools, antennas, thin wheels): `model.cut` them and model
   low-poly ones with `model.loft` on their own bones.
6. `model.lowpoly` (with `tubes` for tails and other long round parts). Review the colours again on
   the low-poly model. **Checkpoint 2: the colours.**
7. One script per animation (animation.md); preview each from several views. **Checkpoint 3: the
   motion.** Show the user the `previews/<name>_hires.png` contact sheets and say the .blend can be
   opened in Blender to scrub the actions.
8. `pp.py render`. Report the sheets in `out/`, frame counts and any warnings; `pp.py view` plays them.

If the generator isn't set up (README) and the user doesn't want to set it up, build the subject from
parts instead ([references/modelling.md](references/modelling.md)) and skip `generate`, `import_mesh`
and `paint`; `lowpoly` is only for generated meshes.

### Add an animation

`inspect` -> add it to `character.json` -> new `NNN_anim_<name>.py` -> run -> preview -> review ->
`render <name>`. The model and the other actions stay as they are.

### Change the model or an animation ("bigger hat", "more windup")

`inspect` -> new script that changes only what was asked -> run -> preview -> review -> re-render the
affected sheets. On a low-poly character, recolour with `model.color_faces` on `body`, or change the
guide `body_hi` and run `model.lowpoly` again. `anim.action(name)` rewrites an action, so start from its
keys in the `inspect` output.

### Change render settings ("128x128", "Sweetie 16 palette", "outline", "side view only", "8 fps")

Edit `character.json` (`output`, or one animation's entry to override it there) -> `render`. Don't
touch the .blend. The fps only changes how often the motion is sampled; the animation's speed stays
the same.

### Make an animation faster or slower

New script: `import anim; anim.retime(0.75, ["attack"])` (under 1 is faster), run, preview, render.

### Reuse an animation from another character

Both characters must share bone names. New script: `anim.import_action("../knight/knight.blend",
"walk")` (paths from the character's folder; optionally a new name as the third argument), add the
animation to `character.json`, then preview and adjust keys that depend on proportions or on the rest
pose (lunges, bobs, arm angles).

### Save to or use the library

A workspace can keep a `library/` folder next to `characters/`. Save with
`library.save_parts("../../library/parts/<name>.json", [part names])` or
`library.save_action("../../library/actions/<name>.json", "<action>")`, and load into another character
with `library.load_parts(path, scale=...)` or `library.load_action(path, "<new name>")`.

### The user edited the .blend and asks to re-render

Render only. Don't run scripts against the .blend.

## character.json

`pp.py new` writes it with the PS1 look; `generate` fills in `reference_scale` (but its `height`) and
`references`:

```json
{
  "name": "hero",
  "reference": "reference.png",
  "reference_scale": {"ground": 965, "top": 147, "height": 2.2},
  "references": [{"image": "analysis/flat.png", "mask": "analysis/mask.png", "view": 90, "center": 497}],
  "output": {
    "frame": [64, 64], "pixels_per_unit": 17, "anchor": [32, 52], "fps": 12,
    "shading_steps": 5, "dither": 0.6, "hue_shift": 0.15, "light": [-1, -0.6, 0.7], "despeckle": false,
    "views": {"S": 90, "SE": 45, "E": 0, "NE": 315, "N": 270, "NW": 225, "W": 180, "SW": 135},
    "elevation": 30, "supersample": 4
  },
  "animations": {
    "idle": {"loop": true},
    "attack": {"loop": false, "frame": [96, 64]}
  }
}
```

`views` are camera angles around the character (90 sees its front, 0 its right side, 270 its back);
8 directions write `idle_S`, `idle_SE`, ... Keep the whole character and its animations inside the
frame from every view: the character is about `height * pixels_per_unit` pixels tall, and with the
camera looking down, `anchor` (the pixel under the origin) sits above the frame's bottom. An animation
can have its own `frame`. Every setting: [references/render.md](references/render.md).

## Output

`out/<name>.png` is a spritesheet: one frame per `1 / fps` seconds of animation, in one row (or
`columns` per row), so a 2 s idle at 12 fps in 64x64 frames is a 1536x64 sheet. `out/<name>.json` is in
Aseprite's array format: frame rectangles, per-frame `duration` in ms, a frame tag, and `rootMotion`
offsets in pixels (y down) when the animation moves the root. Engines' Aseprite importers read it
directly.
