"""Models from references: a generated mesh taken to a PS1-style low-poly character (import_mesh, centre and
front to fit a skeleton, auto_weights and limb_weights, paint, color_faces and stripes, cut, lowpoly; see
skills/pseudo-pixel/references/generated.md), and lofted parts (loft, ring) for props and blueprint
modelling from orthographic references (front, side, rear).

character.json lists the views:

    "references": [
      {"image": "refs/front.png", "mask": "analysis/front_mask.png", "view": 90, "center": 516},
      {"image": "refs/side.png", "mask": "analysis/side_mask.png", "view": 0, "center": 528},
      {"image": "refs/rear.png", "mask": "analysis/rear_mask.png", "view": 270, "center": 512}
    ],
    "reference_scale": {"ground": 957, "top": 159, "height": 2.2}

`center` is the column of the character's centre line, `ground` the row its feet stand on, `top` its
highest row and `height` its height in units. Views: 90 front (screen right is the character's left,
+y), 0 its right side (screen right is +x, forward), 270 its back (screen right is -y).

    from model import Blueprint, loft, ring, paint
    B = Blueprint()
    lo, hi = B.span("front", z, (-0.4, 0.4))      # occupied interval along the view's screen axis
    rings = [ring((x, 0, z), (0, 1, 0), (1, 0, 0), (rf, rb, ry, ry)) for ...]
    obj = loft("head", rings, bone="head", colors={...})
"""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_point_line
from mathutils.kdtree import KDTree

import build
import rig
import sprite

AXES = {0: ((1, 0, 0), 1), 90: ((0, 1, 0), 1), 270: ((0, 1, 0), -1)}  # view -> world axis, sign


