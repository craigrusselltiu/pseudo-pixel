"""Run inside Blender: export the rendered model, its rig and every action to <char_dir>/previews/model.glb
for the animation player (pp.py play). Never saves the .blend."""
import json
import os
import sys

import bpy

char_dir = sys.argv[sys.argv.index("--") + 1]
out = os.path.join(char_dir, "previews", "model.glb")
os.makedirs(os.path.dirname(out), exist_ok=True)
# What the sprites show: meshes that render (not the hidden low-poly guide) and the armatures they ride on
keep = {o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render}
keep |= {m.object for o in keep for m in o.modifiers if m.type == "ARMATURE" and m.object}
keep |= {o.parent for o in keep if o.parent}
for o in bpy.data.objects:
    o.hide_set(False)
    o.select_set(o in keep)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_apply=False,
                          export_yup=True)
with open(os.path.join(char_dir, "previews", "model.json"), "w", encoding="utf-8") as f:
    json.dump({"fps": bpy.context.scene.render.fps / bpy.context.scene.render.fps_base}, f)
print(f"exported {out}: {len(keep)} objects, {len(bpy.data.actions)} actions, "
      f"{bpy.context.scene.render.fps} fps timeline")
