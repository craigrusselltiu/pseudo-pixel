"""Milestone 2 test character: the standard humanoid rig with box parts and a sword on a weapon bone.

python pp.py run examples/humanoid examples/humanoid/scripts/001_build.py
"""
import bmesh
import bpy
from mathutils import Matrix, Vector

import rig

arm = rig.humanoid(height=1.6, head=0.28, legs=0.4)
hand = arm.data.bones["hand.R"].head_local
rig.add_bones(arm, {"weapon": (tuple(hand + Vector((0, 0, -0.08))), tuple(hand + Vector((0.5, 0, -0.08))),
                               "hand.R")})


def material(hex_color):
    mat = bpy.data.materials.get(hex_color) or bpy.data.materials.new(hex_color)
    srgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = linear + [1]
    mat.diffuse_color = linear + [1]
    return mat


def box(name, size, at, bone, color):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bm.to_mesh(mesh)
    bm.free()
    obj.data.materials.append(material(color))
    obj.parent, obj.parent_type, obj.parent_bone = arm, "BONE", bone
    bpy.context.view_layer.update()
    obj.matrix_world = Matrix.Translation(at) @ Matrix.Diagonal(Vector(size).to_4d())


ARMOUR, DARK, SKIN, STEEL = "#8b9bb4", "#3a4466", "#e8b796", "#c0cbdc"
box("head", (0.34, 0.32, 0.34), (0.03, 0, 1.32), "head", ARMOUR)
box("visor", (0.1, 0.26, 0.1), (0.2, 0, 1.33), "head", DARK)
box("chest", (0.3, 0.36, 0.26), (0, 0, 0.97), "chest", ARMOUR)
box("belly", (0.26, 0.3, 0.24), (0, 0, 0.76), "hips", DARK)
for side, y in (("L", 0.192), ("R", -0.192)):
    box(f"upper_arm.{side}", (0.11, 0.1, 0.32), (0, y, 0.88), f"upper_arm.{side}", ARMOUR)
    box(f"forearm.{side}", (0.1, 0.1, 0.3), (0, y, 0.56), f"forearm.{side}", ARMOUR)
    box(f"hand.{side}", (0.1, 0.1, 0.1), (0, y, 0.36), f"hand.{side}", SKIN)
    box(f"thigh.{side}", (0.14, 0.13, 0.3), (0, y * 0.58, 0.5), f"thigh.{side}", DARK)
    box(f"shin.{side}", (0.13, 0.12, 0.29), (0, y * 0.58, 0.21), f"shin.{side}", ARMOUR)
    box(f"foot.{side}", (0.22, 0.12, 0.1), (0.05, y * 0.58, 0.05), f"foot.{side}", DARK)
box("blade", (0.5, 0.03, 0.1), (0.35, -0.23, 0.32), "weapon", STEEL)
box("guard", (0.1, 0.03, 0.2), (0.08, -0.23, 0.32), "weapon", DARK)