class Blueprint:
    """The character's reference views, with world <-> pixel conversion and silhouette spans."""

    def __init__(self, char_dir=None):
        self.dir = char_dir or os.environ.get("PP_CHAR_DIR", "")
        with open(os.path.join(self.dir, "character.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        s = cfg["reference_scale"]
        self.ground, self.height = s["ground"], s["height"]
        self.k = s["height"] / (s["ground"] - s["top"])
        self.views = {}
        for r in cfg["references"]:
            img = sprite.load_png(os.path.join(self.dir, r["image"]))[..., :3].astype(np.float32)
            mask = sprite.load_png(os.path.join(self.dir, r["mask"]))[..., 0] > 127
            name = os.path.splitext(os.path.basename(r["image"]))[0]
            self.views[name] = {"img": img, "mask": mask, "view": r["view"], "center": r["center"]}

    def row(self, z):
        return self.ground - z / self.k

    def col(self, name, u):
        """Column of screen coordinate u (units along the view's screen-right axis)."""
        return self.views[name]["center"] + u / self.k

    def screen(self, name, p):
        """A world point's (u, z) on a view: u along the screen-right axis."""
        axis, sign = AXES[self.views[name]["view"]]
        return sign * Vector(axis).dot(Vector(p)), p[2]

    def span(self, name, z, window, pick="center"):
        """The silhouette's occupied interval (u0, u1) at height z, within window (u0, u1) in screen
        units: the run around the window's centre (pick="center") or everything (pick="all").
        None when the row is empty there."""
        v = self.views[name]
        r = int(round(self.row(z)))
        if not 0 <= r < v["mask"].shape[0]:
            return None
        c0, c1 = (int(round(self.col(name, u))) for u in window)
        c0, c1 = max(min(c0, c1), 0), min(max(c0, c1), v["mask"].shape[1] - 1)
        line = v["mask"][r, c0:c1 + 1]
        cols = np.nonzero(line)[0]
        if not len(cols):
            return None
        if pick == "all":
            a, b = cols[0], cols[-1]
        else:
            mid = (c1 - c0) // 2
            if not line[mid]:
                mid = cols[np.argmin(np.abs(cols - mid))]
            a = b = mid
            while a > 0 and line[a - 1]:
                a -= 1
            while b < len(line) - 1 and line[b + 1]:
                b += 1
        to_u = lambda c: (c0 + c - v["center"]) * self.k  # noqa: E731
        return to_u(a), to_u(b + 1)

    def vspan(self, name, u, zwindow):
        """The silhouette's occupied height interval (z0, z1) in column u, within zwindow, around the
        window's middle: for horizontal parts such as T-pose arms."""
        v = self.views[name]
        c = int(round(self.col(name, u)))
        r0, r1 = sorted(int(round(self.row(z))) for z in zwindow)
        col = v["mask"][r0:r1 + 1, c]
        rows = np.nonzero(col)[0]
        if not len(rows):
            return None
        mid = (r1 - r0) // 2
        if not col[mid]:
            mid = rows[np.argmin(np.abs(rows - mid))]
        a = b = mid
        while a > 0 and col[a - 1]:
            a -= 1
        while b < len(col) - 1 and col[b + 1]:
            b += 1
        return self.ground_z(r0 + b + 1), self.ground_z(r0 + a)

    def ground_z(self, row):
        return (self.ground - row) * self.k

    def patch(self, name, u, z, radius=2):
        """The reference's pixels (N x 3, 0-255 RGB) inside the silhouette around screen point (u, z)."""
        v = self.views[name]
        r, c = int(round(self.row(z))), int(round(self.col(name, u)))
        h, w = v["mask"].shape
        r0, r1, c0, c1 = max(r - radius, 0), min(r + radius + 1, h), max(c - radius, 0), min(c + radius + 1, w)
        if r0 >= r1 or c0 >= c1:
            return None
        patch, m = v["img"][r0:r1, c0:c1].reshape(-1, 3), v["mask"][r0:r1, c0:c1].ravel()
        return patch[m] if m.any() else None

    def color(self, name, u, z, radius=2):
        """The reference's median colour (0-255 RGB) around screen point (u, z)."""
        v = self.views[name]
        r, c = int(round(self.row(z))), int(round(self.col(name, u)))
        h, w = v["mask"].shape
        r0, r1, c0, c1 = max(r - radius, 0), min(r + radius + 1, h), max(c - radius, 0), min(c + radius + 1, w)
        if r0 >= r1 or c0 >= c1:
            return None
        patch, m = v["img"][r0:r1, c0:c1].reshape(-1, 3), v["mask"][r0:r1, c0:c1].ravel()
        if not m.any():
            return None
        return np.median(patch[m], axis=0)


def ring(center, u, v, radii, n=24, square=2.0, point=(1.0, 1.0), arc=None):
    """A closed cross-section: n points around `center` in the plane of unit axes u and v.

    radii = (u+, u-, v+, v-): extents along +u, -u, +v, -v. square is the superellipse exponent (2 an
    ellipse, higher boxier). point = (front, back) tapers v near +u and -u: 1 is round, 2 makes the +u
    end pointy (a snout), below 1 blunter. arc=(t0, t1) in radians makes an open arc of n points
    instead (angles from +u toward +v), for shells like an open coat."""
    c, u, v = Vector(center), Vector(u).normalized(), Vector(v).normalized()
    e = 2.0 / square
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n if arc is None else arc[0] + (arc[1] - arc[0]) * i / (n - 1)
        cu, sv = math.cos(t), math.sin(t)
        ru = radii[0] if cu >= 0 else radii[1]
        rv = radii[2] if sv >= 0 else radii[3]
        p = point[0] if cu >= 0 else point[1]
        a = math.copysign(abs(cu) ** e, cu) * ru
        b = math.copysign(abs(sv) ** e, sv) * rv * (abs(sv) ** (e * (p - 1)) if p != 1 else 1)
        pts.append(c + u * a + v * b)
    return pts


def loft(name, rings, bone="root", color="#808080", cap=(True, True), smooth=1, closed=True,
         thickness=0.0, armature=None):
    """A mesh through rings of equal point counts (quads between neighbours), capped at the ends,
    with subdivision `smooth` levels and smooth shading. closed=False leaves each ring open (a
    shell such as an open coat; give it `thickness`). Parented to `bone` like build.part."""
    arm = armature or rig.armature()
    build.remove(name)
    bm = bmesh.new()
    rows = [[bm.verts.new(p) for p in r] for r in rings]
    n = len(rings[0])
    for a, b in zip(rows[:-1], rows[1:]):
        for i in range(n if closed else n - 1):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    for end, row in ((cap[0], rows[0]), (cap[1], rows[-1])):
        if end and closed:
            centre = bm.verts.new(sum((v.co for v in row), Vector()) / n)
            for i in range(n):
                bm.faces.new((row[i], row[(i + 1) % n], centre))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(build.material(color))
    if thickness:
        mod = obj.modifiers.new("solidify", "SOLIDIFY")
        mod.thickness, mod.offset = thickness, 0
    if smooth:
        mod = obj.modifiers.new("smooth", "SUBSURF")
        mod.levels = mod.render_levels = smooth
    world = obj.matrix_world.copy()
    obj.parent, obj.parent_type, obj.parent_bone = arm, "BONE", bone
    pose_position, arm.data.pose_position = arm.data.pose_position, "REST"  # placed in the rest pose,
    bpy.context.view_layer.update()                                         # whatever action is active
    obj.matrix_world = world
    arm.data.pose_position = pose_position
    obj["pp_model"] = json.dumps({"bone": bone})
    return obj


def flatten(image, mask, palette, out, radius=4, shades=None):
    """Flatten a reference into palette colours before painting from it: every pixel inside the mask
    takes its nearest palette colour, then the colour most common within `radius` pixels, so the
    artist's shading pixels and outlines melt into the flat area they sit in (a shirt's shadow pixels
    no longer read as the coat). shades: {palette name: [hex, ...]}, the artist's shading tones of a
    colour that sit nearer another one (a vest's shadow tan nearer the leather): they count as that
    colour. Paths are relative to the character folder; writes `out` and returns its path, for the
    reference's "image" in character.json."""
    d = os.environ.get("PP_CHAR_DIR", "")
    img = sprite.load_png(os.path.join(d, image))
    inside = sprite.load_png(os.path.join(d, mask))[..., 0] > 127
    hexes = list(palette.values())
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]  # noqa: E731
    pal = np.array([rgb(h) for h in hexes], float)
    match = [rgb(h) for h in hexes]
    owner = list(range(len(hexes)))
    for name, tones in (shades or {}).items():
        match += [rgb(h) for h in tones]
        owner += [list(palette).index(name)] * len(tones)
    lab = _lab(img[..., :3].astype(float))
    dist = ((lab[..., None, :] - _lab(np.array(match, float))[None, None]) ** 2).sum(-1)
    label = np.array(owner)[dist.argmin(-1)]
    size = 2 * radius + 1
    votes = []
    for k in range(len(hexes)):  # box-sum of each colour's pixels around every pixel
        m = np.pad(((label == k) & inside).astype(np.int32), radius)
        c = m.cumsum(0).cumsum(1)
        c = np.pad(c, ((1, 0), (1, 0)))
        votes.append(c[size:, size:] - c[:-size, size:] - c[size:, :-size] + c[:-size, :-size])
    flat = pal[np.argmax(votes, axis=0)]
    rgba = np.zeros_like(img)
    rgba[..., :3] = np.where(inside[..., None], flat, 255)
    rgba[..., 3] = 255
    sprite.save_png(os.path.join(d, out), rgba)
    return out


def color_faces(obj, rule):
    """Colour a mesh polygon by polygon, as low-poly characters were (PS1 models coloured their
    polygons instead of texturing them: a pupil is one quad). rule(center, normal) returns a hex
    colour for each face, from its centre and normal in world space at rest, or None to keep its colour:
    the way to touch up what paint guessed for the sides no reference shows (the back of a head below a
    hat brim is fur: `lambda c, n: "#c0521e" if n.x < -0.2 and BRIM_UNDER < c.z < BRIM else None`)."""
    world = obj.matrix_world
    nmat = world.to_3x3().inverted().transposed()
    mesh = obj.data
    slots = {m.name: i for i, m in enumerate(mesh.materials)}
    for p in mesh.polygons:
        color = rule(world @ p.center, (nmat @ p.normal).normalized())
        if color is None:
            continue
        if color not in slots:
            mesh.materials.append(build.material(color))
            slots[color] = len(mesh.materials) - 1
        p.material_index = slots[color]


def apply_modifiers(obj):
    """Bake obj's modifiers (subdivision, thickness) into its mesh, so it can be painted finely."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    old, obj.data = obj.data, mesh
    obj.modifiers.clear()
    if not mesh.materials:
        for m in old.materials:
            mesh.materials.append(m)
    bpy.data.meshes.remove(old)
    for p in mesh.polygons:
        p.use_smooth = True
    return mesh


def smooth_normals(obj, iterations=30):
    """Shade obj with the normals of a smoothed copy of itself, as Guilty Gear Xrd edits normals for clean
    cel shading: the shape stays, but the toon bands follow its broad forms instead of every lump of a
    generated or sculpted surface, so they read as clean shapes and don't crawl as it moves. Stored as
    custom normals, which follow the skin; works before or after rigging."""
    scene = bpy.context.scene
    proxy = bpy.data.objects.new(obj.name + "_smooth", obj.data.copy())
    scene.collection.objects.link(proxy)
    proxy.matrix_world = obj.matrix_world
    smooth = proxy.modifiers.new("smooth", "SMOOTH")
    smooth.factor, smooth.iterations = 1.0, iterations
    apply_modifiers(proxy)
    states = [(m, m.show_viewport) for m in obj.modifiers]
    for m, _ in states:
        m.show_viewport = False
    dt = obj.modifiers.new("normals", "DATA_TRANSFER")
    dt.object, dt.use_loop_data, dt.data_types_loops = proxy, True, {"CUSTOM_NORMAL"}
    dt.loop_mapping = "POLYINTERP_NEAREST"
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True,
                                           depsgraph=depsgraph)
    obj.modifiers.remove(dt)
    for m, shown in states:
        m.show_viewport = shown
    old, obj.data = obj.data, mesh
    bpy.data.meshes.remove(old)
    mesh_proxy = proxy.data
    bpy.data.objects.remove(proxy)
    bpy.data.meshes.remove(mesh_proxy)


def auto_weights(obj, arm, voxel=0.02):
    """Skin obj to arm with automatic (bone heat) weights. Heat weighting fails on surfaces that aren't
    watertight, which generated meshes often aren't, and at character scale (a 2-unit figure) it can
    fail outright, leaving every vertex unweighted. So the weights are computed on a voxel-remeshed
    (watertight) copy scaled up 10x, and transferred back to obj by nearest surface. Returns the number
    of vertices still unweighted."""
    view = bpy.context.view_layer
    proxy = bpy.data.objects.new(obj.name + "_skin", obj.data.copy())
    bpy.context.scene.collection.objects.link(proxy)
    proxy.matrix_world = obj.matrix_world
    bm = bmesh.new()  # close the surface's holes first (a part cut away), or the remesh stays open
    bm.from_mesh(proxy.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bm.to_mesh(proxy.data)
    bm.free()
    remesh = proxy.modifiers.new("remesh", "REMESH")
    remesh.mode, remesh.voxel_size = "VOXEL", voxel
    apply_modifiers(proxy)
    proxy.vertex_groups.clear()
    pose_position, arm.data.pose_position = arm.data.pose_position, "REST"  # weights from the rest pose:
    ad = arm.animation_data                                                  # heat weighting fails while an
    action, slot = (ad.action, ad.action_slot) if ad else (None, None)       # action is attached
    if ad:
        ad.action = None
    arm_world = arm.matrix_world.copy()
    proxy.matrix_world = Matrix.Scale(10, 4) @ obj.matrix_world
    arm.matrix_world = Matrix.Scale(10, 4) @ arm_world
    view.update()
    for o in view.objects:
        o.select_set(False)
    proxy.select_set(True)
    arm.select_set(True)
    view.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    arm.matrix_world = arm_world
    arm.data.pose_position = pose_position
    if ad:
        ad.action = action
        if slot is not None and ad.action_slot is None:
            ad.action_slot = slot
    proxy.parent = None
    proxy.matrix_world = obj.matrix_world
    view.update()
    obj.vertex_groups.clear()
    for g in proxy.vertex_groups:
        obj.vertex_groups.new(name=g.name)
    dt = obj.modifiers.new("weights", "DATA_TRANSFER")
    dt.object, dt.use_vert_data, dt.data_types_verts = proxy, True, {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src, dt.layers_vgroup_select_dst = "ALL", "NAME"
    view.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=dt.name)
    mesh = proxy.data
    bpy.data.objects.remove(proxy)
    bpy.data.meshes.remove(mesh)
    world = obj.matrix_world.copy()
    obj.parent = arm
    obj.matrix_world = world
    mod = obj.modifiers.new("armature", "ARMATURE")
    mod.object = arm
    return sum(1 for v in obj.data.vertices if not any(g.weight > 0.001 for g in v.groups))


def paint(obj, B, palette, views=None, radius=2, mirror_side=True, bake=True, clean=2, regions=None, facing=0.3,
          no_fill=None, wrap=0.35):
    """Give every face of obj the palette colour nearest to what the references show there.

    palette: {name: hex}, a few flat colours for this mesh (shading comes from the toon shader, so
    leave the reference's shades out). Each face is looked up in the view it faces most (front, rear,
    or side; a face on the left side reads the right-side view at the same x and z when mirror_side),
    but only in a view that can see it: a face hidden behind another part from that camera (a tail
    behind the legs) would get the colour of whatever hides it, so that view is skipped. A face no view
    sees takes the colour of the nearest painted face (of its region) that the views see edge-on, at a
    score under `wrap`: the colour that wraps around from the silhouette's edge, as an artist paints the
    back of a figure from its sides (the back of a head takes its sides' fur, not the face's cream; the
    back of a coat its sides' brown, not the shirt). Whatever is left fills from painted neighbours,
    ring by ring; wrap=0 fills everything that way. views limits the views used, e.g. ["side"] for a tail drawn fully in
    the side view. bake applies the modifiers first so the colour regions follow the subdivided
    surface (pass bake=False on a rigged mesh); clean passes of a majority filter over neighbouring
    faces remove single-face speckles. no_fill: palette names of small features (eyes, nose, a badge)
    that faces no view sees never take from their neighbours, so a dark outline caught on one face
    can't flood the back of a head. facing: how squarely (0-1) a face must point at a view's camera to
    be painted from it; lower it to paint grazing faces (a hat's crown from the front).

    regions (on a skinned mesh): {bone name or prefix: [palette names]}. A face whose bone matches (the
    bone most of its vertices are weighted to, unless the face looks toward it: see _face_bones) may only
    take those colours, and when no view sees it, it is filled only from faces of the same region. Projection can't tell a tail from the trousers in front
    of it; the skin weights can: {"tail.": ["fur", "fur_dark", "cream"]}. A region can also limit the
    views that paint it, {"head": {"colors": [...], "views": ["front"]}}: a generated mesh lines up
    with the image it was generated from, and other sheets drawn separately can land on the wrong
    part (an ear drawn over the hat in the side view)."""
    if bake:
        apply_modifiers(obj)
    names = {v["view"]: k for k, v in B.views.items()}
    mats = []
    for key, hex_color in palette.items():
        mats.append((build.material(hex_color), np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], float)))
    mesh = obj.data
    mesh.materials.clear()
    for m, _ in mats:
        mesh.materials.append(m)
    world = obj.matrix_world
    nmat = world.to_3x3().inverted().transposed()
    allowed = set(views) if views else set(B.views)
    lab = lambda c: _lab(c)  # noqa: E731
    pal_lab = np.array([lab(c) for _, c in mats])
    region = _regions(obj, regions or {})
    every = np.arange(len(mats))
    spec = {r: v if isinstance(v, dict) else {"colors": v} for r, v in (regions or {}).items()}
    allowed_idx = {r: np.array([list(palette).index(n) for n in v["colors"]]) for r, v in spec.items()}
    region_views = {r: set(v["views"]) for r, v in spec.items() if "views" in v}
    bvh = BVHTree.FromPolygons([world @ v.co for v in mesh.vertices], [p.vertices for p in mesh.polygons])
    toward = {90: Vector((1, 0, 0)), 270: Vector((-1, 0, 0)), 0: Vector((0, -1, 0))}  # to each camera
    seen = [0.0] * len(mesh.polygons)
    for poly in mesh.polygons:
        p = world @ poly.center
        n = (nmat @ poly.normal).normalized()
        scores = []
        for view, name in names.items():
            if name not in allowed:
                continue
            if view == 90:
                s = n.x
            elif view == 270:
                s = -n.x
            else:
                s = abs(n.y) if mirror_side else -n.y
            scores.append((s, name))
        scores.sort(reverse=True)
        seen[poly.index] = scores[0][0]
        if scores[0][0] < facing:  # faces up or down: no sheet shows it; filled from neighbours below
            poly.material_index = len(mats)
            continue
        col = None
        for score, name in scores:
            if score < facing:
                break
            if name not in region_views.get(region[poly.index], allowed):
                continue
            view = B.views[name]["view"]
            d = Vector((0, 1 if n.y > 0 else -1, 0)) if view == 0 and mirror_side else toward[view]
            if bvh.ray_cast(p + d * 0.004, d)[0] is not None:
                continue  # hidden behind another part from this camera
            u, z = B.screen(name, p)
            col = B.patch(name, u, z, radius)
            if col is not None:
                break
        if col is None:
            poly.material_index = len(mats)
            continue
        # Every pixel of the patch votes for its nearest allowed colour: a 1 px outline or a stray
        # shading pixel loses to the colour it sits in.
        idx = allowed_idx.get(region[poly.index], every)
        d = ((lab(col)[:, None, :] - pal_lab[idx][None]) ** 2).sum(-1)
        poly.material_index = int(idx[np.bincount(d.argmin(1), minlength=len(idx)).argmax()])
    banned = {list(palette).index(n) for n in no_fill or ()}
    if wrap:
        _wrap(mesh, world, len(mats), region, seen, wrap, banned)
    _fill(mesh, len(mats), region, banned)
    if clean:
        _majority(mesh, clean, region)


def _wrap(mesh, world, unset, region, score, rim, banned):
    """Give each unset face the commonest colour among the 8 nearest painted faces of its region seen
    edge-on (score under rim)."""
    edge = {}
    for p in mesh.polygons:
        if p.material_index != unset and score[p.index] < rim and p.material_index not in banned:
            edge.setdefault(region[p.index], []).append(p.index)
    trees = {}
    for r, ids in edge.items():
        trees[r] = KDTree(len(ids))
        for i in ids:
            trees[r].insert(world @ mesh.polygons[i].center, i)
        trees[r].balance()
    labels = [p.material_index for p in mesh.polygons]
    for p in mesh.polygons:
        if labels[p.index] == unset and region[p.index] in trees:
            votes = {}
            for _, i, _ in trees[region[p.index]].find_n(world @ p.center, 8):
                votes[labels[i]] = votes.get(labels[i], 0) + 1
            p.material_index = max(votes, key=votes.get)


def _neighbours(mesh):
    edge_faces = {}
    for poly in mesh.polygons:
        for key in poly.edge_keys:
            edge_faces.setdefault(key, []).append(poly.index)
    nb = [set() for _ in mesh.polygons]
    for faces in edge_faces.values():
        for f in faces:
            nb[f].update(faces)
    return nb


def _face_bones(obj):
    """Each face's bone: the one most of its vertices are weighted to, unless the face looks toward that
    bone (it is another part's surface pressed against that limb: the back of a coat under a tail, the
    side of a coat under an arm, which automatic weights give to the limb); then the nearest bone it looks
    away from. None for faces without weights."""
    names = {g.index: g.name for g in obj.vertex_groups}
    vert = [names.get(max(v.groups, key=lambda g: g.weight).group) if len(v.groups) else None
            for v in obj.data.vertices]
    arm = next((m.object for m in obj.modifiers if m.type == "ARMATURE" and m.object), None)
    segs = {b.name: (b.head_local, b.tail_local) for b in arm.data.bones if b.use_deform} if arm else {}
    m = arm.matrix_world.inverted() @ obj.matrix_world if arm else Matrix()
    m3 = m.to_3x3().inverted().transposed()

    def away(c, n, bone):
        q, t = intersect_point_line(c, *segs[bone])
        a, b = segs[bone]
        q = a + (b - a) * min(max(t, 0.0), 1.0)
        return n.dot((c - q).normalized()), (c - q).length

    out = []
    for p in obj.data.polygons:
        counts = {}
        for i in p.vertices:
            counts[vert[i]] = counts.get(vert[i], 0) + 1
        bone = max(counts, key=counts.get)
        if bone in segs:
            c, n = m @ p.center, (m3 @ p.normal).normalized()
            if away(c, n, bone)[0] < -0.2:
                near = sorted(segs, key=lambda b: away(c, n, b)[1])
                bone = next((b for b in near if away(c, n, b)[0] >= 0), bone)
        out.append(bone)
    return out


def _regions(obj, regions):
    """Each face's region: the key of `regions` that its bone (_face_bones) starts with, or None."""
    return [next((r for r in regions if b and b.startswith(r)), None) for b in _face_bones(obj)]


def _fill(mesh, unset, region=None, banned=()):
    """Give faces marked `unset` the most common material of their painted neighbours (of the same
    region, when regions are given), growing inward."""
    region = region or [None] * len(mesh.polygons)
    nb = _neighbours(mesh)
    labels = [p.material_index for p in mesh.polygons]
    todo = [i for i, x in enumerate(labels) if x == unset]
    while todo:
        left, ring = [], {}
        for i in todo:  # one ring at a time, from the labels before it, so no side floods the rest
            counts = {}
            for j in nb[i]:
                if labels[j] != unset and region[j] == region[i] and labels[j] not in banned:
                    counts[labels[j]] = counts.get(labels[j], 0) + 1
            if counts:
                ring[i] = max(counts, key=counts.get)
            else:
                left.append(i)
        for i, label in ring.items():
            labels[i] = label
        if len(left) == len(todo):
            if any(region[i] is not None for i in left):  # a region no view sees: fill across regions
                region = [None] * len(region)
                continue
            for i in left:
                labels[i] = 0
            break
        todo = left
    for poly, label in zip(mesh.polygons, labels):
        poly.material_index = label


def _majority(mesh, passes, region=None):
    """Each face takes the most common material among itself and its edge neighbours (of its region)."""
    region = region or [None] * len(mesh.polygons)
    neighbours = _neighbours(mesh)
    labels = [p.material_index for p in mesh.polygons]
    for _ in range(passes):
        new = []
        for i, nb in enumerate(neighbours):
            counts = {}
            for j in nb:
                if region[j] == region[i]:
                    counts[labels[j]] = counts.get(labels[j], 0) + 1
            best = max(counts, key=counts.get)
            new.append(best if counts[best] > counts.get(labels[i], 0) else labels[i])
        labels = new
    for poly, label in zip(mesh.polygons, labels):
        poly.material_index = label


def _lab(rgb):
    """sRGB 0-255 -> CIE Lab, for perceptual nearest-colour matching."""
    c = np.asarray(rgb, float) / 255  # (..., 3)
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = (c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
           / np.array([0.9505, 1.0, 1.089]))
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=-1)


def import_mesh(path, name="body", turn=90.0, height=None, faces=0, min_piece=0.001):
    """Import a generated or modelled mesh (GLB, FBX or OBJ) as one object: joined, turned `turn` degrees
    about z so it faces +x (a glTF model facing the viewer faces -y in Blender: 90), scaled to `height`,
    decimated to about `faces` faces, loose fragments under `min_piece` of its vertices dropped (crumbs a
    pixel across, or the bits of a prop that float free when an arm moves), smooth shaded, and standing on
    the ground with the point between its feet on the origin (not its bounding box's centre, which a tail
    or a weapon pulls aside): the sprites turn on that point."""
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        bpy.ops.wm.obj_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    bm = bmesh.new()
    for o in meshes:
        m = o.data.copy()
        m.transform(o.matrix_world)
        bm.from_mesh(m)
        bpy.data.meshes.remove(m)
    for o in new:
        bpy.data.objects.remove(o)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(turn), 3, "Z"))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # generators don't always wind faces outward
    lo = min(v.co.z for v in bm.verts)
    hi = max(v.co.z for v in bm.verts)
    k = height / (hi - lo) if height else 1.0
    for v in bm.verts:
        v.co *= k
    build.remove(name)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    if faces and len(mesh.polygons) > faces:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.ratio = faces / len(mesh.polygons)
        apply_modifiers(obj)
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    seen, drop = set(), []
    for v in bm.verts:
        if v in seen:
            continue
        stack, piece = [v], []
        seen.add(v)
        while stack:
            x = stack.pop()
            piece.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        if len(piece) < min_piece * len(bm.verts):
            drop += piece
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    co = np.array([v.co[:] for v in bm.verts])
    lo = co[:, 2].min()
    feet = co[co[:, 2] < lo + 0.03 * (co[:, 2].max() - lo)]
    shift = Vector((-feet[:, 0].mean(), -feet[:, 1].mean(), -lo))
    bmesh.ops.translate(bm, verts=bm.verts, vec=shift)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    print(f"imported {name}: {len(mesh.polygons)} faces, {len(drop)} fragment vertices dropped")
    return obj


