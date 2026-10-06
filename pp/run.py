"""Run inside Blender: execute a script against the character's .blend, then save it."""
import os
import sys

import bpy

char_dir, script = sys.argv[sys.argv.index("--") + 1:][:2]
if not bpy.data.filepath:
    bpy.ops.wm.read_factory_settings(use_empty=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with open(script, encoding="utf-8") as f:
    exec(compile(f.read(), script, "exec"), {"__name__": "__main__", "__file__": script})

name = os.path.basename(os.path.normpath(char_dir))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(char_dir, name + ".blend"))
print(f"saved {name}.blend")
