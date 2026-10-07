# AGENTS.md

This repository is pseudo-pixel: a tool for turning a character reference image into pixel-art
spritesheets with Blender.

- **Using the tool** (making or editing characters and sprites): follow
  [skills/pseudo-pixel/SKILL.md](skills/pseudo-pixel/SKILL.md) and the references next to it. Agents
  that load Agent Skills can install that folder as a skill.
- **Working on the tool itself**: read [PLAN.md](PLAN.md) for the design.
  - `pp/` runs inside Blender's Python. `pp/post.py` is plain numpy and has unit tests:
    `python -m unittest discover tests`.
  - Check changes to the Blender side by building and rendering an example, for example
    `examples/knight` (README has the commands).
  - Keep `SKILL.md` and the references agent-neutral: plain shell commands, no agent-specific tool
    names.
