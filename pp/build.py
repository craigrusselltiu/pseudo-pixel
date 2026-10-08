"""Modelling helpers: low-poly parts, each with one flat colour and parented to one bone.

    part("torso", "box", size=(0.3, 0.36, 0.26), at=(0, 0, 0.97), bone="chest", color="#8b9bb4", bevel=0.03)
    part("helmet", "sphere", size=0.36, at=(0.03, 0, 1.32), bone="head", color="#9aa3ad")
    part("arm.L", "box", size=(0.11, 0.1, 0.32), at=(0, 0.19, 0.88), bone="upper_arm.L", color="#8b9bb4")
    mirror("arm.L")                       # arm.R on upper_arm.R, mirrored across the XZ plane

Sizes are full extents in units (x forward, y left, z up) and `at` is the part's centre, both in the
rest pose. Calling part() with an existing name replaces that part, which is how edit scripts change
one. Every part records its arguments in a `pp_part` property, which `pp.py inspect` shows.
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

import rig

SHAPES = ("box", "sphere", "dome", "cylinder", "cone", "profile")


def character():
    """The character.json of the character being built, or {} outside pp.py run."""
    path = os.path.join(os.environ.get("PP_CHAR_DIR", ""), "character.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def view():
    """(yaw, elevation) of the character's game view: its first entry in `views`, and `elevation`."""
    out = character().get("output", {})
    views = out.get("views") or [0]
    return (list(views.values()) if isinstance(views, dict) else views)[0], out.get("elevation", 0)


def material(hex_color):
    """A Principled BSDF named after its colour, shared by every part with that colour."""
    hex_color = hex_color.lower()
    mat = bpy.data.materials.get(hex_color)
    if mat:
        return mat
    mat = bpy.data.materials.new(hex_color)
    srgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb] + [1]
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = linear
    mat.diffuse_color = linear
    return mat


