"""Hand-written test character for the render pipeline: boxes on a small skeleton, idle + attack.

python pp.py run examples/test examples/test/build.py
"""
import math

import bpy
from mathutils import Matrix, Vector

scene = bpy.context.scene

# Armature. Character faces +X; the camera looks along +Y, so -Y is the near side.
arm = bpy.data.objects.new("rig", bpy.data.armatures.new("rig"))
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
BONES = {  # name: (head, tail, parent)
    "root": ((0, 0, 0), (0, 0, 0.2), None),
    "body": ((0, 0, 0.5), (0, 0, 1.1), "root"),
    "head": ((0, 0, 1.1), (0, 0, 1.4), "body"),
    "arm.R": ((0, -0.22, 1.0), (0, -0.22, 0.6), "body"),
}
for name, (head, tail, parent) in BONES.items():
    b = arm.data.edit_bones.new(name)
    b.head, b.tail = head, tail
    if parent:
        b.parent = arm.data.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")
for pb in arm.pose.bones:
    pb.rotation_mode = "XYZ"


def material(hex_color):
    """A plain Principled BSDF; render.py reads its base colour and swaps in toon shading."""
    mat = bpy.data.materials.get(hex_color)
    if mat:
        return mat
    mat = bpy.data.materials.new(hex_color)
    srgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = linear + [1]
    mat.diffuse_color = linear + [1]
    return mat


def box(name, size, at, bone, color, shape="cube"):
    if shape == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=12, ring_count=8)
    else:
        bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material(color))
    world = Matrix.Translation(at) @ Matrix.Diagonal(Vector(size).to_4d())
    obj.parent, obj.parent_type, obj.parent_bone = arm, "BONE", bone
    bpy.context.view_layer.update()
    obj.matrix_world = world


box("leg.L", (0.14, 0.12, 0.5), (0.05, 0.1, 0.25), "root", "#3b3f58")
box("leg.R", (0.14, 0.12, 0.5), (-0.05, -0.1, 0.25), "root", "#4b5070")
box("torso", (0.32, 0.36, 0.6), (0, 0, 0.8), "body", "#5a6b8c")
box("helmet", (0.34, 0.34, 0.34), (0.02, 0, 1.25), "head", "#9aa3ad", shape="sphere")
box("arm.R", (0.1, 0.1, 0.4), (0, -0.22, 0.8), "arm.R", "#7d8aa8")
box("sword", (0.06, 0.04, 0.6), (0, -0.26, 0.4), "arm.R", "#d8dee9")


def swing_axis(bone_name):
    """Local Euler index and sign for a side-view swing; positive swings forward (toward +X)."""
    local = arm.data.bones[bone_name].matrix_local.to_3x3().inverted() @ Vector((0, -1, 0))
    i = max(range(3), key=lambda k: abs(local[k]))
    return i, math.copysign(1, local[i])


def new_action(name):
    arm.animation_data_create()
    arm.animation_data.action = None
    return name


def key(frame, bone, swing=None, bob=None):
    pb = arm.pose.bones[bone]
    if swing is not None:
        i, sign = swing_axis(bone)
        pb.rotation_euler = [0, 0, 0]
        pb.rotation_euler[i] = sign * math.radians(swing)
        pb.keyframe_insert("rotation_euler", frame=frame)
    if bob is not None:
        pb.location = (0, bob, 0)  # body bone points up, so local Y is world Z
        pb.keyframe_insert("location", frame=frame)


def lunge(frame, x):
    """Root motion along +X; the root bone points up, so world X is its local X."""
    pb = arm.pose.bones["root"]
    pb.location = (x, 0, 0)
    pb.keyframe_insert("location", frame=frame)


def finish(name):
    act = arm.animation_data.action
    act.name = name
    act.use_fake_user = True


# idle: loop, a bob over 16 timeline frames (frame 16 repeats frame 0 and is dropped)
new_action("idle")
for f, y in ((0, 0), (8, -0.06), (16, 0)):
    key(f, "body", bob=y)
finish("idle")

# attack: windup, strike with a lunge, recover
new_action("attack")
for f, angle in ((0, 0), (4, -60), (10, 100), (18, 30), (22, 0)):
    key(f, "arm.R", swing=angle)
for f, x in ((0, 0), (10, 0.25), (22, 0.25)):
    lunge(f, x)
finish("attack")
