# pseudo-pixel: Plan

Turn a 2D reference image into pixel-art spritesheets using the Dead Cells workflow:
reference -> 3D model matching the reference -> rigged 3D animation -> toon render from the reference's
angle, sampled at the sprite frame rate -> spritesheet.

An LLM coding agent does the modelling, rigging and animation by writing Blender Python. Blender does the
rendering. The tool is model-agnostic: any agent and model that can run shell commands, write Python and
look at images can drive it. The user can open the result in Blender at any point, change it by hand, and
keep going.

## Goals

1. **One-shot:** give a reference image and a list of animations, get spritesheets out.
2. **Reuse:** a character is built once. Asking for a new animation later reuses its model and rig.
3. **Configurable output:** frame size (e.g. 32x32), frame rate (e.g. 12 fps), palette, outline, and so on.
4. **Hand-editable:** the user can tweak the model, rig and animations in Blender, and can also ask the agent
   to make changes in plain language. Neither one overwrites the other's work.

## Non-goals (for now)

- Generating characters from text alone (a reference image is required).
- Mixamo or other external services. Blender is the only required dependency; the image-to-3D generator
  (TripoSG, milestone 7) is an optional local setup.
- Multiple facing directions by default. Sheets are rendered from the reference's angle; flip them in
  the game engine for the mirrored direction. (Extra camera angles are available through `views`.)
- Hand weight painting (see "Rig" below). Optional automatic smooth skinning exists (milestone 5).
- A GUI or a standalone app. The interface is a coding agent plus a skill.

## Shape of the project

The project has two parts:

- **The tool (this repo):** an Agent Skill (`SKILL.md`) plus Blender Python scripts and helper libraries.
- **A workspace (the user's):** any folder with a `characters/` directory. This is where the generated
  characters live. The workspace is kept separate from the tool so users can version their characters
  in their own repo.

```
pseudo-pixel/                       # this repo
  AGENTS.md                         # points agents without skill support at SKILL.md
  skills/pseudo-pixel/
    SKILL.md                        # workflow, conventions, review checklists
    references/
      modelling.md                  # how to turn a reference into parts
      rig.md                        # bone names, axes, rotation conventions
      animation.md                  # timing, key poses, loop rules, common recipes
  pp/                               # runs inside Blender's bundled Python
    rig.py                          # skeletons (humanoid, extras, custom) and the axis convention
    build.py                        # modelling helpers (parts, materials)
    anim.py                         # animation helpers (pose, key, loop, mirror, retime)
    info.py                         # `pp.py inspect`: dump a .blend to JSON (not inspect.py, which
                                    #   would shadow the standard library module)
    sprite.py                       # camera, toon materials, frame rendering (shared)
    render.py                       # `pp.py render`: spritesheets + JSON
    post.py                         # quantize, despeckle, outline, pack, review-sheet helpers (numpy)
    preview.py                      # `pp.py preview`: compare, turnaround and contact-sheet previews + checks
    run.py                          # `pp.py run`: apply a script to the .blend and save
    library.py                      # parts and actions saved as JSON for reuse
    model.py                        # generated meshes: import, paint, smooth normals, auto weights, Blueprint
    gen_triposg.py                  # `pp.py generate`: runs TripoSG in its own Python environment
  viewer/
    index.html                      # static sprite viewer; `pp.py view` embeds the characters' and examples' sheets
    view.bat                        # double-click: rebuild the viewer and open it (Windows)
  pp.py                             # thin CLI that finds Blender and runs the scripts above
  examples/
    knight/                         # a sample character, end to end

my-game/                            # a workspace
  characters/
    knight/
      reference.png
      character.json                # output settings and animation list
      knight.blend                  # SOURCE OF TRUTH: model + rig + all actions
      scripts/                      # every script the agent ran against the .blend, in order
        001_build_model.py
        002_anim_idle.py
        003_anim_attack.py
      previews/                     # review renders (compare, turnarounds, contact sheets)
      out/
        idle.png  idle.json
        attack.png  attack.json
```

## Key decisions

### Model-agnostic: the tool never calls an LLM

The model comes from whichever agent is running the tool (Claude Code, Codex, Gemini CLI, OpenCode,
Cursor, and so on), and the user picks the model in that agent. This repo contains no API clients, no
provider abstraction, and no API keys.

- **Deterministic work lives in `pp.py` and `pp/`:** plain CLI commands with text and JSON output. Any
  agent that can run a shell command can use them, and so can a human.
- **Judgement work lives in `SKILL.md` and `references/`:** written as plain Markdown instructions in the
  open Agent Skills format. They use no agent-specific tool names or features. They say "run
  `python pp.py render ...`", not "use the Bash tool".
- **`AGENTS.md`** at the repo root points agents that don't load skills to `SKILL.md`.
- **Model requirements:** writing Python, running shell commands, and reading images. Vision is required,
  because the review loops compare renders against the reference. To help weaker models, `pp.py` also
  prints text checks next to every preview: clipped frames, parts thinner than 1.5 px, colour count, and
  the character's height in pixels.
- **Comparing models:** the reference images in `examples/` double as a small test set. Running the same
  requests with different models shows which ones model and animate well. That is a manual comparison,
  not an automated benchmark.
- **Rejected alternative:** having `pp.py` call model APIs itself. It would need a provider layer and keys
  for every vendor. It would also lose the interactive back-and-forth ("make the helmet bigger") that the
  agent session already provides.

### The `.blend` file is the source of truth

The user needs to be able to edit by hand, so the scripts can't be the source of truth. If they were,
rebuilding from them would wipe out the user's manual changes.

- The agent builds the `.blend` once with a generator script, then saves it.
- From then on, every change the agent makes is an **incremental** script that opens the `.blend`, edits it,
  and saves it. The agent never regenerates a character from scratch unless the user asks.
- Before any edit, the agent runs `pp.py inspect`, which dumps objects, bones, materials, actions and keyframes
  to JSON. That way the agent sees the user's manual edits instead of assuming the .blend still matches its
  old scripts.
- The scripts in `scripts/` are a log for readability and debugging. They are not replayed.
- Blender's `.blend1` backups plus the user's own git history cover undo.

### Model: segmented rigid parts

The agent looks at the reference and builds the character from parts: boxes, cylinders, spheres,
cones and extrusions traced from the reference, adjusted with bevels and taper. Each part is
**parented to a single bone**. The goal is fidelity: from the reference's angle, the model should
line up with the drawing in silhouette, proportions, features and colours, using as many parts as that
takes (markings such as stripes and patches are parts too).

- At sprite sizes the joints between rigid parts can't be seen.
- It avoids weight painting completely, which is the most error-prone step for an LLM.
- Users can easily edit it in Blender: select a part, move or scale it, done.
- Each part gets one flat material whose base colour is sampled from the reference.

`build.py` provides compact helpers so the generated scripts stay short and readable, for example:

```python
part("torso", shape="box", size=(0.35, 0.2, 0.45), at=(0, 0, 1.1), bone="chest", color="#5a6b8c", bevel=0.03)
part("helmet", shape="sphere", size=0.22, at=(0, 0, 1.55), bone="head", color="#9aa3ad")
mirror("arm_upper.L")   # creates arm_upper.R on bone upper_arm.R
```

**Measuring in the reference's view.** `character.json` records the reference's camera (`views`,
`elevation`) and scale (`reference_scale`: ground pixel, top pixel, height in units). `build.Ref`
uses them to turn reference pixels into world positions on the line of sight (the agent picks the
depth), and to trace outlines into profile parts that face the camera.

**Game-ready skins.** Once the parts match the reference, `build.smooth_skin` fuses each region's soft
parts (voxel remesh, relax, decimate), transfers each part's colour, and skins the result to the
region's bones, so the character renders as sculpted meshes rather than glued primitives. Small and
hard details stay rigid parts.

**Thin parts flicker.** `build.py` warns when any part is thinner than about 1.5 px in the game view at
the character's `pixels_per_unit`, because such parts flicker in and out between frames. Thin
features (sword blades, straps, antennae) should be thickened rather than dropped.

**Parts are reusable.** Dead Cells' artist called reusing old model parts for new characters "the single most
useful little trick in our workflow". A workspace can keep a `library/` folder of saved parts (helmets,
weapons, monster limbs) and of actions. Actions transfer between characters that share the standard
skeleton, so "give the soldier the knight's walk" is a copy plus a review.

Review loop: `pp.py preview --compare` renders the model from the reference's angle at the reference's
own scale and overlays it on the reference, so every difference in outline, proportion, placement and
colour shows. A turnaround (game view at 4x and at sprite size, then four sides) checks readability and
the hidden sides. The agent fixes and repeats, up to 5 rounds, then reports what still differs.

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
- Foot IK (`rig.add_foot_ik`): planted foot controls with knee poles, switched on per action when it
  keys them, so stances keep the feet on the ground while the hips move. Other actions stay FK.

### Animation: 3D keyframe animation, sampled at the sprite frame rate

Characters are animated the way a 3D game's characters are: key poses on Blender's timeline with
smooth (Bezier) interpolation, anticipation, follow-through and overlapping motion. The sprite sheet is
a sampling of that motion, not a set of hand-picked poses.

- Each animation is a named Action on the armature (`idle`, `walk`, `attack`). Adding a new animation
  means adding a new Action to the existing .blend. The model and rig are untouched.
- **The timeline runs at 24 fps** (set when the .blend is created; a rate changed in Blender is kept).
  Keys sit on whole timeline frames, and lengths are planned in seconds.
- **Sampling:** the renderer samples each action every `1 / fps` seconds (12 fps by default), so the
  number of sprite frames is the animation's length times the fps: a 2 s idle is 24 frames. Changing
  `fps` is a render setting; the animation's speed never changes.
- The agent writes key poses with `anim.py` helpers:

  ```python
  a = action("attack")
  a.key(0,  {"upper_arm.R": (20, 0, 0)})                           # ready
  a.key(6,  {"upper_arm.R": (-40, 0, 0), "chest": (-10, 0, 0)})    # anticipation
  a.key(9,  {"upper_arm.R": (95, 0, 0), "chest": (15, 0, 0)})      # strike
  a.key(12, {"upper_arm.R": (110, 0, 0)})                          # follow-through
  a.key(22, "rest")
  a.end(24)                                                        # one second
  ```

- **Uniform frames:** every sample is a frame with duration `1000 / fps` ms. `merge_holds: true` merges
  identical consecutive frames into one longer frame for engines that read per-frame durations.
- **Speed changes** are `anim.retime(factor, [names])`, which stretches the keys.
- Looping animations: the last frame repeats the first and is left out of the sheet, and the curves
  are cyclic so the motion flows through the loop point.
- Animate in place. The root stays at the anchor, so sprites never drift by sub-pixel amounts (a source of
  flicker). Root motion, such as a lunge, is keyed as location on the `root` bone. The renderer mutes
  those curves and writes the offsets to the JSON instead (`rootMotion: {x, y}` per frame, in pixels
  from the animation's start, y down) for the engine to apply.
- Review loop: the agent renders a contact sheet of every sampled frame, and the same moments at a larger
  size, checks the motion (arcs, spacing, overlap, loops) and adjusts.
- The user can edit keyframes directly in Blender's Action editor. `pp.py inspect` picks up those changes.
- Impact effects such as smears, sparks and slashes are out of scope. Dead Cells sold impact with VFX and
  hit-freeze in the engine, not in the character sprites.

### Rendering: small, crisp, consistent

- **Orthographic camera at the reference's angle** (`views` and `elevation`), at a fixed
  **pixels-per-unit** stored in `character.json`. The light turns with the camera, so every angle is lit
  from the same screen direction.
  The scale never changes between animations. Fitting each animation to its frame would make the
  character change size from one sheet to the next.
- **Anchor:** the root bone's ground position maps to a fixed pixel (by default, bottom-center of the
  frame), so sprites line up in the engine. `anchor` is `bottom-center`, `center`, `bottom-left`, or an
  `[x, y]` pixel measured from the top-left.