def _mesh(shape, segments, taper, points):
    """Unit-sized geometry centred on the origin (fits a 1 x 1 x 1 box)."""
    bm = bmesh.new()
    if shape == "box":
        bmesh.ops.create_cube(bm, size=1)
    elif shape in ("sphere", "dome"):
        bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=max(4, segments * 2 // 3), radius=0.5)
        if shape == "dome":  # upper half with a flat base, stretched to fill the unit box
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            cut = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True)
            edges = [e for e in cut["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
            bmesh.ops.contextual_create(bm, geom=edges)
            for v in bm.verts:
                v.co.z = v.co.z * 2 - 0.5
    elif shape in ("cylinder", "cone"):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=0.5,
                              radius2=0.0 if shape == "cone" else 0.5, depth=1)
    elif shape == "profile":
        # A polygon in the side-view (x, z) plane, in units around the part's centre, extruded along y.
        if not points or len(points) < 3:
            raise ValueError("profile needs at least 3 (x, z) points")
        verts = [bm.verts.new((x, -0.5, z)) for x, z in points]
        face = bm.faces.new(verts)
        ext = bmesh.ops.extrude_face_region(bm, geom=[face])
        bmesh.ops.translate(bm, vec=(0, 1, 0), verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    else:
        raise ValueError(f"unknown shape {shape!r}; use one of {SHAPES}")
    if taper != 1:
        lo = min(v.co.z for v in bm.verts)
        hi = max(v.co.z for v in bm.verts)
        for v in bm.verts:
            f = 1 + (taper - 1) * (v.co.z - lo) / ((hi - lo) or 1)  # 1 at the bottom, `taper` at the top
            v.co.x *= f
            v.co.y *= f
    return bm


def part(name, shape="box", size=(0.2, 0.2, 0.2), at=(0, 0, 0), bone="root", color="#808080",
         bevel=0.0, taper=1.0, rotate=(0, 0, 0), segments=10, points=None, smooth=0, armature=None):
    """Create (or replace) a part.

    shape: box, sphere, dome (half sphere with a flat base), cylinder (along z), cone (point up), or profile: a polygon of (x, z) points in
    units around `at`, extruded along y (blades, axes, capes, ears, coat tails, hair). It faces the
    side view unless rotated; rotate=Ref().facing turns it to face the game view.
    size: a number or (x, y, z); for a profile, a number: its thickness along y. bevel: chamfer width in
    units. taper: scale of the top relative to the bottom (1 = none). rotate: Euler degrees applied
    around the part's centre. smooth: subdivision surface levels (2 is typical) with smooth shading, which
    turns the shape into a rounded, organic version of itself (cloth, fur, limbs, boots, hats); a
    bevel keeps a smoothed box closer to its full size.
    """
    arm = rig.armature(armature)
    if bone not in arm.data.bones:
        raise KeyError(f"no bone {bone!r}; bones: {[b.name for b in arm.data.bones]}")
    size = (size, size, size) if isinstance(size, (int, float)) else tuple(size)
    if shape == "profile":
        xs, zs = [p[0] for p in points or ()], [p[1] for p in points or ()]
        scale = (1, size[1], 1)
        size = (max(xs) - min(xs), size[1], max(zs) - min(zs)) if points else size
    else:
        scale = size
    remove(name)

    mesh = bpy.data.meshes.new(name)
    bm = _mesh(shape, segments, taper, points)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = smooth > 0 or (shape in ("sphere", "dome", "cylinder", "cone") and len(poly.vertices) < 5)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material(color))
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments, mod.limit_method = bevel, 1, "ANGLE"
        mod.affect = "EDGES"
    if smooth:
        mod = obj.modifiers.new("smooth", "SUBSURF")
        mod.levels = mod.render_levels = smooth

    # Bake the size into the mesh so the bevel width stays in units and transforms stay clean.
    mesh.transform(Matrix.Diagonal(Vector(scale).to_4d()))
    rot = Euler([math.radians(a) for a in rotate], "XYZ").to_matrix().to_4x4()
    obj.parent, obj.parent_type, obj.parent_bone = arm, "BONE", bone
    pose_position, arm.data.pose_position = arm.data.pose_position, "REST"  # `at` is in the rest pose,
    bpy.context.view_layer.update()                                         # whatever action is active
    obj.matrix_world = Matrix.Translation(at) @ rot
    arm.data.pose_position = pose_position

    rnd = lambda v: [round(x, 4) for x in v]  # noqa: E731
    obj["pp_part"] = json.dumps({"shape": shape, "size": rnd(size), "at": rnd(at), "bone": bone,
                                 "color": color, "bevel": bevel, "taper": taper,
                                 "rotate": list(rotate), "segments": segments, "smooth": smooth,
                                 "points": [rnd(p) for p in points] if points else None})
    _warn_thin(name, size, rotate)
    return obj


def _warn_thin(name, size, rotate):
    ppu = character().get("output", {}).get("pixels_per_unit")
    if not ppu:
        return
    # Extents along the game view's screen right and up after rotation (an axis-aligned estimate).
    right, up, _ = rig.view_axes(*view())
    m = Euler([math.radians(a) for a in rotate], "XYZ").to_matrix()
    axes = [m.col[j] * size[j] for j in range(3)]
    visible = min(sum(abs(a.dot(d)) for a in axes) for d in (right, up))
    if visible * ppu < 1.5:
        print(f"WARNING part {name}: {visible * ppu:.2f} px thick in the game view; under 1.5 px it "
              f"flickers. Make it at least {1.5 / ppu:.3f} units.")


class Ref:
    """Measure parts off the reference image in pixels and get units back, in the reference's view.

        R = Ref()                        # from character.json: reference_scale and the game view
        R = Ref(ground=(128, 234), top=14, height=1.6, yaw=0)   # or explicitly
        R.len(42)                   -> 42 reference pixels in units
        R.pt(150, 37)               -> (u, v) screen units for that pixel: right of and above the ground point
        R.at(150, 37, depth=0.1)    -> the world point drawn at that pixel, `depth` units toward the camera
        R.box(100, 14, 158, 66)     -> (world centre, (width, height) on screen) of a pixel rectangle
        R.points(polygon, at)       -> a pixel polygon as a profile part's points around `at`
        R.facing                    -> rotate= value that turns a profile part to face the camera

    ground is the pixel under the character's origin (between the feet), top the y of its highest pixel
    and height its height in units. yaw and elevation default to the game view (see rig.view_axes), so a
    front-facing reference is measured as a front view. At yaw 0 (a side view facing right) R.at gives
    (u, 0, v) and pt/box are the plain side-view measurements.
    """

    def __init__(self, ground=None, top=None, height=None, yaw=None, elevation=None):
        cfg = character()
        m = cfg.get("reference_scale") or {}
        ground, top, height = ground or m.get("ground"), top or m.get("top"), height or m.get("height")
        if ground is None or top is None or height is None:
            raise ValueError("pass ground, top and height, or set reference_scale in character.json")
        gyaw, gelev = view()
        self.yaw = gyaw if yaw is None else yaw
        self.elevation = gelev if elevation is None else elevation
        self.right, self.up, self.toward = rig.view_axes(self.yaw, self.elevation)
        self.gx, self.gy = ground
        self.k = height / (ground[1] - top)
        self.facing = (-self.elevation, 0, self.yaw)

    def len(self, px):
        return px * self.k

    def pt(self, x, y):
        return ((x - self.gx) * self.k, (self.gy - y) * self.k)

    def at(self, x, y, depth=0.0):
        u, v = self.pt(x, y)
        return tuple(self.right * u + self.up * v + self.toward * depth)

    def box(self, x0, y0, x1, y1, depth=0.0):
        (au, av), (bu, bv) = self.pt(x0, y1), self.pt(x1, y0)
        return self.at((x0 + x1) / 2, (y0 + y1) / 2, depth), (bu - au, bv - av)

    def points(self, pts, about):
        """Reference pixel points as offsets from `about` (a part centre, in world units) along the
        screen's right and up: a profile part's points. Pass rotate=R.facing so it faces the camera."""
        au, av = Vector(about).dot(self.right), Vector(about).dot(self.up)
        return [(u - au, v - av) for u, v in (self.pt(*p) for p in pts)]


def mirror(name, armature=None):
    """Create the other side's copy of a .L/.R part: mirrored across the XZ plane, on the mirrored bone."""
    src = bpy.data.objects[name]
    p = json.loads(src["pp_part"])
    other = rig.mirror_name(name)
    if other == name:
        raise ValueError(f"{name!r} has no .L/.R suffix to mirror")
    at = (p["at"][0], -p["at"][1], p["at"][2])
    rx, ry, rz = p["rotate"]
    points = p.get("points")
    size = p["size"][1] if p["shape"] == "profile" else p["size"]
    return part(other, p["shape"], size, at, rig.mirror_name(p["bone"]), p["color"], p["bevel"],
                p["taper"], (-rx, ry, -rz), p.get("segments", 10), points, p.get("smooth", 0), armature)


def remove(name):
    obj = bpy.data.objects.get(name)
    if obj:
        mesh = obj.data if obj.type == "MESH" else None
        bpy.data.objects.remove(obj)
        if mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def recolor(name, hex_color):
    obj = bpy.data.objects[name]
    obj.data.materials.clear()
    obj.data.materials.append(material(hex_color))
    if "pp_part" in obj:
        p = json.loads(obj["pp_part"])
        p["color"] = hex_color
        obj["pp_part"] = json.dumps(p)


def parts():
    """Names of every part in the scene."""
    return [o.name for o in bpy.context.scene.objects if "pp_part" in o]


def smooth_skin(name="skin", names=None, armature=None, voxel=0.0, relax=0, faces=0, bones=None):
    """Smooth skinning: join copies of the parts into one mesh deformed by the armature with automatic
    weights, and hide the rigid originals from the render. Joints bend instead of the parts sliding
    past each other.

    With `voxel` (a size in units, about 0.02-0.03), the joined parts are fused into one continuous
    surface by a voxel remesh, like sculpting them together: seams between parts blend into a single
    game-ready mesh. `relax` smooths that surface (iterations, about 5-15) and `faces` decimates it to
    a face budget (about 8000-20000). Each new face takes the colour of the nearest original part.
    Leave small or hard details (eyes, badges, weapons) out of `names`; they stay as crisp rigid parts.
    `bones` limits which bones the skin follows (default: all deforming bones). Give each skin the bones
    of its region, or automatic weights let nearby bones pull on it (raised arms lifting a coat).

    The originals stay in the .blend for editing: change them with part(), then call smooth_skin()
    again to rebuild the skin. remove(name) and unhiding the originals undoes it.
    """
    arm = rig.armature(armature)
    srcs = [bpy.data.objects[n] for n in (names or parts())]
    remove(name)
    for o in srcs:  # hidden objects are not evaluated, so their modifiers would be skipped
        o.hide_set(False)
    pose_position = arm.data.pose_position
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    bm = bmesh.new()
    mats = []
    for o in srcs:
        mesh = bpy.data.meshes.new_from_object(o.evaluated_get(depsgraph))  # modifiers (bevels) applied
        mesh.transform(o.matrix_world)
        offset = len(mats)
        for m in mesh.materials:
            mats.append(m)
        for poly in mesh.polygons:
            poly.material_index += offset
        bm.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
    skin_mesh = bpy.data.meshes.new(name)
    bm.to_mesh(skin_mesh)
    for m in mats:
        skin_mesh.materials.append(m)
    skin = bpy.data.objects.new(name, skin_mesh)
    bpy.context.scene.collection.objects.link(skin)
    if voxel:
        skin_mesh = _fuse(skin, bm, voxel, relax, faces)
    bm.free()

    view = bpy.context.view_layer
    for o in view.objects:
        o.select_set(False)
    skin.select_set(True)
    arm.select_set(True)
    view.objects.active = arm
    deform = {b.name: b.use_deform for b in arm.data.bones}
    if bones:
        for b in arm.data.bones:
            b.use_deform = deform[b.name] and b.name in bones
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    for b in arm.data.bones:
        b.use_deform = deform[b.name]
    for o in srcs:
        o.hide_render = True
        o.hide_set(True)
    skin["pp_skin"] = json.dumps([o.name for o in srcs])
    arm.data.pose_position = pose_position
    return skin


def _fuse(obj, src, voxel, relax, faces):
    """Voxel-remesh obj into one surface, relax and decimate it, and give each face the material of the
    nearest face of `src` (the joined parts, as a bmesh)."""
    from mathutils.bvhtree import BVHTree
    mod = obj.modifiers.new("remesh", "REMESH")
    mod.mode, mod.voxel_size, mod.use_smooth_shade = "VOXEL", voxel, True
    if relax:
        mod = obj.modifiers.new("relax", "SMOOTH")
        mod.factor, mod.iterations = 0.5, relax
    if faces:
        bpy.context.view_layer.update()
        count = len(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.polygons)
        if count > faces:
            mod = obj.modifiers.new("decimate", "DECIMATE")
            mod.ratio = faces / count
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    obj.modifiers.clear()
    old, obj.data = obj.data, mesh
    if not mesh.materials:
        for m in old.materials:
            mesh.materials.append(m)
    bpy.data.meshes.remove(old)
    src.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(src)
    for poly in mesh.polygons:
        index = tree.find_nearest(poly.center)[2]
        poly.material_index = src.faces[index].material_index if index is not None else 0
        poly.use_smooth = True
    return mesh
