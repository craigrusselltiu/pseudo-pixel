"""Sprite rendering inside Blender, shared by render.py and preview.py.

Sets up an orthographic side camera, swaps every material for flat toon shading, renders frames with no
anti-aliasing and post-processes them with post.py. Never saves the .blend: everything set up here only
exists for this run.
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Vector

import anim
import post

DEFAULTS = {
    "anchor": "bottom-center",
    "shading_steps": 3,
    "light": [-1, -1, 1],
    "palette": None,
    "outline": None,
    "despeckle": False,
    "expand_holds": False,
    "columns": None,
    "normals": False,
    "views": [0],
}
SHADOW = 0.45  # brightness of the darkest toon step, as a factor on the base colour (linear)
CAM_DIST = 20  # camera distance from the origin
ANCHORS = {"bottom-center": (0.5, 1.0), "center": (0.5, 0.5), "bottom-left": (0.0, 1.0)}


def load_config(char_dir):
    with open(os.path.join(char_dir, "character.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["output"] = {**DEFAULTS, **cfg["output"]}
    return cfg


def anim_options(cfg, name):
    return {**cfg["output"], **cfg["animations"].get(name, {})}


def base_color(mat):
    if mat.node_tree:
        for node in mat.node_tree.nodes:
            name = {"BSDF_PRINCIPLED": "Base Color", "EMISSION": "Color"}.get(node.type)
            if name and not node.inputs[name].is_linked:
                return list(node.inputs[name].default_value)[:3]
    return list(mat.diffuse_color)[:3]


class Renderer:
    def __init__(self, char_dir, cfg, tmp):
        self.char_dir, self.cfg, self.tmp = char_dir, cfg, tmp
        self.scene = scene = bpy.context.scene
        self.arm = next(o for o in scene.objects if o.type == "ARMATURE")
        self.meshes = [o for o in scene.objects if o.type == "MESH" and not o.hide_render]
        out = cfg["output"]
        scene.render.fps = out["fps"]
        r = scene.render
        engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
        r.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = 1
        r.filter_size = 0.0
        r.dither_intensity = 0.0
        r.film_transparent = True
        r.resolution_percentage = 100

        cam = bpy.data.objects.get("pp_camera")
        if cam is None:
            cam = bpy.data.objects.new("pp_camera", bpy.data.cameras.new("pp_camera"))
            scene.collection.objects.link(cam)
        cam.data.type = "ORTHO"
        cam.data.clip_end = 2 * CAM_DIST
        scene.camera = self.cam = cam
        for i, obj in enumerate(self.meshes):
            obj.pass_index = i + 1
        self._toon_materials(out["shading_steps"], out["light"])
        self.frame_size = None

    # --- scene setup -------------------------------------------------------------------------------

    def _toon_materials(self, steps, light):
        """Replace every material with flat toon shading: a constant ramp on N.L times the base colour."""
        light = Vector(light).normalized()
        for mat in {s.material for o in self.meshes for s in o.material_slots if s.material}:
            color = base_color(mat)
            nt = mat.node_tree
            nt.nodes.clear()
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            dot = nt.nodes.new("ShaderNodeVectorMath")
            dot.operation = "DOT_PRODUCT"
            dot.inputs[1].default_value = light
            half = nt.nodes.new("ShaderNodeMath")  # half-Lambert: N.L in [-1, 1] -> [0, 1]
            half.operation = "MULTIPLY_ADD"
            half.inputs[1].default_value = half.inputs[2].default_value = 0.5
            ramp = nt.nodes.new("ShaderNodeValToRGB")
            ramp.color_ramp.interpolation = "CONSTANT"
            elems = ramp.color_ramp.elements
            while len(elems) < steps:
                elems.new(1.0)
            while len(elems) > steps:
                elems.remove(elems[-1])
            for i, e in enumerate(elems):
                v = 1.0 if steps == 1 else SHADOW + (1 - SHADOW) * i / (steps - 1)
                e.position, e.color = i / steps, (v, v, v, 1)
            mul = nt.nodes.new("ShaderNodeVectorMath")
            mul.operation = "MULTIPLY"
            mul.inputs[1].default_value = color
            emit = nt.nodes.new("ShaderNodeEmission")
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(geo.outputs["Normal"], dot.inputs[0])
            nt.links.new(dot.outputs["Value"], half.inputs[0])
            nt.links.new(half.outputs[0], ramp.inputs["Fac"])
            nt.links.new(ramp.outputs["Color"], mul.inputs[0])
            nt.links.new(mul.outputs["Vector"], emit.inputs["Color"])
            nt.links.new(emit.outputs[0], out.inputs["Surface"])

    def _id_material(self):
        mat = bpy.data.materials.get("pp_ids")
        if mat:
            return mat
        mat = bpy.data.materials.new("pp_ids")
        nt = mat.node_tree
        nt.nodes.clear()
        info = nt.nodes.new("ShaderNodeObjectInfo")
        cam = nt.nodes.new("ShaderNodeCameraData")
        depth = nt.nodes.new("ShaderNodeMath")  # view depth in pixels (always positive, since
        depth.operation = "MULTIPLY"            # negative emission is clamped to 0)
        depth.name = "depth"
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        emit = nt.nodes.new("ShaderNodeEmission")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(info.outputs["Object Index"], comb.inputs["X"])
        nt.links.new(cam.outputs["View Z Depth"], depth.inputs[0])
        nt.links.new(depth.outputs[0], comb.inputs["Y"])
        nt.links.new(comb.outputs[0], emit.inputs["Color"])
        nt.links.new(emit.outputs[0], out.inputs["Surface"])
        return mat

    def _normal_material(self):
        """Emits the camera-space normal as n * 0.5 + 0.5 (x right, y up, z toward the camera)."""
        mat = bpy.data.materials.get("pp_normals")
        if mat:
            return mat
        mat = bpy.data.materials.new("pp_normals")
        nt = mat.node_tree
        nt.nodes.clear()
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        xf = nt.nodes.new("ShaderNodeVectorTransform")
        xf.vector_type, xf.convert_from, xf.convert_to = "NORMAL", "WORLD", "CAMERA"
        enc = nt.nodes.new("ShaderNodeVectorMath")
        enc.operation = "MULTIPLY_ADD"
        enc.inputs[1].default_value = (0.5, 0.5, -0.5)  # Blender's camera space has +Z pointing away
        enc.inputs[2].default_value = (0.5, 0.5, 0.5)
        emit = nt.nodes.new("ShaderNodeEmission")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(geo.outputs["Normal"], xf.inputs[0])
        nt.links.new(xf.outputs[0], enc.inputs[0])
        nt.links.new(enc.outputs["Vector"], emit.inputs["Color"])
        nt.links.new(emit.outputs[0], out.inputs["Surface"])
        return mat

    def _set_output(self, kind):
        s, vs = self.scene.render.image_settings, self.scene.view_settings
        if kind in ("color", "normals"):
            s.file_format, s.color_mode, s.color_depth = "PNG", "RGBA", "8"
            vs.view_transform = "Standard" if kind == "color" else "Raw"
            bpy.context.view_layer.material_override = None if kind == "color" else self._normal_material()
        else:  # ids: object index in R, depth in pixels in G, as raw floats
            s.file_format, s.color_mode, s.color_depth = "OPEN_EXR", "RGBA", "32"
            vs.view_transform = "Raw"
            bpy.context.view_layer.material_override = self._id_material()
        vs.look, vs.exposure, vs.gamma = "None", 0, 1

    def frame_camera(self, w, h, ppu, anchor="bottom-center", yaw=0.0):
        """Frame w x h pixels at ppu pixels per unit. The world origin (the root's ground position) maps
        to the anchor pixel, measured from the top-left. yaw (degrees) turns the camera around the
        character: 0 is the side view, 90 its front, 180 its other side, 270 its back."""
        ax, ay = (w * ANCHORS[anchor][0], h * ANCHORS[anchor][1]) if isinstance(anchor, str) else anchor
        t = math.radians(yaw)
        right = Vector((math.cos(t), math.sin(t), 0))
        back = Vector((math.sin(t), -math.cos(t), 0))  # from the origin toward the camera
        self.cam.data.ortho_scale = max(w, h) / ppu
        self.cam.location = right * (w / 2 - ax) / ppu + back * CAM_DIST + Vector((0, 0, (ay - h / 2) / ppu))
        self.cam.rotation_euler = (math.pi / 2, 0, t)
        self.scene.render.resolution_x, self.scene.render.resolution_y = w, h
        self._id_material().node_tree.nodes["depth"].inputs[1].default_value = ppu
        self.frame_size, self.ppu, self.right = (w, h), ppu, right

    # --- rendering ---------------------------------------------------------------------------------

    def _render(self, path):
        self.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path)
        px = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(px)
        w, h = img.size
        bpy.data.images.remove(img)
        return np.flipud(px.reshape(h, w, 4))  # Blender rows are bottom-up

    def color(self, frame, tag="f"):
        self._set_output("color")
        self.scene.frame_set(frame)
        px = self._render(os.path.join(self.tmp, f"{tag}_{frame}.png"))
        return np.round(px * 255).astype(np.uint8)

    def normals(self, frame, finished, tag="f"):
        """Normal map for a finished frame: outline pixels get a flat normal, empty pixels stay clear."""
        self._set_output("normals")
        self.scene.frame_set(frame)
        px = np.round(self._render(os.path.join(self.tmp, f"{tag}_{frame}_n.png")) * 255).astype(np.uint8)
        self._set_output("color")
        out = np.zeros_like(px)
        opaque = finished[..., 3] > 0
        surface = opaque & (px[..., 3] >= 128)
        out[surface, :3] = px[surface, :3]
        out[opaque & ~surface, :3] = (128, 128, 255)
        out[opaque, 3] = 255
        return out

    def ids(self, frame, tag="f"):
        """(object ids, depth in pixels) for inner outlines; id 0 and depth inf are empty."""
        self._set_output("ids")
        self.scene.frame_set(frame)
        px = self._render(os.path.join(self.tmp, f"{tag}_{frame}_ids.exr"))
        self._set_output("color")
        hit = px[..., 3] > 0.5
        return np.where(hit, np.round(px[..., 0]), 0).astype(np.int32), np.where(hit, px[..., 1], np.inf)

    def finish(self, px, opts, ids=None, depth=None, scale=1):
        """Post-process one rendered frame with the character's output settings."""
        px = post.binarize_alpha(px)
        palette = post.load_palette(opts["palette"], self.char_dir)
        if palette is not None:
            px = post.quantize(px, palette)
        if opts["despeckle"]:
            px = post.despeckle(px)
        outline = opts["outline"]
        if outline:
            px = post.outline(px, outline.get("color", "#000000"), ids, depth,
                              outline.get("depth", 1.0) * scale)
        return px

    def still(self, frame, opts, scale=1, tag="still"):
        """One finished frame, rendered at `scale` times the frame size and pixels per unit."""
        inner = opts["outline"] and opts["outline"].get("mode", "outer") == "inner"
        px = self.color(frame, tag)
        ids, depth = self.ids(frame, tag) if inner else (None, None)
        return self.finish(px, opts, ids, depth, scale)

    # --- animations --------------------------------------------------------------------------------

    def use_action(self, name):
        act = bpy.data.actions.get(name)
        if act is None:
            raise KeyError(f"no action {name!r} in the .blend; actions: {[a.name for a in bpy.data.actions]}")
        ad = self.arm.animation_data or self.arm.animation_data_create()
        ad.action = act
        if ad.action_slot is None and act.slots:
            ad.action_slot = act.slots[0]
        return act

    def root_motion(self, act):
        """Mute the root bone's location curves and return frame -> (x, y) pixel offset (y down)."""
        curves = [fc for fc in anim.fcurves(act) if fc.data_path == 'pose.bones["root"].location']
        for fc in curves:
            fc.mute = True
        if not curves or "root" not in self.arm.data.bones:
            return lambda f: (0.0, 0.0)
        basis = self.arm.matrix_world.to_3x3() @ self.arm.data.bones["root"].matrix_local.to_3x3()
        ppu, right = self.ppu, self.right

        def offset(f):
            loc = Vector((0, 0, 0))
            for fc in curves:
                loc[fc.array_index] = fc.evaluate(f)
            d = basis @ loc  # world motion, projected onto the screen's right and up
            return (round(d.dot(right) * ppu, 2) + 0.0, round(-d.z * ppu, 2) + 0.0)  # + 0.0 drops -0.0
        return offset

    def animation(self, name, opts, scale=1, yaw=0):
        """Render every timeline frame of an action, merging held frames.

        Returns {"keys": timeline frame of each sprite frame, "frames": finished RGBA arrays,
        "ticks": frames each is held for, "offsets": root motion in pixels, "normals": normal maps
        (when opts["normals"]) or None}.
        """
        w, h = opts["frame"]
        anchor = opts["anchor"]
        if not isinstance(anchor, str):
            anchor = [a * scale for a in anchor]
        self.frame_camera(w * scale, h * scale, opts["pixels_per_unit"] * scale, anchor, yaw)
        act = self.use_action(name)
        offset = self.root_motion(act)
        start, end = (int(round(x)) for x in act.frame_range)
        if opts.get("loop"):
            end -= 1  # last frame repeats the first

        keys, frames, ticks, offsets = [], [], [], []
        for f in range(start, end + 1):
            px = self.color(f, name)
            if frames and offset(f) == offsets[-1] and np.array_equal(px, frames[-1]):
                ticks[-1] += 1
            else:
                keys.append(f)
                frames.append(px)
                ticks.append(1)
                offsets.append(offset(f))

        inner = opts["outline"] and opts["outline"].get("mode", "outer") == "inner"
        for i, f in enumerate(keys):
            ids, depth = self.ids(f, name) if inner else (None, None)
            frames[i] = self.finish(frames[i], opts, ids, depth, scale)
        normals = [self.normals(f, frames[i], name) for i, f in enumerate(keys)] if opts.get("normals") else None
        return {"keys": keys, "frames": frames, "ticks": ticks, "offsets": offsets, "normals": normals}

    def stills(self, name, frames, opts, scale=1):
        """Finished frames of an action at the given timeline frames (root motion muted)."""
        w, h = opts["frame"]
        anchor = opts["anchor"]
        if not isinstance(anchor, str):
            anchor = [a * scale for a in anchor]
        self.frame_camera(w * scale, h * scale, opts["pixels_per_unit"] * scale, anchor)
        self.root_motion(self.use_action(name))
        return [self.still(f, opts, scale, name) for f in frames]


def save_png(path, rgba):
    h, w = rgba.shape[:2]
    img = bpy.data.images.new("pp_png", w, h, alpha=True)
    img.pixels.foreach_set((np.flipud(rgba).astype(np.float32) / 255).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def load_png(path):
    """An image file as a top-down uint8 RGBA array."""
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return np.flipud(np.round(px.reshape(h, w, 4) * 255).astype(np.uint8))


def thin_parts(meshes, ppu, limit=1.5):
    """Mesh parts whose smallest size seen from the side (world x or z, in the current pose) is under
    `limit` pixels. Such parts flicker in and out between frames."""
    out = []
    for o in meshes:
        local = [Vector(c) for c in o.bound_box]
        world = [o.matrix_world @ c for c in local]
        xs, zs = [c.x for c in world], [c.z for c in world]
        size = min(max(xs) - min(xs), max(zs) - min(zs)) * ppu
        if size < limit:
            out.append((o.name, round(size, 2)))
    return out

