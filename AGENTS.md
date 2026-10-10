# AGENTS.md

This repository is pseudo-pixel: a tool for turning a character reference image into pixel-art
spritesheets with Blender.

- **Using the tool** (making or editing characters and sprites): follow
  [skills/pseudo-pixel/SKILL.md](skills/pseudo-pixel/SKILL.md) and the references next to it. Agents
  that load Agent Skills can install that folder as a skill.
- **Working on the tool itself**:
  - `pp.py` is the CLI (any Python 3); it runs the scripts in `pp/` inside Blender.
    `pp/gen_triposg.py` runs in the generator's own environment instead.
  - `pp/model.py` is the generated pipeline (import, rig fitting, weights, paint, low poly), `pp/rig.py`
    and `pp/anim.py` the skeleton and actions, `pp/sprite.py` and `pp/post.py` the renderer and its
    pixel post-processing. `pp/post.py` is plain numpy and has unit tests:
    `python -m unittest discover tests`.
  - Check changes to the Blender side by running a character through the pipeline and rendering it,
    or by rebuilding an example (`examples/knight`).
  - The tool must work for any character, not one: keep helpers general and measure from the mesh and
    the reference instead of hard-coding numbers.
  - Keep `SKILL.md` and the references agent-neutral: plain shell commands, no agent-specific tool
    names.