def _co(obj):
    """obj's vertices at rest, in world space, as an N x 3 array."""
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    m = np.array(obj.matrix_world)
    return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


def centre(obj, point, normal=(0, 0, 1), slab=0.03, radius=0.3):
    """The middle of obj's cross-section through `point`: the centre of the extents of its vertices
    within `slab` of the plane through `point` across `normal`, and within `radius` of `point` in that
    plane (so an arm or a tail beside the body stays out). Place joints with it: a spine joint is the
    middle of the body at that height (normal up), an elbow the middle of the sleeve across the arm
    (normal along the arm). Joints at the mesh's mean depth zigzag the spine; joints at a guessed
    position end up inside the coat instead of the sleeve."""
    p, n = np.array(point, float), np.array(normal, float) / np.linalg.norm(normal)
    co = _co(obj)
    near = co[np.abs((co - p) @ n) < slab]
    off = near - p - np.outer((near - p) @ n, n)
    near = near[np.linalg.norm(off, axis=1) < radius]
    if not len(near):
        return Vector(point)
    mid = (near.min(0) + near.max(0)) / 2
    return Vector(mid - ((mid - p) @ n) * n)


def front(obj, y, z, r=0.03):
    """The x of obj's surface nearest the front camera at (y, z): the depth a front reference shows
    there. A joint picked on the reference lies about half the limb's thickness behind it."""
    co = _co(obj)
    near = co[np.hypot(co[:, 1] - y, co[:, 2] - z) < r]
    return float(near[:, 0].max()) if len(near) else 0.0


