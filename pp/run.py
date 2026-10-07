"""Run inside Blender: execute a script against the character's .blend, then save it (pp.py run).

The script can import the helpers in this folder (rig, anim, ...). The scene frame rate is set from
character.json first, so keys land on sprite frames.
"""
import json
import os
import sys

import bpy

char_dir, script = sys.argv[sys.argv.index("--") + 1:][:2]
if not bpy.data.filepath:
    bpy.ops.wm.read_factory_settings(use_empty=True)

os.environ["PP_CHAR_DIR"] = char_dir
cfg_path = os.path.join(char_dir, "character.json")
if os.path.exists(cfg_path):
    with open(cfg_path, encoding="utf-8") as f:
        bpy.context.scene.render.fps = json.load(f)["output"]["fps"]
    bpy.context.scene.render.fps_base = 1

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with open(script, encoding="utf-8") as f:
    exec(compile(f.read(), script, "exec"), {"__name__": "__main__", "__file__": script})

name = os.path.basename(os.path.normpath(char_dir))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(char_dir, name + ".blend"))
print(f"saved {name}.blend")
