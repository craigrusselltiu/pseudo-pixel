"""Sprite rendering inside Blender, shared by render.py and preview.py.

Sets up an orthographic camera at the character's view (yaw and elevation), swaps every material for flat toon shading, renders frames with no
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
import rig

DEFAULTS = {
    "anchor": "bottom-center",
    "shading_steps": 4,
    "dither": 0.35,
    "hue_shift": 0.5,
    "light": [-1, -1, 1],
    "palette": None,
    "outline": None,
    "despeckle": False,
    "merge_holds": False,
    "columns": None,
    "normals": False,
    "views": [0],
    "elevation": 0,
    "supersample": 1,
}
SHADOW = 0.45  # brightness of the darkest toon step, as a factor on the base colour (linear)
SHADOW_TINT = (0.72, 0.8, 1.3)  # per-channel factors the darkest tone leans toward (cool), at hue_shift 1
LIGHT_TINT = (1.12, 1.05, 0.85)  # and the lit tone (warm)
CAM_DIST = 20  # camera distance from the origin
ANCHORS = {"bottom-center": (0.5, 1.0), "center": (0.5, 0.5), "bottom-left": (0.0, 1.0)}


def load_config(char_dir):
    with open(os.path.join(char_dir, "character.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["output"] = _views({**DEFAULTS, **cfg["output"]})
    return cfg


def _views(opts):
    """`views` given as {name: yaw} (8-direction sprites: {"S": 90, "E": 0, ...}) become a list of yaws,
    with the names in `view_names` for the sheet suffixes; a list keeps the yaws as names."""
    views = opts["views"]
    if isinstance(views, dict):
        opts["view_names"], opts["views"] = list(views), list(views.values())
    elif "view_names" not in opts:
        opts["view_names"] = [str(v) for v in views]
    return opts


def anim_options(cfg, name):
    own = cfg["animations"].get(name, {})
    opts = {**cfg["output"], **own}
    if "views" in own:
        opts.pop("view_names", None)
    return _views(opts)


def tone(color, t, hue):
    """One toon tone of a linear base colour: t is 0 for the darkest tone and 1 for the lit one."""
    v = SHADOW + (1 - SHADOW) * t
    k_dark, k_light = hue * (1 - t), hue * t * t
    return [min(c * v * (1 + (d - 1) * k_dark) * (1 + (li - 1) * k_light), 1.0)
            for c, d, li in zip(color, SHADOW_TINT, LIGHT_TINT)]


def _bayer_group():
    """A shader node group: the 4x4 ordered-dither threshold (0-1) of the pixel being rendered, from
    the window coordinate times the render resolution (its input)."""
    ng = bpy.data.node_groups.get("pp_bayer")
    if ng:
        return ng
    ng = bpy.data.node_groups.new("pp_bayer", "ShaderNodeTree")
    ng.interface.new_socket("Resolution", in_out="INPUT", socket_type="NodeSocketVector")
    ng.interface.new_socket("Value", in_out="OUTPUT", socket_type="NodeSocketFloat")
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    coord = n.new("ShaderNodeTexCoord")
    px = n.new("ShaderNodeVectorMath")
    px.operation = "MULTIPLY"
    link(coord.outputs["Window"], px.inputs[0])
    link(gin.outputs[0], px.inputs[1])
    flo = n.new("ShaderNodeVectorMath")
    flo.operation = "FLOOR"
    link(px.outputs[0], flo.inputs[0])
    xyz = n.new("ShaderNodeSeparateXYZ")
    link(flo.outputs[0], xyz.inputs[0])

    def math(op, a, b=None):
        m = n.new("ShaderNodeMath")
        m.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                link(v, m.inputs[i])
        return m.outputs[0]

    def bit(v, level):  # (v / 2**level) mod 2
        return math("FLOORED_MODULO", math("FLOOR", math("DIVIDE", v, 2 ** level)), 2)

    def b2(a, b):  # the 2x2 Bayer matrix [[0, 2], [3, 1]]: 2a + 3b - 4ab
        return math("SUBTRACT", math("ADD", math("MULTIPLY", a, 2), math("MULTIPLY", b, 3)),
                    math("MULTIPLY", math("MULTIPLY", a, b), 4))

    x, y = xyz.outputs[0], xyz.outputs[1]
    v = math("ADD", math("MULTIPLY", b2(bit(x, 0), bit(y, 0)), 4), b2(bit(x, 1), bit(y, 1)))
    link(math("DIVIDE", math("ADD", v, 0.5), 16), gout.inputs[0])
    return ng


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
        r = scene.render
        self.timeline_fps = r.fps / r.fps_base  # the rate the actions are keyed at
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
        self.light = Vector(out["light"]).normalized()
        self.ss = 1
        self._toon_materials(out)
        self.frame_size = None

    # --- scene setup -------------------------------------------------------------------------------

    def _toon_materials(self, out):
        """Replace every material with toon shading: half-Lambert N.L, optionally offset by an ordered
        (Bayer) dither pattern in screen pixels, into a constant ramp of `shading_steps` tones of the base
        colour. With hue_shift, darker tones lean cool and the lit tone warm, as pixel artists shade.
        The light direction and the resolution (for the dither pattern) are set per view by frame_camera."""
        steps, dither, hue = out["shading_steps"], out["dither"], out["hue_shift"]
        self.light_inputs, self.res_inputs = [], []
        for mat in {s.material for o in self.meshes for s in o.material_slots if s.material}:
            color = base_color(mat)
            nt = mat.node_tree
            nt.nodes.clear()
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            dot = nt.nodes.new("ShaderNodeVectorMath")
            dot.operation = "DOT_PRODUCT"
            self.light_inputs.append(dot.inputs[1])
            half = nt.nodes.new("ShaderNodeMath")  # half-Lambert: N.L in [-1, 1] -> [0, 1]
            half.operation = "MULTIPLY_ADD"
            half.inputs[1].default_value = half.inputs[2].default_value = 0.5
            nt.links.new(geo.outputs["Normal"], dot.inputs[0])
            nt.links.new(dot.outputs["Value"], half.inputs[0])
            fac = half.outputs[0]
            if dither and steps > 1:  # fac += (bayer - 0.5) * dither / steps: mixes neighbouring tones
                bayer = nt.nodes.new("ShaderNodeGroup")
                bayer.node_tree = _bayer_group()
                self.res_inputs.append(bayer.inputs[0])
                offset = nt.nodes.new("ShaderNodeMath")
                offset.operation = "MULTIPLY_ADD"
                offset.inputs[1].default_value = dither / steps
                offset.inputs[2].default_value = -0.5 * dither / steps
                add = nt.nodes.new("ShaderNodeMath")
                add.operation = "ADD"
                nt.links.new(bayer.outputs[0], offset.inputs[0])
                nt.links.new(fac, add.inputs[0])
                nt.links.new(offset.outputs[0], add.inputs[1])
                fac = add.outputs[0]
            ramp = nt.nodes.new("ShaderNodeValToRGB")
            ramp.color_ramp.interpolation = "CONSTANT"
            elems = ramp.color_ramp.elements
            while len(elems) < steps:
                elems.new(1.0)
            while len(elems) > steps:
                elems.remove(elems[-1])
            for i, e in enumerate(elems):
                e.position, e.color = i / steps, (*tone(color, 1.0 if steps == 1 else i / (steps - 1), hue), 1)
            emit = nt.nodes.new("ShaderNodeEmission")
            out_node = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(fac, ramp.inputs["Fac"])
            nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
            nt.links.new(emit.outputs[0], out_node.inputs["Surface"])

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

    def frame_camera(self, w, h, ppu, anchor="bottom-center", yaw=0.0, elevation=0.0, ss=1):
        """Frame w x h pixels at ppu pixels per unit. The world origin (the root's ground position) maps
        to the anchor pixel, measured from the top-left. yaw (degrees) turns the camera around the
        character: 0 sees its right side, 90 its front, 180 its left side, 270 its back. elevation
        (degrees) raises the camera to look down. The light turns with the camera, so every view is lit
        from the same screen direction. ss renders ss x ss samples per pixel, which color, ids and
        normals reduce back to w x h (post.downsample)."""
        ax, ay = (w * ANCHORS[anchor][0], h * ANCHORS[anchor][1]) if isinstance(anchor, str) else anchor
        right, up, toward = rig.view_axes(yaw, elevation)
        self.cam.data.ortho_scale = max(w, h) / ppu
        self.cam.location = right * (w / 2 - ax) / ppu + up * (ay - h / 2) / ppu + toward * CAM_DIST
        self.cam.rotation_euler = (math.pi / 2 - math.radians(elevation), 0, math.radians(yaw))
        self.scene.render.resolution_x, self.scene.render.resolution_y = w * ss, h * ss
        self.ss = ss
        self._id_material().node_tree.nodes["depth"].inputs[1].default_value = ppu
        lx, ly, lz = self.light  # +x screen right, -y toward the camera, +z screen up
        light = right * lx - toward * ly + up * lz
        for socket in self.light_inputs:
            socket.default_value = light
        for socket in self.res_inputs:
            socket.default_value = (w, h, 0)
        self.frame_size, self.ppu, self.right, self.up = (w, h), ppu, right, up

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

    def _goto(self, frame):
        """Set the timeline to a frame, which may fall between whole frames."""
        whole = math.floor(frame + 1e-6)
        self.scene.frame_set(whole, subframe=max(frame - whole, 0.0))

    def color(self, frame, tag="f"):
        """The frame as rendered, ss x ss samples per pixel; post.downsample reduces it."""
        self._set_output("color")
        self._goto(frame)
        px = self._render(os.path.join(self.tmp, f"{tag}_{frame}.png"))
        return np.round(px * 255).astype(np.uint8)

    def normals(self, frame, finished, tag="f"):
        """Normal map for a finished frame: outline pixels get a flat normal, empty pixels stay clear."""
        self._set_output("normals")
        self._goto(frame)
        px = np.round(self._render(os.path.join(self.tmp, f"{tag}_{frame}_n.png")) * 255).astype(np.uint8)
        px = post.downsample(px, self.ss)
        self._set_output("color")
        out = np.zeros_like(px)
        opaque = finished[..., 3] > 0
        surface = opaque & (px[..., 3] >= 128)
        out[surface, :3] = px[surface, :3]
        out[opaque & ~surface, :3] = (128, 128, 255)
        out[opaque, 3] = 255
        return out

    def ids(self, frame, tag="f", opaque=None):
        """(object ids, depth in pixels) for inner outlines; id 0 and depth inf are empty. opaque: the
        finished colour frame's coverage, which the ids follow when supersampled."""
        self._set_output("ids")
        self._goto(frame)
        px = self._render(os.path.join(self.tmp, f"{tag}_{frame}_ids.exr"))
        self._set_output("color")
        hit = px[..., 3] > 0.5
        ids, depth = np.where(hit, np.round(px[..., 0]), 0).astype(np.int32), np.where(hit, px[..., 1], np.inf)
        return post.downsample_ids(ids, depth, self.ss, opaque)

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
        px = post.downsample(self.color(frame, tag), self.ss)
        ids, depth = self.ids(frame, tag, px[..., 3] > 0) if inner else (None, None)
        return self.finish(px, opts, ids, depth, scale)

    def _frame_view(self, opts, scale=1, yaw=None):
        """Frame the camera for an animation's output settings, at its first view unless yaw is given.
        Supersampling applies at the sprite size only (scale 1), not to the high-resolution previews."""
        w, h = opts["frame"]
        anchor = opts["anchor"]
        if not isinstance(anchor, str):
            anchor = [a * scale for a in anchor]
        yaw = opts["views"][0] if yaw is None else yaw
        self.frame_camera(w * scale, h * scale, opts["pixels_per_unit"] * scale, anchor, yaw, opts["elevation"],
                          opts["supersample"] if scale == 1 else 1)

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
        ppu, right, up = self.ppu, self.right, self.up

        def offset(f):
            loc = Vector((0, 0, 0))
            for fc in curves:
                loc[fc.array_index] = fc.evaluate(f)
            d = basis @ loc  # world motion, projected onto the screen's right and up
            return (round(d.dot(right) * ppu, 2) + 0.0, round(-d.dot(up) * ppu, 2) + 0.0)  # + 0.0 drops -0.0
        return offset

    def samples(self, act, opts):
        """Timeline frames to sample an action at: one per sprite frame, `fps` per second of animation.
        Loops leave out their last frame, which repeats the first."""
        start, end = act.frame_range
        step = self.timeline_fps / opts["fps"]
        n = (end - start) / step
        if opts.get("loop"):
            if abs(n - round(n)) > 1e-3:
                print(f"WARNING {act.name}: the loop is {end - start:g} timeline frames, not a multiple of "
                      f"{step:g} (timeline fps / sprite fps), so it hitches where it wraps")
            count = max(1, math.ceil(n - 1e-3))
        else:
            count = math.floor(n + 1e-3) + 1
        return [round(start + i * step, 4) for i in range(count)]

    def animation(self, name, opts, scale=1, yaw=None):
        """Sample an action at the sprite fps and render each sample as a sprite frame. With
        opts["merge_holds"], identical consecutive frames merge into one with a longer duration.

        Returns {"keys": timeline frame of each sprite frame, "frames": finished RGBA arrays,
        "ticks": sprite frames each is held for, "offsets": root motion in pixels, "normals": normal maps
        (when opts["normals"]) or None}. yaw defaults to the first of opts["views"].
        """
        self._frame_view(opts, scale, yaw)
        act = self.use_action(name)
        offset = self.root_motion(act)

        samples = self.samples(act, opts)
        raws = [self.color(f, name) for f in samples]
        prev = None  # supersampled frames carry hysteresis from frame to frame (post.downsample)
        if opts.get("loop"):  # a warm-up lap, so it carries across the loop point too
            for raw in raws:
                prev = post.downsample(raw, self.ss, prev)
        keys, frames, ticks, offsets = [], [], [], []
        for f, raw in zip(samples, raws):
            px = prev = post.downsample(raw, self.ss, prev)
            if (opts.get("merge_holds") and frames and offset(f) == offsets[-1]
                    and np.array_equal(px, frames[-1])):
                ticks[-1] += 1
            else:
                keys.append(f)
                frames.append(px)
                ticks.append(1)
                offsets.append(offset(f))

        inner = opts["outline"] and opts["outline"].get("mode", "outer") == "inner"
        for i, f in enumerate(keys):
            ids, depth = self.ids(f, name, frames[i][..., 3] > 0) if inner else (None, None)
            frames[i] = self.finish(frames[i], opts, ids, depth, scale)
        normals = [self.normals(f, frames[i], name) for i, f in enumerate(keys)] if opts.get("normals") else None
        return {"keys": keys, "frames": frames, "ticks": ticks, "offsets": offsets, "normals": normals}

    def stills(self, name, frames, opts, scale=1):
        """Finished frames of an action at the given timeline frames (root motion muted)."""
        self._frame_view(opts, scale)
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


def thin_parts(meshes, ppu, yaw=0.0, elevation=0.0, limit=1.5):
    """Mesh parts whose smallest size on screen in the given view (in the current pose) is under
    `limit` pixels. Such parts flicker in and out between frames."""
    right, up, _ = rig.view_axes(yaw, elevation)
    out = []
    for o in meshes:
        world = [o.matrix_world @ Vector(c) for c in o.bound_box]
        xs, zs = [c.dot(right) for c in world], [c.dot(up) for c in world]
        size = min(max(xs) - min(xs), max(zs) - min(zs)) * ppu
        if size < limit:
            out.append((o.name, round(size, 2)))
    return out

