"""A workspace library of reusable parts and actions, stored as JSON so it can be read and diffed.

    import library
    library.save_parts("../../library/parts/great_helm.json", ["helmet", "visor", "plume"])
    library.load_parts("../../library/parts/great_helm.json", scale=1.1)    # onto this character
    library.save_action("../../library/actions/walk.json", "walk")
    library.load_action("../../library/actions/walk.json", "march")

Parts are stored relative to their bone's head, so they land in the same place on a character with
different proportions. Actions are stored in the anim.py convention (see anim.describe) and work on any
rig with the same bone names. Paths are relative to the character folder.
"""
import json
import os

import bpy

import anim
import build
import rig


def _path(path):
    return path if os.path.isabs(path) else os.path.join(os.environ.get("PP_CHAR_DIR", "."), path)


def _write(path, data):
    path = _path(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print(f"saved {path}")


def _read(path):
    with open(_path(path), encoding="utf-8") as f:
        return json.load(f)


def save_parts(path, names, armature=None):
    """Save parts made with build.part, with their positions relative to their bones."""
    bones = rig.armature(armature).data.bones
    out = {}
    for name in names:
        p = json.loads(bpy.data.objects[name]["pp_part"])
        head = bones[p["bone"]].head_local
        p["offset"] = [round(a - h, 4) for a, h in zip(p.pop("at"), head)]
        out[name] = p
    _write(path, {"parts": out})


def load_parts(path, names=None, scale=1.0, rename=None, armature=None):
    """Add saved parts to this character on the bones of the same names. `scale` resizes them (and
    their offsets); `rename` maps saved part names to new ones."""
    bones = rig.armature(armature).data.bones
    rename = rename or {}
    made = []
    for name, p in _read(path)["parts"].items():
        if names and name not in names:
            continue
        if p["bone"] not in bones:
            print(f"WARNING part {name}: no bone {p['bone']!r} on this rig; skipped")
            continue
        head = bones[p["bone"]].head_local
        at = [h + o * scale for h, o in zip(head, p["offset"])]
        size = p["size"][1] * scale if p["shape"] == "profile" else [s * scale for s in p["size"]]
        points = [[x * scale, z * scale] for x, z in p["points"]] if p.get("points") else None
        made.append(build.part(rename.get(name, name), p["shape"], size, at, p["bone"], p["color"],
                               p["bevel"] * scale, p["taper"], p["rotate"], p.get("segments", 10), points,
                               p.get("smooth", 0)))
    return made


def save_action(path, name, armature=None):
    _write(path, {"action": name, **anim.describe(bpy.data.actions[name], rig.armature(armature))})


def load_action(path, name=None, armature=None):
    """Recreate a saved action on this character, optionally under a new name."""
    data = _read(path)
    return anim.load(name or data["action"], data, armature)
