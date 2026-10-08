"""Blueprint modelling from orthographic references (front, side, rear), as a 3D artist models from
model sheets: every mesh is lofted through cross-sections whose extents are measured from the
silhouettes, and coloured by projecting the references onto it as flat material regions.

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
        self.ground, self.k = s["ground"], s["height"] / (s["ground"] - s["top"])
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
    colour for each face, from its centre and normal in world space at rest."""
    world = obj.matrix_world
    nmat = world.to_3x3().inverted().transposed()
    mesh = obj.data
    slots = {m.name: i for i, m in enumerate(mesh.materials)}
    for p in mesh.polygons:
        color = rule(world @ p.center, (nmat @ p.normal).normalized())
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
          no_fill=None):
    """Give every face of obj the palette colour nearest to what the references show there.

    palette: {name: hex}, a few flat colours for this mesh (shading comes from the toon shader, so
    leave the reference's shades out). Each face is looked up in the view it faces most (front, rear,
    or side; a face on the left side reads the right-side view at the same x and z when mirror_side),
    but only in a view that can see it: a face hidden behind another part from that camera (a tail
    behind the legs) would get the colour of whatever hides it, so that view is skipped. Faces no view
    sees are filled from their painted neighbours, growing ring by ring, so they take the colour of
    the surface they belong to. views limits the views used, e.g. ["side"] for a tail drawn fully in
    the side view. bake applies the modifiers first so the colour regions follow the subdivided
    surface (pass bake=False on a rigged mesh); clean passes of a majority filter over neighbouring
    faces remove single-face speckles. no_fill: palette names of small features (eyes, nose, a badge)
    that faces no view sees never take from their neighbours, so a dark outline caught on one face
    can't flood the back of a head. facing: how squarely (0-1) a face must point at a view's camera to
    be painted from it; lower it to paint grazing faces (a hat's crown from the front).

    regions (on a skinned mesh): {bone name or prefix: [palette names]}. A face whose vertices are
    mostly weighted to a matching bone may only take those colours, and when no view sees it, it is
    filled only from faces of the same region. Projection can't tell a tail from the trousers in front
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
    _fill(mesh, len(mats), region, {list(palette).index(n) for n in no_fill or ()})
    if clean:
        _majority(mesh, clean, region)


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


def _regions(obj, regions):
    """Each face's region (a key of `regions`, matched as a bone name prefix against the bone most of its
    vertices are weighted to), or None."""
    names = {g.index: g.name for g in obj.vertex_groups}
    vert = []
    for v in obj.data.vertices:
        best = max(v.groups, key=lambda g: g.weight, default=None)
        bone = names.get(best.group) if best else None
        vert.append(next((r for r in regions if bone and bone.startswith(r)), None))
    out = []
    for p in obj.data.polygons:
        counts = {}
        for i in p.vertices:
            counts[vert[i]] = counts.get(vert[i], 0) + 1
        out.append(max(counts, key=counts.get))
    return out


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


def import_mesh(path, name="body", turn=90.0, height=None, faces=0):
    """Import a generated or modelled mesh (GLB, FBX or OBJ) as one object: joined, turned `turn` degrees
    about z so it faces +x (a glTF model facing the viewer faces -y in Blender: 90), scaled to `height`,
    standing on the ground, centred on the origin, decimated to about `faces` faces, smooth shaded."""
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
    lo = Vector([min(v.co[i] for v in bm.verts) for i in range(3)])
    hi = Vector([max(v.co[i] for v in bm.verts) for i in range(3)])
    k = height / (hi.z - lo.z) if height else 1.0
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    for v in bm.verts:
        v.co = (v.co - centre) * k
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
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj
