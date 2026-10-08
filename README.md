# pseudo-pixel

Turn a 2D reference image into pixel-art spritesheets, using the Dead Cells workflow:
reference -> 3D model matching the reference -> rigged 3D animation -> toon render from the
reference's angle, sampled at the sprite frame rate -> spritesheet.

An LLM coding agent builds the model, rig and animations in Blender, and you can edit any of them by hand
in Blender as well. It works with any agent and model that can run shell commands, write Python and read
images.

![The knight example: reference image, then its idle, walk and attack sheets at 2x](docs/knight.png)

*`examples/knight`: the reference, then the idle, walk and attack sheets an agent built from it
(shown at 2x).*

**Status:** every milestone in [PLAN.md](PLAN.md) is implemented: render pipeline, rig and animation
helpers, modelling helpers, the agent skill, and the extras (normal maps, extra views, a parts and
actions library, leg IK, optional smooth skinning, agent packaging).

## Using it with an agent

Install Blender 5.2 or newer, clone this repository, then give your agent the skill:

- **Claude Code:** `/plugin marketplace add craigrusselltiu/pseudo-pixel`, then
  `/plugin install pseudo-pixel@pseudo-pixel`. Or run Claude Code inside the clone.
- **Gemini CLI:** `gemini extensions install https://github.com/craigrusselltiu/pseudo-pixel`.
- **Codex, OpenCode, Cursor and others:** run the agent in the clone (it reads [AGENTS.md](AGENTS.md)),
  or copy `skills/pseudo-pixel` wherever your agent loads Agent Skills from.

The skill is [skills/pseudo-pixel/SKILL.md](skills/pseudo-pixel/SKILL.md). Then ask for what you want,
for example:

- "Make a character from `art/knight.png` with idle, walk and attack."
- "Add a hit animation to the knight."
- "Make the knight's helmet bigger" or "the attack needs more windup."
- "Render the knight at 96x96 with the Sweetie 16 palette, from the side."

The agent models the character to match the reference as closely as it can, fuses the parts into
game-ready sculpted skins, and renders it from the reference's own angle: a character facing the
camera in the reference faces the camera in the sprites. Legs have foot IK, so idles, attacks and
hits keep the feet planted while the body bounces, shifts its weight and recoils.
It animates the model as for a 3D game (smooth motion on a 24 fps timeline), and the renderer samples
that motion at the sprite frame rate (12 fps by default), so a 2-second idle becomes 24 frames: a
1536x64 sheet at the default 64x64 frame size.

Characters live in `characters/<name>/` in your project, with the reference, `character.json`, the
`.blend` (the source of truth, which you can open and edit in Blender at any time), a numbered log of
the scripts it ran, review previews, and `out/` with the sheets. In this repository `characters/` is
git-ignored, so you can try the tool in the clone.

## Generating the model with an image-to-3D model

