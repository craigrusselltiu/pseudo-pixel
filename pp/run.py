"""Run inside Blender: execute a script against the character's .blend, then save it (pp.py run).

The script can import the helpers in this folder (rig, anim, ...). A new .blend gets a 24 fps timeline
(TIMELINE_FPS), which actions are keyed on; after that the .blend's own rate is kept, so a rate changed
in Blender sticks. The sprite fps in character.json only matters when rendering.
"""
import os
import sys

import bpy

TIMELINE_FPS = 24

char_dir, script = sys.argv[sys.argv.index("--") + 1:][:2]
if not bpy.data.filepath:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps, bpy.context.scene.render.fps_base = TIMELINE_FPS, 1

os.environ["PP_CHAR_DIR"] = char_dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with open(script, encoding="utf-8") as f:
    exec(compile(f.read(), script, "exec"), {"__name__": "__main__", "__file__": script})

name = os.path.basename(os.path.normpath(char_dir))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(char_dir, name + ".blend"))
print(f"saved {name}.blend")
