# pseudo-pixel

Turn a 2D reference image into pixel-art spritesheets, using the Dead Cells workflow:
reference -> low-detail 3D model -> rigged animation -> low-res toon render -> spritesheet.

An LLM coding agent builds the model, rig and animations in Blender, and you can edit any of them by hand
in Blender as well. It works with any agent and model that can run shell commands, write Python and read
images.

**Status:** the render pipeline, rig and animation helpers work (milestones 1-2); the agent skill is
not written yet. See [PLAN.md](PLAN.md).

## Usage (so far)

```
python pp.py run     <character_dir> <script.py>          # apply a script to the .blend and save it
python pp.py inspect <character_dir>                      # the .blend's objects, bones and keys as JSON
python pp.py preview <character_dir> [--anim NAME ...]    # contact sheets + checks in previews/
python pp.py render  <character_dir> [animation ...]      # spritesheets + JSON in out/
python -m unittest discover tests                         # post-processing tests (numpy only)
```

To try the example humanoid (rig, idle, walk and attack written with `pp/rig.py` and `pp/anim.py`):

```
for s in 001_build 002_idle 003_walk 004_attack; do
  python pp.py run examples/humanoid examples/humanoid/scripts/$s.py
done
python pp.py preview examples/humanoid
python pp.py render examples/humanoid
```

Conventions for rigs and animation scripts are in
[skills/pseudo-pixel/references](skills/pseudo-pixel/references).

Blender is found via the `BLENDER` environment variable, `PATH`, or the default install location.

Render settings live in the character's `character.json` under `output`, and each animation can override
them:

| Key | Default | Meaning |
|---|---|---|
| `frame` | required | Frame size in pixels, `[w, h]` |
| `pixels_per_unit` | required | Scale: pixels per Blender unit, the same for every animation |
| `fps` | required | Sprite frame rate, which is also the Blender timeline rate |
| `anchor` | `"bottom-center"` | Pixel the root's ground position maps to: `bottom-center`, `center`, `bottom-left`, or `[x, y]` |
| `shading_steps` | `3` | Toon tones per material (`1` is flat colour). Applies to the whole character |
| `light` | `[-1, -1, 1]` | Direction toward the key light (+X is screen right, -Y is toward the camera) |
| `palette` | none | List of hex colours, or a `.hex` / `.gpl` file relative to the character folder |
| `despeckle` | `false` | Remove isolated single pixels |
| `outline` | none | `{"color": "#1a1c2c", "mode": "outer" or "inner", "depth": 1}` |
| `columns` | one row | Frames per row in the sheet |
| `expand_holds` | `false` | Repeat held frames instead of giving them longer durations |
| `loop` | `false` | Per animation: the last frame repeats the first and is left out |

## Requirements

- Blender 5.2 LTS or newer
- A coding agent with a vision-capable model (Claude Code, Codex, Gemini CLI, OpenCode, etc.)

## License

MIT