Instead of building the character from parts, pseudo-pixel can generate its mesh from one image with
[TripoSG](https://github.com/VAST-AI-Research/TripoSG) (MIT), an open-weight image-to-3D model running on
your own GPU, then import it, colour it from the references, rig it and animate it as usual:

```
python pp.py generate characters/<name> <image with a transparent background>
```

TripoSG has ~8 GB of weights and takes about 3.5 minutes per model on an RTX 3060 (12 GB).

Setup, once: clone TripoSG and make a Python environment for it next to this repository
(`../pp-gen/TripoSG`, `../pp-gen/venv`, or point `PP_TRIPOSG` and `PP_GEN_PYTHON` elsewhere) with CUDA PyTorch and the repo's requirements; the weights download on first
use. `pp/model.py` has the helpers that take it from there: `import_mesh` (face +x, scale, decimate),
`paint` (flat colour regions projected from the reference sheets), `smooth_normals` (clean toon shading
on a lumpy surface) and `Blueprint` (the sheets and their silhouettes). Render generated characters with
`"supersample": 4`.

## Viewer

`python pp.py view` finds every sheet in `characters/*/out` and `examples/*/out` and opens them in a
local viewer: pick a character and an animation (and a direction, for 8-direction characters), play,
pause, step, change the speed and zoom, toggle looping and root motion. It writes `characters/viewer.html` with the sheets embedded (from the
template [viewer/index.html](viewer/index.html)), so it works offline with no server. Run it again
after rendering to pick up new sheets, or on Windows double-click `viewer/view.bat`, which rebuilds the
viewer and opens it.

## Commands

```
python pp.py new     <character_dir> <reference_image>    # new character folder + character.json
python pp.py run     <character_dir> <script.py>          # apply a script to the .blend and save it
python pp.py inspect <character_dir>                      # the .blend's objects, bones and keys as JSON
python pp.py preview <character_dir> [--compare] [--turnaround] [--anim NAME ...] [--view NAME]   # review images + checks
python pp.py render  <character_dir> [animation ...]      # spritesheets + JSON in out/
python pp.py view                                         # play every sheet in the viewer
python pp.py generate <character_dir> <image>            # a 3D model from an image (TripoSG)
python -m unittest discover tests                         # post-processing tests (numpy only)
```

## Examples

Each example has its scripts in `scripts/`, numbered in the order they run. To rebuild one from
scratch (the first script creates the rig, so it needs a fresh .blend):

```
rm -f examples/knight/knight.blend
for s in examples/knight/scripts/*.py; do python pp.py run examples/knight "$s"; done
python pp.py preview examples/knight --turnaround
python pp.py render examples/knight
```

Each one shows a different camera, from the common pixel-art perspectives:

- `examples/knight`: an armoured humanoid with sword and shield, modelled from its reference, with
  idle, walk and attack, in side view (a platformer). Its rendered sheets are committed in `out/`.
- `examples/humanoid`: the bare rig and animation test character, in a battle view (`views: [110]`,
  `elevation: 15`): facing the camera, turned slightly to screen left, slashing toward the viewer.
- `examples/mage`: a caped, robed humanoid with a staff, seen from 45 degrees above and facing
  south-east (`views: [45]`, `elevation: 45`).
- `examples/slime`: a non-humanoid on a custom two-bone rig, with squash-and-stretch idle and hop, in
  2:1 isometric facing south-west (`views: [135]`, `elevation: 30`).
- `examples/test`: the render pipeline's test character, in side view.

The reference images in the examples are simple drawings made for testing. Conventions for
modelling, rigs and animation are in [skills/pseudo-pixel/references](skills/pseudo-pixel/references).

Blender is found via the `BLENDER` environment variable, `PATH`, or the default install location.

Render settings live in the character's `character.json` under `output`, and each animation can override
them:

| Key | Default | Meaning |
|---|---|---|
| `frame` | required | Frame size in pixels, `[w, h]` |
| `pixels_per_unit` | required | Scale: pixels per Blender unit, the same for every animation |
| `fps` | required | Sprite frame rate: how many frames are sampled per second of animation (the Blender timeline runs at 24 fps) |
| `anchor` | `"bottom-center"` | Pixel the root's ground position maps to: `bottom-center`, `center`, `bottom-left`, or `[x, y]` |
| `shading_steps` | `4` | Toon tones per material (`1` is flat colour). Applies to the whole character |
| `dither` | `0.35` | Ordered (Bayer) dithering between neighbouring tones: `0` is hard bands, `1` dithers across each whole band |
| `hue_shift` | `0.5` | How far darker tones lean cool (blue-purple) and the lit tone warm, as pixel artists shade; `0` keeps every tone the base hue |
| `light` | `[-1, -1, 1]` | Direction toward the key light, relative to the camera (+X is screen right, -Y is toward the camera, +Z up) |
| `palette` | none | List of hex colours, or a `.hex` / `.gpl` file relative to the character folder |
| `despeckle` | `false` | Remove isolated single pixels |
| `outline` | none | `{"color": "#1a1c2c", "mode": "outer" or "inner", "depth": 1}` |
| `columns` | one row | Frames per row in the sheet |
| `merge_holds` | `false` | Merge identical consecutive frames into one frame with a longer duration |
| `supersample` | `1` | Samples per pixel along each axis (`4` renders 4x4). Each pixel takes its dominant colour and keeps it from frame to frame until a new colour clearly takes over, so pixels stop flickering as the model moves. Use `4` for generated or detailed meshes |
| `normals` | `false` | Also write a normal-map sheet (`<name>_n.png`) for lighting sprites in the engine |
| `views` | `[0]` | Camera angles in degrees around the character: 0 its right side (facing screen right), 90 its front, 180 its left side, 270 its back. Set the first to the reference's angle; more than one writes `<name>_<angle>` sheets. A `{name: angle}` object names them instead, for 8-direction sprites: `{"S": 90, "SE": 45, "E": 0, "NE": 315, "N": 270, "NW": 225, "W": 180, "SW": 135}` writes `idle_S`, `idle_SE`, ... |
| `elevation` | `0` | Camera height in degrees: how far it looks down on the character |
| `loop` | `false` | Per animation: the last frame repeats the first and is left out |

## Requirements

- Blender 5.2 LTS or newer
- A coding agent with a vision-capable model (Claude Code, Codex, Gemini CLI, OpenCode, etc.)

## License

MIT
