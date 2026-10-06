# pseudo-pixel

Turn a 2D reference image into pixel-art spritesheets, using the Dead Cells workflow:
reference -> low-detail 3D model -> rigged animation -> low-res toon render -> spritesheet.

An LLM coding agent builds the model, rig and animations in Blender, and you can edit any of them by hand
in Blender as well. It works with any agent and model that can run shell commands, write Python and read
images.

**Status:** planning. See [PLAN.md](PLAN.md).

## Usage (so far)

```
python pp.py run    examples/test examples/test/build.py   # build the test character's .blend
python pp.py render examples/test [animation]              # spritesheets + JSON in examples/test/out
```

Blender is found via the `BLENDER` environment variable, `PATH`, or the default install location.

## Requirements

- Blender 5.2 LTS or newer
- A coding agent with a vision-capable model (Claude Code, Codex, Gemini CLI, OpenCode, etc.)

## License

MIT
