"""Run inside Blender: print the character's current state as JSON (pp.py inspect).

Pose values use the same convention as anim.py, and each key lists every animated bone, so a key can be
copied straight into an edit script.
Named info.py rather than inspect.py so it never shadows the standard library's inspect module.
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim  # noqa: E402
import rig  # noqa: E402


def r(v, n=3):
    return [round(x, n) + 0.0 for x in v]


def hex_color(lin):
    srgb = [c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in lin[:3]]
    return "#" + "".join(f"{round(min(max(c, 0), 1) * 255):02x}" for c in srgb)


def base_color(mat):
    if mat.node_tree:
        for node in mat.node_tree.nodes:
            name = {"BSDF_PRINCIPLED": "Base Color", "EMISSION": "Color"}.get(node.type)
            if name and not node.inputs[name].is_linked:
                return node.inputs[name].default_value
    return mat.diffuse_color


def describe_objects():
    out = {}
    for o in bpy.context.scene.objects:
        if o.type not in ("MESH", "ARMATURE") or o.name.startswith("pp_"):
            continue
        d = {"type": o.type.lower()}
        if o.parent:
            d["parent"] = o.parent.name + (f":{o.parent_bone}" if o.parent_type == "BONE" else "")
        if o.type == "MESH":
            d["center"] = r(o.matrix_world.translation)
            d["size"] = r(o.dimensions)
            d["materials"] = [hex_color(base_color(s.material)) for s in o.material_slots if s.material]
            d["verts"] = len(o.data.vertices)
        d.update({k: o[k] for k in o.keys() if k.startswith("pp_")})
        out[o.name] = d
    return out


def describe_bones(arm):
    return {b.name: {"head": r(b.head_local), "tail": r(b.tail_local),
                     "parent": b.parent.name if b.parent else None}
            for b in arm.data.bones}


def describe_action(arm, act):
    bones = arm.data.bones
    curves = {}
    for fc in anim.fcurves(act):
        name = fc.data_path.split('"')[1] if fc.data_path.startswith("pose.bones") else None
        if name in bones:
            curves.setdefault(name, []).append(fc)
    frames = sorted({int(round(kp.co.x)) for fcs in curves.values() for fc in fcs
                     for kp in fc.keyframe_points})
    keys = {}
    for f in frames:
        pose = {}
        for name, fcs in curves.items():
            vals = {"rotation_euler": [0.0] * 3, "location": [0.0] * 3}
            for fc in fcs:
                if fc.data_path.endswith(("rotation_euler", "location")):
                    vals[fc.data_path.rsplit(".", 1)[1]][fc.array_index] = fc.evaluate(f)
            rot, loc = rig.from_pose(bones[name], vals["rotation_euler"], vals["location"])
            entry = {"rot": r(rot, 1)}
            if any(fc.data_path.endswith("location") for fc in fcs):
                entry["loc"] = r(loc)
            pose[name] = entry
        keys[f] = dict(sorted(pose.items()))
    interps = sorted({kp.interpolation for fc in anim.fcurves(act) for kp in fc.keyframe_points})
    return {"range": [int(act.frame_range[0]), int(act.frame_range[1])],
            "loop": bool(act.get("pp_loop", False)), "interpolation": interps, "keys": keys}


def main():
    scene = bpy.context.scene
    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    out = {"file": bpy.data.filepath, "fps": scene.render.fps, "objects": describe_objects()}
    if arms:
        out["bones"] = describe_bones(arms[0])
        out["actions"] = {a.name: describe_action(arms[0], a) for a in bpy.data.actions}
    print(json.dumps(out, indent=1))


main()
