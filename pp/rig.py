"""Skeletons with a predictable axis convention: the standard humanoid, extra bones, custom rigs.

Convention (details in skills/pseudo-pixel/references/rig.md):
- The character faces +X. Its left is +Y (away from the camera) and up is +Z.
- Every bone's local Z axis points forward (+X). Bones that lie (nearly) horizontal, like feet and
  tails, point their local Z down instead. So rotating about local X is the swing seen by the side
  camera: positive X moves the bone's tip forward, or down for horizontal bones.
- Pose values are Euler XYZ in degrees. On .R bones Y and Z are mirrored, so the same numbers mean the
  same motion on both sides: positive Z swings the tip outward, away from the body.
- Locations are in world-aligned units (x forward, y left, z up), with y mirrored on .R bones so +y is
  outward on both sides. Scales are factors along the same world axes (for squash and stretch).
"""
import math

import bpy
from mathutils import Euler, Vector

HUMANOID = ("root", "hips", "spine", "chest", "neck", "head",
            "upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R",
            "thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R")


def armature(name=None):
    """The scene's armature (by name, or the only one)."""
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if name:
        arms = [o for o in arms if o.name == name]
    if len(arms) != 1:
        raise ValueError(f"expected one armature{' named ' + name if name else ''}, found {len(arms)}")
    return arms[0]


def _roll_axis(head, tail):
    d = (Vector(tail) - Vector(head)).normalized()
    for want in (Vector((1, 0, 0)), Vector((0, 0, -1))):
        z = want - d * want.dot(d)
        if z.length > 0.3:  # |d . forward| < 0.95: not horizontal
            return z.normalized()


def add_bones(arm, bones):
    """Add bones to an armature: {name: (head, tail, parent or None)}, in armature space."""
    view = bpy.context.view_layer
    prev = view.objects.active
    view.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for name, (head, tail, parent) in bones.items():
        b = eb.get(name) or eb.new(name)
        b.head, b.tail = head, tail
        b.align_roll(_roll_axis(head, tail))
        b.use_connect = False
        b.parent = eb[parent] if parent else None
    bpy.ops.object.mode_set(mode="OBJECT")
    view.objects.active = prev
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    return arm


def custom(bones, name="rig"):
    """A new armature with the given bones (see add_bones). Its first bone should be `root`."""
    arm = bpy.data.objects.new(name, bpy.data.armatures.new(name))
    bpy.context.scene.collection.objects.link(arm)
    arm.show_in_front = True
    return add_bones(arm, bones)


def humanoid(height=1.6, head=0.22, legs=0.45, arms=0.4, shoulders=0.12, hips=0.07, feet=0.1,
             name="rig"):
    """The standard humanoid skeleton, standing at the origin facing +X with arms down.

    `height` is in units; the rest are fractions of it: head height, hip height (legs), shoulder to
    wrist (arms), half shoulder width, half hip width, and foot length. Chunky, big-headed characters
    read better at low resolution, so try head=0.3 legs=0.35 for a stylised look.
    """
    H = height
    hip_z, head_z = legs * H, (1 - head) * H
    neck_z = head_z - 0.04 * H
    torso = neck_z - hip_z
    ankle_z = 0.04 * H
    knee_z = (hip_z + ankle_z) / 2
    sh_z = neck_z - 0.03 * H
    elbow_z, wrist_z = sh_z - arms * H / 2, sh_z - arms * H
    bones = {
        "root": ((0, 0, 0), (0, 0, 0.1 * H), None),
        "hips": ((0, 0, hip_z), (0, 0, hip_z + 0.2 * torso), "root"),
        "spine": ((0, 0, hip_z + 0.2 * torso), (0, 0, hip_z + 0.55 * torso), "hips"),
        "chest": ((0, 0, hip_z + 0.55 * torso), (0, 0, neck_z), "spine"),
        "neck": ((0, 0, neck_z), (0, 0, head_z), "chest"),
        "head": ((0, 0, head_z), (0, 0, H), "neck"),
    }
    for side, s in (("L", 1), ("R", -1)):
        sy, hy = s * shoulders * H, s * hips * H
        bones.update({
            f"upper_arm.{side}": ((0, sy, sh_z), (0, sy, elbow_z), "chest"),
            f"forearm.{side}": ((0, sy, elbow_z), (0, sy, wrist_z), f"upper_arm.{side}"),
            f"hand.{side}": ((0, sy, wrist_z), (0, sy, wrist_z - 0.08 * H), f"forearm.{side}"),
            f"thigh.{side}": ((0, hy, hip_z), (0, hy, knee_z), "hips"),
            f"shin.{side}": ((0, hy, knee_z), (0, hy, ankle_z), f"thigh.{side}"),
            f"foot.{side}": ((0, hy, ankle_z), (feet * H, hy, ankle_z), f"shin.{side}"),
        })
    return custom(bones, name)


def is_right(bone_name):
    return bone_name.endswith((".R", "_R", ".r", "_r"))


def mirror_name(bone_name):
    for a, b in ((".L", ".R"), ("_L", "_R"), (".l", ".r"), ("_l", "_r")):
        if bone_name.endswith(a):
            return bone_name[:-2] + b
        if bone_name.endswith(b):
            return bone_name[:-2] + a
    return bone_name


def _sides(bone_name):
    return (1, -1, -1) if is_right(bone_name) else (1, 1, 1)


def _axis_map(bone):
    """For each local axis, the world axis it lies (closest) along in the rest pose."""
    m = bone.matrix_local.to_3x3()
    return [max(range(3), key=lambda j: abs(m[j][i])) for i in range(3)]


def to_pose(bone, rot=None, loc=None, scale=None):
    """Convention values (degrees, world-aligned units and factors) -> pose-bone values
    (Euler radians, local location, local scale). Missing inputs give None."""
    sx, sy, sz = _sides(bone.name)
    euler = None
    if rot is not None:
        euler = Euler([math.radians(v) * s for v, s in zip(rot, (sx, sy, sz))], "XYZ")
    local = None
    if loc is not None:
        w = Vector((loc[0], loc[1] * (-1 if is_right(bone.name) else 1), loc[2]))
        local = bone.matrix_local.to_3x3().inverted() @ w
    local_scale = None
    if scale is not None:
        local_scale = Vector([scale[j] for j in _axis_map(bone)])
    return euler, local, local_scale


def from_pose(bone, euler, local, local_scale=(1, 1, 1)):
    """Inverse of to_pose: pose-bone values -> (degrees, world-aligned location, world-aligned scale)."""
    sx, sy, sz = _sides(bone.name)
    rot = [math.degrees(v) * s for v, s in zip(euler, (sx, sy, sz))]
    w = bone.matrix_local.to_3x3() @ Vector(local)
    loc = [w.x, w.y * (-1 if is_right(bone.name) else 1), w.z]
    scale = [1.0, 1.0, 1.0]
    for i, j in enumerate(_axis_map(bone)):
        scale[j] = local_scale[i]
    return rot, loc, scale
