# pseudo-pixel: Plan

Turn a 2D reference image into pixel-art spritesheets using the Dead Cells workflow:
reference -> low-detail 3D model -> rigged animation -> low-res toon render -> spritesheet.

Claude does the modelling, rigging and animation by writing Blender Python. Blender does the rendering.
The user can open the result in Blender at any point, change it by hand, and keep going.

## Goals

1. **One-shot:** give a reference image and a list of animations, get spritesheets out.
2. **Reuse:** a character is built once. Asking for a new animation later reuses its model and rig.
3. **Configurable output:** frame size (e.g. 32x32), frame rate (e.g. 12 fps), palette, outline, and so on.
4. **Hand-editable:** the user can tweak the model, rig and animations in Blender, and can also ask Claude
   to make changes in plain language. Neither one overwrites the other's work.

## Non-goals (for now)

- Generating characters from text alone (a reference image is required).
- Image-to-3D ML models, Mixamo, or other external services. Blender is the only dependency.
- Multiple facing directions. Characters face right; flip them in the game engine.
- Smooth skinning or weight painting (see "Rig" below).
- A GUI or a standalone app. The interface is Claude Code plus a skill.

## Shape of the project

The project has two parts:

- **The tool (this repo):** a Claude Code skill (`SKILL.md`) plus Blender Python scripts and helper libraries.
- **A workspace (the user's):** any folder with a `characters/` directory. This is where the generated
  characters live. The workspace is kept separate from the tool so users can version their characters
  in their own repo.

```
pseudo-pixel/                       # this repo
  skills/pseudo-pixel/
    SKILL.md                        # workflow, conventions, review checklists
    references/
      modelling.md                  # how to turn a reference into parts
      rig.md                        # bone names, axes, rotation conventions
      animation.md                  # timing, key poses, loop rules, common recipes
  pp/                               # runs inside Blender's bundled Python
    build.py                        # modelling helpers (parts, bones, materials)
    anim.py                         # animation helpers (pose, key, loop)
    inspect.py                      # dump a .blend to JSON so Claude can see its current state
    render.py                       # render one animation to frames
    post.py                         # quantize to palette, outline, pack sheet + JSON
    preview.py                      # turnaround and contact-sheet previews for review
  pp.py                             # thin CLI that finds Blender and runs the scripts above
  examples/
    knight/                         # a sample character, end to end

my-game/                            # a workspace
  characters/
    knight/
      reference.png
      character.json                # output settings and animation list
      knight.blend                  # SOURCE OF TRUTH: model + rig + all actions
      scripts/                      # every script Claude ran against the .blend, in order
        001_build_model.py
        002_anim_idle.py
        003_anim_attack.py
      previews/                     # review renders (turnarounds, contact sheets)
      out/
        idle.png  idle.json
        attack.png  attack.json
```

## Key decisions

### The `.blend` file is the source of truth

The user needs to be able to edit by hand, so the scripts can't be the source of truth. If they were,
rebuilding from them would wipe out the user's manual changes.

- Claude builds the `.blend` once with a generator script, then saves it.
- From then on, every change Claude makes is an **incremental** script that opens the `.blend`, edits it,
  and saves it. Claude never regenerates a character from scratch unless the user asks.
- Before any edit, Claude runs `inspect.py`, which dumps objects, bones, materials, actions and keyframes
  to JSON. That way Claude sees the user's manual edits instead of assuming the .blend still matches its
  old scripts.
- The scripts in `scripts/` are a log for readability and debugging. They are not replayed.
- Blender's `.blend1` backups plus the user's own git history cover undo.

### Model: segmented rigid parts

Claude looks at the reference and builds the character from low-poly parts: boxes, cylinders, spheres
and simple extrusions, adjusted with bevels and taper. Each part is **parented to a single bone**.

- This is how many low-res 3D-to-sprite pipelines work. At 32-64 px the joints between parts can't be
  seen.
- It avoids weight painting completely, which is the most error-prone step for an LLM.
- Users can easily edit it in Blender: select a part, move or scale it, done.
- Each part gets one flat material whose base colour is sampled from the reference.

`build.py` provides compact helpers so the generated scripts stay short and readable, for example:

```python
part("torso", shape="box", size=(0.35, 0.2, 0.45), at=(0, 0, 1.1), bone="chest", color="#5a6b8c", bevel=0.03)
part("helmet", shape="sphere", size=0.22, at=(0, 0, 1.55), bone="head", color="#9aa3ad")
mirror("arm_upper.L")   # creates arm_upper.R on bone upper_arm.R
```

Review loop: Claude renders a turnaround (front, side, back, plus side view at target resolution), looks
at the images next to the reference, and adjusts. It stops after a fixed number of rounds (default 3) and
reports what still differs.

### Rig: a standard skeleton with predictable axes

- **Humanoid template** with fixed bone names: `root, hips, spine, chest, neck, head,
  upper_arm.L/R, forearm.L/R, hand.L/R, thigh.L/R, shin.L/R, foot.L/R`, plus optional extras such as
  `weapon`, `cape.*`, `tail.*` and `hair.*`.
- Non-humanoids (slimes, bats, turrets) get a custom skeleton that is described in `character.json`.
- **All bones use XYZ Euler rotation, in degrees, in animation scripts.** Quaternions are hard to author
  reliably by hand or by an LLM.
- Bone rolls are set so the same axis always means the same thing, for example local X = bend forward or
  back. This is documented in `references/rig.md`, so "raise the arm 40 degrees" turns into a predictable
  rotation.
- FK only for the first version. IK for feet could come later if walk cycles slide too much.

### Animation: one Blender Action per animation

- Each animation is a named Action on the armature (`idle`, `walk`, `attack`). Adding a new animation
  means adding a new Action to the existing .blend. The model and rig are untouched.
- Claude writes key poses with `anim.py` helpers:

  ```python
  a = action("attack", length=0.6, loop=False)
  a.pose(0.00, {"upper_arm.R": (-30, 0, 0), "chest": (0, 0, 10)})   # windup
  a.pose(0.25, {"upper_arm.R": (110, 0, 0), "chest": (0, 0, -15)})  # strike
  a.pose(0.60, "rest")
  ```

- **Animations are authored in seconds, not frames.** `fps` is a render setting: the renderer samples the
  action at `i / fps` (using Blender subframes), so changing 12 fps to 8 fps doesn't mean rewriting the
  animation.
- Looping animations: the last sample must match the first, and it is left out of the sheet.
- Review loop: Claude renders a contact sheet of all frames and the key poses at a larger size, checks
  silhouette readability and timing, and adjusts.
- The user can edit keyframes directly in Blender's Action editor. `inspect.py` picks up those changes.

### Rendering: small, crisp, consistent

- **Orthographic camera, side view**, at a fixed **pixels-per-unit** stored in `character.json`.
  The scale never changes between animations. Fitting each animation to its frame would make the
  character change size from one sheet to the next.
- **Anchor:** the root bone's ground position maps to a fixed pixel (by default, bottom-center of the
  frame), so sprites line up in the engine.