- **Toon shading in Eevee:** at render time, every material is swapped for an emission shader:
  half-Lambert N.L against the `light` direction, plus an ordered (4x4 Bayer) dither offset computed
  from the screen pixel (`dither`) -> constant Color Ramp of `shading_steps` tones of the material's
  base colour, hue-shifted cool in shadow and warm in light (`hue_shift`). The dither lives in the
  shader, so the pattern is fixed to screen pixels and stays stable from frame to frame. The .blend keeps ordinary Principled BSDF materials, so it looks normal in
  Blender and the user edits colours there. This uses no lights and casts no shadows, which keeps the
  result predictable; Shader to RGB with a sun lamp was the first idea, but its brightness depends on
  lamp units and cast shadows add noise at 32 px. Shading settings apply to the whole character.
- **No anti-aliasing:** render straight at the target frame size with a single sample, filter size 0 and
  dithering off. Alpha is then thresholded, so every pixel is either fully opaque or transparent.
- **Supersampling (optional, `supersample: n`):** render n x n samples per pixel and reduce them without
  blending: each pixel takes its dominant colour (the idea of K-Centroid downscaling) and is opaque when
  half its samples are. Animations add hysteresis: a pixel keeps last frame's colour while that colour
  still covers a quarter of its samples, so sub-pixel motion and lumpy surfaces stop flickering pixels
  back and forth, while real motion still moves them (loops get a warm-up lap so this carries across the
  loop point). The dither pattern stays on the final pixel grid. On a generated mesh this halves the
  pixels that change between frames of a breathing idle.
- **Clipping check:** if any frame has opaque pixels touching the frame edge, the agent reports it and
  suggests a bigger frame for that animation.

### Post-processing (`pp/post.py`, numpy only)

Steps run in this order: quantize, despeckle, outline (so despeckle never eats outline pixels).

1. **Palette quantization (optional):** map each pixel to the nearest palette colour in OKLab. Palettes are
   a list of hex colours or a `.hex` / `.gpl` file (the Lospec formats).
2. **Outline (optional):** 1 px lines in a set colour, using a 4-neighbour check.
   - `outer`: around the alpha edge.
   - `inner`: also between parts where depth jumps by more than `depth` pixels (default 1), drawn on the
     farther part. For example, an arm in front of the torso. At 32 px, this inner line is often what
     keeps overlapping limbs readable. Object index and depth come from a second render of each sprite
     frame with a material override that writes them to a float EXR (Blender's render passes can't be
     read back from Python without the compositor).
3. **Despeckle (optional):** replace pixels whose colour matches none of their 8 neighbours with the
   most common colour among their 4 neighbours. Converting raw 3D to low resolution produces these, and
   they are a main cause of the flicker Dead Cells' artist said he never solved. The 8-neighbour check
   keeps 1 px diagonal lines such as sword blades. This doesn't fix everything, but it is cheap.
4. **Pack:** frames go left to right in one row by default, or in a grid with `columns` set. With
   `merge_holds`, identical consecutive frames become one frame with a longer duration.
5. **Metadata:** write a JSON file in Aseprite's array format (frame rects, per-frame duration in ms, tags,
   plus root-motion offsets), so existing importers for Godot, Unity, Phaser and others work with it.
6. **Normal map sheet (optional, `normals: true`):** Dead Cells exported a normal map with every frame
   and lit the sprites in-engine. It comes from the same render as the colour sheet, so it costs very
   little.

All of this runs in Blender's bundled Python with numpy, so **Blender is the only dependency**. There is
no Pillow and no pip install. `post.py` doesn't import `bpy`, so its tests run with any Python that has
numpy: `python -m unittest discover tests`.

## `character.json`

```json
{
  "name": "knight",
  "reference": "reference.png",
  "reference_scale": { "ground": [128, 234], "top": 14, "height": 1.6 },
  "rig": "humanoid",
  "output": {
    "frame": [64, 64],
    "pixels_per_unit": 34,
    "views": [0],
    "elevation": 0,
    "anchor": "bottom-center",
    "fps": 12,
    "palette": "palettes/endesga-32.hex",
    "shading_steps": 4,
    "dither": 0.35,
    "hue_shift": 0.5,
    "light": [-1, -1, 1],
    "outline": { "color": "#1a1c2c", "mode": "inner" },
    "despeckle": true,
    "merge_holds": false,
    "normals": false
  },
  "animations": {
    "idle":   { "loop": true },
    "attack": { "loop": false, "frame": [96, 64] }
  }
}
```