def _majority_material(f):
    mats = {}
    for e in f.edges:
        for g in e.link_faces:
            if g is not f:
                mats[g.material_index] = mats.get(g.material_index, 0) + 1
    return max(mats, key=mats.get) if mats else 0


def cut(obj, rule):
    """Delete obj's faces where rule(center, normal, color) is true (world space at rest; color is the
    face's material name, its hex colour) and close the holes. For a prop fused into a generated mesh
    (a gun below a paw): cut it out, then model a crisp low-poly one on its own bone. Returns the number
    of faces cut."""
    world = obj.matrix_world
    nmat = world.to_3x3().inverted().transposed()
    names = [m.name for m in obj.data.materials]
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    drop = [f for f in bm.faces if rule(world @ f.calc_center_median(), (nmat @ f.normal).normalized(),
                                       names[f.material_index] if names else None)]
    edges = {e for f in drop for e in f.edges}
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    new = bmesh.ops.holes_fill(bm, edges=[e for e in edges if e.is_valid and e.is_boundary], sides=0)["faces"]
    for f in new:
        f.material_index = _majority_material(f)
    bmesh.ops.triangulate(bm, faces=new)
    bm.to_mesh(obj.data)
    bm.free()
    return len(drop)


def stripes(obj, bones, color, count, share=0.45, start=0.2, end=0.95, base=None):
    """Paint `count` rings of `color` around the part on `bones` (a tail's markings), when the reference
    draws them too faintly for paint to pick up: the faces on those bones (_face_bones), measured along
    the chain from its root (0) to its tip (1), with rings evenly spaced between `start` and `end`, each
    `share` of its spacing wide. base: a colour for the faces between the rings (default: keep theirs)."""
    arm = rig.armature()
    segs = _segments(arm, bones)
    lengths = np.cumsum([0] + [(b - a).length for _, a, b in segs])
    owner = _face_bones(obj)
    slots = {}
    for c in [color] + ([base] if base else []):
        if c.lower() not in [m.name for m in obj.data.materials]:
            obj.data.materials.append(build.material(c))
        slots[c] = [m.name for m in obj.data.materials].index(c.lower())
    painted = 0
    for p in obj.data.polygons:
        if owner[p.index] not in bones:
            continue
        _, _, _, t, k = _nearest_on(p.center, segs)
        s = (lengths[k] + t * (lengths[k + 1] - lengths[k])) / lengths[-1]
        if start <= s <= end:
            phase = ((s - start) / (end - start) * count) % 1.0
            if (1 - share) / 2 <= phase < (1 + share) / 2:
                p.material_index = slots[color]
                painted += 1
                continue
        if base:
            p.material_index = slots[base]
    print(f"stripes: {painted} faces in {count} rings of {color}")