- **Toon shading in Eevee:** Shader to RGB -> constant Color Ramp (2-3 tone steps per material) from one
  key light whose direction is set in config.
- **No anti-aliasing:** render straight at the target frame size with a single sample and the smallest
  filter size. Every pixel is either fully opaque or transparent.
- **Clipping check:** if any frame has opaque pixels touching the frame edge, Claude reports it and
  suggests a bigger frame for that animation.

### Post-processing (inside Blender's Python, using numpy)

1. **Palette quantization (optional):** map each pixel to the nearest palette colour in OKLab. Palettes are
   a list of hex colours or a `.hex` / `.gpl` file (the Lospec formats).
2. **Outline (optional):** add a 1 px outline around the alpha edge in a set colour, either outer-only or
   including inner edges.
3. **Pack:** frames go left to right in one row by default, or in a grid with `columns` set.
4. **Metadata:** write a JSON file in Aseprite's array format (frame rects, duration in ms, tags), so
   existing importers for Godot, Unity, Phaser and others work with it.

All of this runs in Blender's bundled Python with numpy, so **Blender is the only dependency**. There is
no Pillow and no pip install.

## `character.json`

```json
{
  "name": "knight",
  "reference": "reference.png",
  "rig": "humanoid",
  "output": {
    "frame": [32, 32],
    "pixels_per_unit": 16,
    "anchor": "bottom-center",
    "fps": 12,
    "palette": "palettes/endesga-32.hex",
    "shading_steps": 3,
    "light": [-1, -1, 1],
    "outline": { "color": "#1a1c2c", "mode": "outer" }
  },
  "animations": {
    "idle":   { "loop": true },
    "attack": { "loop": false, "frame": [48, 32], "fps": 15 }
  }
}
```

Per-animation keys override `output`. Changing a setting and rendering again is cheap and never touches
the .blend.

## Workflows (what the skill handles)

| User says | Claude does |
|---|---|
| "Make a character from `ref.png` with idle and attack, 32x32 at 12 fps" | Create `characters/<name>/`, write `character.json`, build model + rig, review loop, author each action, review loop, render sheets |
| "Add a walk animation to the knight" | `inspect` -> new `walk` action on the existing rig -> review -> render `walk` only |
| "Make the knight's helmet bigger" / "the attack needs more windup" | `inspect` -> incremental edit script -> review -> re-render affected sheets |
| "Render everything at 64x64 with the Sweetie 16 palette" | Edit `character.json` -> re-render (no .blend changes) |
| User edited the .blend by hand, then "re-render" | Render only. Claude does not touch the .blend |

## CLI (`pp.py`)

A thin wrapper so the skill and the user run the same commands:

```
python pp.py inspect  characters/knight
python pp.py preview  characters/knight [--turnaround | --anim attack]
python pp.py render   characters/knight [--anim attack]
python pp.py run      characters/knight scripts/004_bigger_helmet.py    # apply an edit script and save
```

It finds Blender through `BLENDER` (an env var), then `PATH`, then the default install locations, and runs
`blender -b <file.blend> -P <script> -- <args>`.

## Milestones

1. **Render pipeline:** a hand-written test character (boxes on a skeleton) with one hand-written action.
   Get camera, pixels-per-unit, anchor, toon shading, no-AA, quantize, outline, pack and JSON working.
   This is fully deterministic and can be tested without an LLM.
2. **Rig + animation helpers:** the humanoid template, axis conventions, `anim.py`, `inspect.py`,
   contact-sheet previews. Hand-write idle, walk and attack to validate the helpers.
3. **Modelling helpers + reference-to-model:** `build.py`, turnaround previews, `references/modelling.md`.
   Test on 3-5 varied references (humanoid, armoured, caped, non-humanoid).
4. **The skill:** `SKILL.md` that ties the workflows together, including the review loops and the "never
   overwrite the .blend" rule. Run the end-to-end example in `examples/knight/`.
5. **Later (only if needed):** normal-map export (Dead Cells used these for dynamic lighting), more
   facing directions, IK, smooth-skinning option, packaging as a Claude Code plugin.

## Decided

- **Blender:** 5.2 LTS minimum (developed against 5.2.2, bundled Python 3.13, numpy 2.3).
- **License:** MIT.

## Open questions

- **Default palette:** none (keep the model's flat colours), or ship a few Lospec palettes in `palettes/`?