Per-animation keys override `output`. Changing any setting is a render-only change: rendering again is
cheap and never touches the .blend.

## Workflows (what the skill handles)

| User says | Agent does |
|---|---|
| "Make a character from `ref.png` with idle and attack" | Create `characters/<name>/`, write `character.json`, build model + rig, review loop, author each action, review loop, render sheets |
| "Add a walk animation to the knight" | `inspect` -> new `walk` action on the existing rig -> review -> render `walk` only |
| "Make the knight's helmet bigger" / "the attack needs more windup" | `inspect` -> incremental edit script -> review -> re-render affected sheets |
| "Render everything at 96x96 with the Sweetie 16 palette" | Edit `character.json` -> re-render (no .blend changes) |
| "Change the knight to 8 fps" | Edit `character.json` -> re-render (the motion is sampled less often) |
| "Make the attack faster" | `anim.retime(0.75, ["attack"])` -> review -> re-render |
| "Give the soldier the knight's walk" | Copy the action (same skeleton), review, render |
| User edited the .blend by hand, then "re-render" | Render only. The agent does not touch the .blend |

## CLI (`pp.py`)

A thin wrapper so the skill and the user run the same commands:

```
python pp.py inspect  characters/knight
python pp.py preview  characters/knight [--compare] [--turnaround] [--anim attack]
python pp.py render   characters/knight [attack]
python pp.py run      characters/knight scripts/004_bigger_helmet.py    # apply an edit script and save
python pp.py view                                                        # play every sheet in the viewer
python pp.py generate characters/knight art/knight_cutout.png           # optional: a mesh from one image
```

It finds Blender through `BLENDER` (an env var), then `PATH`, then the default install locations, and runs
`blender -b <file.blend> -P <script> -- <args>`. It hides Blender's own progress output (`--verbose`
shows it), and `run` sets the scene frame rate from `character.json` before the script runs.

Pose values in `inspect` output use the same convention as `anim.py`, and each key lists every animated
bone, so a key can be pasted into an edit script.

## Milestones

1. **Render pipeline (done):** a hand-written test character (boxes on a skeleton) with one hand-written action.
   Get camera, pixels-per-unit, anchor, toon shading, no-AA, hold merging, quantize, outlines, despeckle,
   pack and JSON working. This is fully deterministic and can be tested without an LLM. Normal-map sheets
   moved to milestone 5.
2. **Rig + animation helpers (done):** the humanoid template, axis conventions, `anim.py`, `pp.py
   inspect`, contact-sheet previews (and the turnaround preview from milestone 3). Hand-written idle,
   walk and attack in `examples/humanoid/`.
3. **Modelling helpers + reference-to-model (done):** `build.py` (parts, mirroring, the `Ref`
   measuring helper), turnaround previews, `references/modelling.md`. Tested on three references drawn
   for the purpose: an armoured knight with sword and shield (`examples/knight`), a caped mage with a
   staff (`examples/mage`) and a slime on a custom rig with squash-and-stretch keys (`examples/slime`).
   What the review loop caught went into `modelling.md`: capes deeper than the body cover it, face
   features must stick out in y to show from the side, spheres sunk into the ground show when the
   character leaves it (hence the `dome` shape).
4. **The skill (done):** `SKILL.md` that ties the workflows together, including the review loops and the
   "never overwrite the .blend" rule, plus `AGENTS.md`, `pp.py new` and `anim.import_action` (copy an
   action from another character). End-to-end example in `examples/knight/`: model, idle in the
   reference's pose, walk and attack, with the rendered sheets committed.
5. **Extras (done):**
   - **Normal-map sheets:** `normals: true` renders camera-space normals into `<name>_n.png`, with the
     same layout as the colour sheet.
   - **Parts and actions library:** `pp/library.py` saves parts (relative to their bones) and actions
     (in the `anim.py` convention) as JSON, so they can be read, diffed and reused across characters.
   - **More facing directions:** `views: [0, 90, ...]` renders extra camera angles as separate sheets.
   - **IK:** `anim.leg_ik` solves the two-bone leg analytically and returns ordinary FK keys, so feet
     can be planted without IK constraints, and `inspect` and hand edits keep working on plain
     rotations.
   - **Smooth skinning:** `build.smooth_skin()` joins the parts into one auto-weighted mesh. The rigid
     parts stay as the editable source.
   - **Packaging:** a Claude Code plugin and marketplace (`.claude-plugin/`), a Gemini CLI extension
     (`gemini-extension.json`), and `AGENTS.md` for everything else.