def _segments(arm, chain):
    """[(bone name, head, tail)] of a bone chain at rest, in armature space."""
    return [(n, arm.data.bones[n].head_local.copy(), arm.data.bones[n].tail_local.copy()) for n in chain]


def _nearest_on(co, segs):
    """(distance, name, closest point, t along the segment, index) from co to a chain of segments."""
    best = None
    for i, (name, a, b) in enumerate(segs):
        q, t = intersect_point_line(co, a, b)
        t = min(max(t, 0.0), 1.0)
        q = a + (b - a) * t
        d = (co - q).length
        if best is None or d < best[0]:
            best = (d, name, q, t, i)
    return best


def limb_weights(obj, arm, limbs, radius=0.16, blend=0.05):
    """Free limbs that a generated mesh fused to the body, and weight each to its own bones only.

    A generated character's arms hang against its coat and its tail lies against the coat's back, all one
    surface, so automatic weights tie coat to the arms (raising an arm tears shards out of the coat), the
    coat's back to the tail bones, and paws to the spine. limbs: bone chains, each a list of bones or a
    (bones, radius) pair, e.g. [["upper_arm.R", "forearm.R", "hand.R"], ["upper_arm.L", "forearm.L",
    "hand.L"], (["tail.1", "tail.2", "tail.3"], 0.35)], whose bones run down the middle of each limb
    (place them with `centre`). A vertex is limb when it lies within the limb's radius of its chain and
    faces away from it, or within half that (coat touching the limb faces toward it). Further than the
    radius from the chain's root (below the armpit), the faces bridging limb and body are cut and each
    side is closed on its own. Limb vertices are weighted along their chain, blending over `blend` at each
    joint and into the chain's parent bone at the root; other vertices lose their limb weights. Run after
    auto_weights and before paint (which reads the weights' regions)."""
    mesh = obj.data
    limbs = [(c, radius) if isinstance(c[0], str) else c for c in limbs]
    radii = [r for _, r in limbs]
    limbs = [c for c, _ in limbs]
    chains = [_segments(arm, c) for c in limbs]
    tops = [arm.data.bones[c[0]].parent.name for c in limbs]
    roots = [segs[0][1] for segs in chains]
    side_of, near = {}, {}
    for v in mesh.vertices:
        for k, segs in enumerate(chains):
            d, name, q, t, i = _nearest_on(v.co, segs)
            if d >= radii[k] or (i == 0 and t < 0.15):
                continue  # the shoulder cap stays with the body
            near[v.index] = k
            if d < radii[k] / 2 or v.normal.dot((v.co - q).normalized()) > 0.0:
                side_of[v.index] = k
    links = {i: [] for i in near}  # a generated surface is noisy: settle each vertex to its neighbours' side
    for e in mesh.edges:
        a, b = e.vertices
        if a in links:
            links[a].append(b)
        if b in links:
            links[b].append(a)
    for _ in range(3):
        vote = {}
        for i, k in near.items():
            n = [side_of.get(j) for j in links[i]] + [side_of.get(i)]
            vote[i] = k if n.count(k) * 2 > len(n) else None
        for i, k in vote.items():
            if k is None:
                side_of.pop(i, None)
            else:
                side_of[i] = k

    # Cut the faces bridging a limb and the body below the armpit; close each side's part of every hole
    bm = bmesh.new()
    bm.from_mesh(mesh)
    layer = bm.verts.layers.int.new("pp_limb")
    for v in bm.verts:
        v[layer] = side_of.get(v.index, -1) + 1
    bridge = [f for f in bm.faces if len({v[layer] for v in f.verts}) > 1
              and all(min((v.co - roots[k]).length for v in f.verts) > radii[k]
                      for k in {v[layer] - 1 for v in f.verts if v[layer]})]
    bmesh.ops.delete(bm, geom=bridge, context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    boundary = {e for e in bm.edges if e.is_boundary}
    new = []
    while boundary:
        e = boundary.pop()
        loop, v = [e.verts[0]], e.verts[1]
        while v is not loop[0]:
            loop.append(v)
            nxt = [x for x in v.link_edges if x in boundary]
            if not nxt:
                break
            boundary.discard(nxt[0])
            v = nxt[0].other_vert(v)
        runs = []  # maximal runs of one side around the loop
        for v in loop:
            if runs and runs[-1][0] == v[layer]:
                runs[-1][1].append(v)
            else:
                runs.append((v[layer], [v]))
        if len(runs) > 1 and runs[0][0] == runs[-1][0]:
            runs[0] = (runs[0][0], runs.pop()[1] + runs[0][1])
        for _, vs in runs:
            if len(vs) >= 3 and len(set(vs)) == len(vs):
                try:
                    new.append(bm.faces.new(vs))
                except ValueError:
                    pass
    for f in new:
        f.material_index = _majority_material(f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=new)
    bm.to_mesh(mesh)
    bm.free()
    attr = mesh.attributes["pp_limb"]
    side_of = {i: a.value - 1 for i, a in enumerate(attr.data) if a.value}
    mesh.attributes.remove(attr)

    # Weights: limb vertices along their own chain, everything else off the limbs
    limb_bones = {n for c in limbs for n in c}
    body_bones = [(b.name, b.head_local, b.tail_local) for b in arm.data.bones
                  if b.use_deform and b.name not in limb_bones]
    for n in limb_bones | {b[0] for b in body_bones}:
        if n not in obj.vertex_groups:
            obj.vertex_groups.new(name=n)
    groups = {g.name: g for g in obj.vertex_groups}
    names = {g.index: g.name for g in obj.vertex_groups}
    for v in mesh.vertices:
        k = side_of.get(v.index)
        ws = {names[g.group]: g.weight for g in v.groups}
        if k is None:
            keep = {n: x for n, x in ws.items() if n not in limb_bones and x > 0}
            if keep == ws:
                continue
            if not keep:
                keep = {_nearest_on(v.co, body_bones)[1]: 1.0}
        else:
            segs = chains[k]
            d, name, q, t, i = _nearest_on(v.co, segs)
            length = (segs[i][2] - segs[i][1]).length
            keep = {name: 1.0}
            if t * length < blend and i > 0:  # near the joint above
                f = 0.5 + 0.5 * t * length / blend
                keep = {name: f, segs[i - 1][0]: 1 - f}
            elif (1 - t) * length < blend and i < len(segs) - 1:  # near the joint below
                f = 0.5 + 0.5 * (1 - t) * length / blend
                keep = {name: f, segs[i + 1][0]: 1 - f}
            r = (v.co - roots[k]).length
            if i == 0 and r < radii[k]:  # the root of the limb eases into the body
                f = 1 - r / radii[k]
                keep = {n: x * (1 - f) for n, x in keep.items()}
                keep[tops[k]] = keep.get(tops[k], 0) + f
        total = sum(keep.values())
        for n in ws:
            groups[n].remove([v.index])
        for n, x in keep.items():
            groups[n].add([v.index], x / total, "REPLACE")
    print(f"limb_weights: {len(bridge)} bridging faces cut, {len(new)} patches, {len(side_of)} limb vertices")


def _tube(name, guide, arm, bones, sides=8, slices=40, max_band=0.2):
    """A low-poly tube rebuilt over a generated tail (or any long round part) on `bones`: `sides`-sided
    rings fitted to the guide's surface along the tail's centreline, with a ring on every colour boundary,
    so each stripe is its own band of polygons. Returns (the tube object, the guide faces it replaces)."""
    gm = guide.data
    owner = _face_bones(guide)
    tail_faces = [p.index for p in gm.polygons if owner[p.index] in bones]
    if len(tail_faces) < 20:
        raise ValueError(f"lowpoly tube {name}: almost no faces weighted to {bones}")

    # The centreline: the middle of the tail's vertices in slices along its bone chain (the bones
    # themselves rarely run down its middle)
    segs = _segments(arm, bones)
    blen = np.cumsum([0] + [(b - a).length for _, a, b in segs])
    bins = [[] for _ in range(slices)]
    for i in {i for f in tail_faces for i in gm.polygons[f].vertices}:
        _, _, _, t, k = _nearest_on(gm.vertices[i].co, segs)
        s = (blen[k] + t * (blen[k + 1] - blen[k])) / blen[-1]
        bins[min(int(s * slices), slices - 1)].append(gm.vertices[i].co[:])
    line = [Vector((np.min(b, 0) + np.max(b, 0)) / 2) for b in bins if len(b) >= 4]
    lsegs = [(None, a, b) for a, b in zip(line, line[1:])]
    llen = np.cumsum([0] + [(b - a).length for a, b in zip(line, line[1:])])
    L = llen[-1]

    def arc(co):
        d, _, q, t, k = _nearest_on(co, lsegs)
        return (llen[k] + t * (llen[k + 1] - llen[k])) / L, d, q

    def along(s):
        k = min(int(np.searchsorted(llen, s * L, side="right")) - 1, len(line) - 2)
        t = (s * L - llen[k]) / max(llen[k + 1] - llen[k], 1e-6)
        return line[k] + (line[k + 1] - line[k]) * t, (line[k + 1] - line[k]).normalized()

    bvh = BVHTree.FromPolygons([v.co for v in gm.vertices], [gm.polygons[i].vertices for i in tail_faces])

    def ring_at(s):
        """The ring's points at s (0-1 along the tail), each where a ray from the centre meets the tail's
        surface, and their median radius."""
        c, t = along(s)
        u = Vector((0, 0, 1)) - t * t.z
        if u.length < 0.3:
            u = Vector((1, 0, 0)) - t * t.x
        u.normalize()
        v = t.cross(u)
        dirs = [math.cos(2 * math.pi * (k + 0.5) / sides) * u + math.sin(2 * math.pi * (k + 0.5) / sides) * v
                for k in range(sides)]
        hits = [bvh.ray_cast(c, d, 1.0)[0] for d in dirs]
        r = [(h - c).length for h in hits if h is not None]
        med = float(np.median(r)) if r else 0.1
        return [c + d * (min((h - c).length, 1.5 * med) if h is not None else med) for d, h in zip(dirs, hits)], med

    radius = [ring_at((b + 0.5) / slices)[1] for b in range(slices)]
    # The faces it replaces: the tail's own, near its centreline and facing away from it (not the coat
    # behind it, which the tail bones also pull on). Their colours, by slice, place the rings.
    votes = [{} for _ in range(slices)]
    replaced = []
    for i in tail_faces:
        p = gm.polygons[i]
        s, d, q = arc(p.center)
        b = min(int(s * slices), slices - 1)
        if d < 1.3 * radius[b] and p.normal.dot((p.center - q).normalized()) > 0.2:
            replaced.append(i)
            c = gm.materials[p.material_index].name
            votes[b][c] = votes[b].get(c, 0) + p.area
    cols = [max(v, key=v.get) if v else None for v in votes]
    for k in range(slices):  # slices without faces take their nearest neighbour's colour
        if cols[k] is None:
            cols[k] = next((cols[j] for j in sorted(range(slices), key=lambda j: abs(j - k)) if cols[j]), "#808080")
    cuts = [0.0] + [k / slices for k in range(1, slices) if cols[k] != cols[k - 1]] + [1.0]
    fine = [0.0]
    for a, b in zip(cuts, cuts[1:]):  # and rings often enough to follow its shape
        n = max(1, math.ceil((b - a) / max_band))
        fine += [a + (b - a) * j / n for j in range(1, n + 1)]
    rings = [[p + (p - along(min(s, 0.99))[0]).normalized() * 0.004 for p in ring_at(min(s, 0.99))[0]] for s in fine]
    band = [cols[min(int((a + b) / 2 * slices), slices - 1)] for a, b in zip(fine, fine[1:])]
    tube = loft(name, rings, bones[0], band[0], cap=(True, True), smooth=0, armature=arm)
    tm = tube.data
    for c in band:
        if c not in [m.name for m in tm.materials]:
            tm.materials.append(build.material(c))
    slot = {m.name: i for i, m in enumerate(tm.materials)}
    n_ring = len(rings) * sides
    for p in tm.polygons:
        ring_ids = [i // sides for i in p.vertices if i < n_ring]
        k = min(ring_ids) if len(ring_ids) == len(p.vertices) else (0 if min(ring_ids) == 0 else len(band) - 1)
        p.material_index = slot[band[k]]
        p.use_smooth = False
    # Each vertex rigidly on its nearest bone; the tube deforms with the armature like the body
    world = tube.matrix_world.copy()
    tube.parent = None
    tube.matrix_world = world
    for b in bones:
        tube.vertex_groups.new(name=b)
    for v in tm.vertices:
        tube.vertex_groups[_nearest_on(v.co, segs)[1]].add([v.index], 1.0, "REPLACE")
    tube.parent = arm
    tube.matrix_world = world
    tube.modifiers.new("armature", "ARMATURE").object = arm
    del tube["pp_model"]
    return tube, replaced


def lowpoly(name="body", budget=None, tubes=None, smooth=6):
    """Turn the rigged, painted generated mesh `name` into a PS1-style low-poly model, as PS1 artists built
    low-poly models over high-poly sculpts. The generated mesh is the guide: a copy is smoothed (so the
    reduction makes broad planes, not crumpled ones) and reduced by edge collapse to a triangle budget per
    zone, spent where it shows: budget {"face": n, "head": n, "body": n}, default 450, 300, 650 (Crash
    Bandicoot had about 500-700 triangles, Spyro about 410). The head is everything above the neck (or
    head) bone's head, the face its front; a rig without a head bone (a vehicle, a blob) is one zone with
    the whole budget. No textures: every triangle takes one colour, the majority of the guide's
    paint under it, and is flat shaded, so the facets read at sprite size. Weights come from the guide, so
    the rig and any actions work unchanged.

    tubes: {name: [bones]} rebuilds long round parts (a tail) as 8-sided tubes fitted to the guide's faces
    on those bones, with a ring on every colour boundary, so each stripe is its own band (reduced with the
    body, a tail has too few triangles for its stripes).

    The guide stays in the .blend as `<name>_hi`, hidden from the render; calling lowpoly again rebuilds
    from it (to change the budget, or after repainting or reweighting the guide)."""
    budget = {"body": 650, "head": 300, "face": 450, **(budget or {})}
    tubes = tubes or {}
    arm = rig.armature()
    guide = bpy.data.objects.get(name + "_hi")
    if guide is None:
        guide = bpy.data.objects[name]
        guide.name = guide.data.name = name + "_hi"
    for n in [name, *tubes]:
        build.remove(n)
    gm = guide.data
    guide_mat = [p.material_index for p in gm.polygons]

    # 1. Tubes, and a copy of the guide without their faces
    replaced, tube_tris = set(), 0
    for tname, bones in tubes.items():
        tube, faces = _tube(tname, guide, arm, bones)
        replaced |= set(faces)
        tube_tris += sum(len(p.vertices) - 2 for p in tube.data.polygons)
    lp = bpy.data.objects.new(name, gm.copy())
    lp.data.name = name
    bpy.context.scene.collection.objects.link(lp)
    lp.matrix_world = guide.matrix_world
    bm = bmesh.new()
    bm.from_mesh(lp.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in replaced], context="FACES")
    bm.to_mesh(lp.data)
    bm.free()
    view = bpy.context.view_layer
    view.objects.active = lp

    # 2. Smooth, then reduce each zone in turn to its budget, the others held
    hb = arm.data.bones.get("neck") or arm.data.bones.get("head")
    if hb is None:  # nothing with a head (a car, a slime): one zone with the whole budget
        budget = {"body": sum(budget.values())}
        head_z = face_x = math.inf
    else:
        head_z, head_x = hb.head_local.z, hb.head_local.x
        co = _co(lp)
        xmax = co[co[:, 2] > head_z, 0].max() if (co[:, 2] > head_z).any() else head_x
        face_x = head_x + 0.35 * (xmax - head_x)

    def zone(c):
        return "body" if c.z <= head_z else "face" if c.x > face_x else "head"

    def tris(z=None):
        return sum(len(p.vertices) - 2 for p in lp.data.polygons if z is None or zone(p.center) == z)

    mod = lp.modifiers.new("smooth", "LAPLACIANSMOOTH")
    mod.iterations, mod.lambda_factor, mod.use_volume_preserve = smooth, 1.0, True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    lp.vertex_groups.new(name="pp_reduce")
    for z in budget:
        vg = lp.vertex_groups["pp_reduce"]  # looked up again: applying a modifier invalidates the old one
        for v in lp.data.vertices:
            vg.add([v.index], 1.0 if zone(v.co) == z else 0.0, "REPLACE")
        mod = lp.modifiers.new("reduce", "DECIMATE")
        mod.decimate_type, mod.use_collapse_triangulate = "COLLAPSE", True
        mod.ratio = min(1.0, (tris() - tris(z) + budget[z]) / tris())
        mod.vertex_group = vg.name
        bpy.ops.object.modifier_apply(modifier=mod.name)
    lp.vertex_groups.remove(lp.vertex_groups["pp_reduce"])

    # 3. One colour per triangle, the majority of the guide's paint under it; flat shading
    bvh = BVHTree.FromPolygons([v.co for v in gm.vertices], [p.vertices for p in gm.polygons])
    for p in lp.data.polygons:
        c = p.center
        votes = {}
        for q in [c] + [c + (lp.data.vertices[i].co - c) * 0.6 for i in p.vertices]:
            idx = bvh.find_nearest(q)[2]
            if idx is not None and idx not in replaced:
                votes[guide_mat[idx]] = votes.get(guide_mat[idx], 0) + 1
        if votes:
            p.material_index = max(votes, key=votes.get)
        p.use_smooth = False
    with bpy.context.temp_override(object=lp, active_object=lp):  # the guide's smoothed normals hide the facets
        bpy.ops.mesh.customdata_custom_splitnormals_clear()

    # 4. Weights from the guide at rest; then the guide is hidden
    lp.vertex_groups.clear()
    for g in guide.vertex_groups:
        lp.vertex_groups.new(name=g.name)
    shown = [(m, m.show_viewport) for m in guide.modifiers]
    for m, _ in shown:
        m.show_viewport = False
    dt = lp.modifiers.new("weights", "DATA_TRANSFER")
    dt.object, dt.use_vert_data, dt.data_types_verts = guide, True, {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src, dt.layers_vgroup_select_dst = "ALL", "NAME"
    bpy.ops.object.modifier_apply(modifier=dt.name)
    for m, s in shown:
        m.show_viewport = s
    world = lp.matrix_world.copy()
    lp.parent = arm
    lp.matrix_world = world
    lp.modifiers.new("armature", "ARMATURE").object = arm
    guide.hide_render = True
    guide.hide_set(True)
    print(f"lowpoly {name}: {tris()} triangles {({z: tris(z) for z in budget})}, tubes {tube_tris} triangles")
    return lp