6. **Fidelity and 3D animation (done):**
   - Sheets are rendered from the reference's angle (`views`, `elevation`), and `build.Ref` measures
     in that view.
   - Modelling aims to match the reference, checked with `pp.py preview --compare`.
   - Actions are smooth 3D animation on a 24 fps timeline, sampled at the sprite fps. Default frame
     64x64.
   - A static viewer (`pp.py view`, from `viewer/index.html`) finds every sheet in `characters/` and
     `examples/` and plays them with speed, zoom, stepping and root motion.

7. **Generated meshes and clarity (done):**
   - `pp.py generate` runs TripoSG on one image; `model.py` imports, paints (flat colours, or a flat
     material map for photo references), smooths the shading normals and auto-weights the mesh (through
     a watertight 10x copy, where bone heat weighting otherwise fails).
   - `supersample` renders n x n samples per pixel and keeps each pixel's dominant colour, with
     frame-to-frame hysteresis, so pixels stop flickering as the model moves.
   - `anim.aim` points a bone's prop (a blade, a barrel) in a world direction, for weapon poses.
   - Animation guidance for clarity: calm idles, few strong eased poses, motion in whole pixels.

## Research notes

What the plan takes from existing 3D-to-pixel pipelines:

- **Dead Cells** ([Game Developer deep dive](https://www.gamedeveloper.com/production/art-design-deep-dive-using-a-3d-pipeline-for-2d-animation-in-i-dead-cells-i-),
  [80.lv interview](https://80.lv/articles/interview-with-the-developers-of-dead-cells)):
  - Simple models in 3DS Max with a basic skeleton.
  - A homebrew tool ("Cruncher") rendered frames at tiny size with no anti-aliasing, plus a normal map
    per frame, using a basic toon shader.
  - Pose-to-pose keys with as few frames as possible. Interpolation frames were added only next to keys.
  - Benefits: retakes in minutes (for example, slowing an attack to nerf a weapon), adding armour by
    attaching a part, and reusing parts across monsters.
  - Unsolved: flickering pixels, and the loss of detail.
- **Guilty Gear Xrd** ([GDC talk](https://www.ggxrd.com/Motomura_Junya_GuiltyGearXrd.pdf)): keys without
  in-betweens, and a deliberately limited frame count, to read as 2D.
- **3D pixel-art rendering** ([David Holland](https://www.davidhol.land/articles/3d-pixel-art-rendering/),
  [Blender Studio](https://studio.blender.org/blog/3d-pixel-art-in-blender/)):
  - Outlines from depth and normal discontinuities, using a 4-neighbour kernel.
  - Constant colour ramps for toon steps.
  - Pixel stability only holds under orthographic projection with grid-snapped movement.
  - "A lot of the work in 3D pixel art is getting 3D effects to look 2D."
- **K-Centroid downscaling** ([Astropulse](https://astropulse.itch.io/k-centroid)): pick each low-res
  pixel's dominant colour instead of blending or point sampling; the idea behind `supersample`.
- **Guilty Gear Xrd's normals:** hand-edited vertex normals give clean cel-shading bands; `smooth_normals`
  does the automatic version (normals from a smoothed copy).
- **Saint11** ([3D as reference](https://saint11.art/blog/3d-ref/)): raw 3D downscaled to pixel art looks
  "horrible" without further work. This is why outlines, palette mapping and despeckle are part of the
  pipeline rather than extras. Hand cleanup in Aseprite stays an option for hero frames.

## Decided

- **Blender:** 5.2 LTS minimum (developed against 5.2.2, bundled Python 3.13, numpy 2.3).
- **License:** MIT.

## Open questions

- **Default palette:** none (keep the model's flat colours), or ship a few Lospec palettes in `palettes/`?
