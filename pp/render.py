"""Run inside Blender: render each animation to a spritesheet PNG + Aseprite-style JSON.

Every timeline frame is rendered; consecutive identical frames are merged into one sprite frame
with a longer duration (stepped animation holds). Never saves the .blend: the toon materials and
camera set up here only exist for this render.
"""
import json
import os
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post  # noqa: E402

char_dir, *only = sys.argv[sys.argv.index("--") + 1:]
with open(os.path.join(char_dir, "character.json"), encoding="utf-8") as f:
    cfg = json.load(f)
out_dir = os.path.join(char_dir, "out")
os.makedirs(out_dir, exist_ok=True)

scene = bpy.context.scene
arm = next(o for o in scene.objects if o.type == "ARMATURE")
meshes = [o for o in scene.objects if o.type == "MESH" and not o.hide_render]

DEFAULTS = {
    "anchor": "bottom-center",
    "shading_steps": 3,
    "light": [-1, -1, 1],
    "palette": None,
    "outline": None,
    "despeckle": False,
    "expand_holds": False,
    "columns": None,
}
SHADOW = 0.45  # brightness of the darkest toon step, as a factor on the base colour (linear)
CAM_DIST = 20  # camera sits at y = -CAM_DIST, looking along +Y
ANCHORS = {"bottom-center": (0.5, 1.0), "center": (0.5, 0.5), "bottom-left": (0.0, 1.0)}


def setup_scene():
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
    cam.rotation_euler = (np.pi / 2, 0, 0)  # looks along +Y, so +X is screen right
    scene.camera = cam
    for i, obj in enumerate(meshes):
        obj.pass_index = i + 1
    return cam


def set_output(kind):
    s = scene.render.image_settings
    if kind == "color":
        s.file_format, s.color_mode, s.color_depth = "PNG", "RGBA", "8"
        scene.view_settings.view_transform = "Standard"
        bpy.context.view_layer.material_override = None
    else:  # ids: object index in R, depth in pixels in G, as raw floats
        s.file_format, s.color_mode, s.color_depth = "OPEN_EXR", "RGBA", "32"
        scene.view_settings.view_transform = "Raw"
        bpy.context.view_layer.material_override = id_material()
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1


def base_color(mat):
    if mat.node_tree:
        for node in mat.node_tree.nodes:
            name = {"BSDF_PRINCIPLED": "Base Color", "EMISSION": "Color"}.get(node.type)
            if name and not node.inputs[name].is_linked:
                return list(node.inputs[name].default_value)[:3]
    return list(mat.diffuse_color)[:3]


def toon_materials(steps, light):
    """Replace every material with flat toon shading: a constant ramp on N.L times the base colour."""
    light = Vector(light).normalized()
    for mat in {s.material for o in meshes for s in o.material_slots if s.material}:
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


def id_material():
    mat = bpy.data.materials.get("pp_ids")
    if mat:
        return mat
    mat = bpy.data.materials.new("pp_ids")
    nt = mat.node_tree
    nt.nodes.clear()
    info = nt.nodes.new("ShaderNodeObjectInfo")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    depth = nt.nodes.new("ShaderNodeMath")  # distance from the camera in pixels; kept positive,
    depth.operation = "MULTIPLY_ADD"        # since negative emission is clamped to 0
    depth.name = "depth"
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    emit = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(info.outputs["Object Index"], comb.inputs["X"])
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], depth.inputs[0])  # camera looks along +Y: larger Y is farther
    nt.links.new(depth.outputs[0], comb.inputs["Y"])
    nt.links.new(comb.outputs[0], emit.inputs["Color"])
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    return mat


def frame_camera(cam, w, h, ppu, anchor):
    """World origin (the root's ground position) maps to the anchor pixel, measured from the top-left."""
    ax, ay = (w * ANCHORS[anchor][0], h * ANCHORS[anchor][1]) if isinstance(anchor, str) else anchor
    cam.data.ortho_scale = max(w, h) / ppu
    cam.location = ((w / 2 - ax) / ppu, -CAM_DIST, (ay - h / 2) / ppu)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    depth = id_material().node_tree.nodes["depth"]
    depth.inputs[1].default_value, depth.inputs[2].default_value = ppu, CAM_DIST * ppu


def render_frame(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    w, h = img.size
    bpy.data.images.remove(img)
    return np.flipud(px.reshape(h, w, 4))  # Blender rows are bottom-up


def save_png(path, rgba):
    h, w = rgba.shape[:2]
    img = bpy.data.images.new("pp_sheet", w, h, alpha=True)
    img.pixels.foreach_set((np.flipud(rgba).astype(np.float32) / 255).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def fcurves(act, slot):
    for layer in act.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot)
            if bag:
                yield from bag.fcurves


def root_motion(act, slot, ppu):
    """Mute the root bone's location curves and return frame -> (x, y) pixel offset (y down)."""
    curves = [fc for fc in fcurves(act, slot) if fc.data_path == 'pose.bones["root"].location']
    for fc in curves:
        fc.mute = True
    if not curves or "root" not in arm.data.bones:
        return lambda f: (0.0, 0.0)
    basis = arm.matrix_world.to_3x3() @ arm.data.bones["root"].matrix_local.to_3x3()

    def offset(f):
        loc = Vector((0, 0, 0))
        for fc in curves:
            loc[fc.array_index] = fc.evaluate(f)
        d = basis @ loc
        return (round(d.x * ppu, 2) + 0.0, round(-d.z * ppu, 2) + 0.0)  # + 0.0 drops -0.0
    return offset


def render_animation(cam, name, opts, tmp):
    w, h = opts["frame"]
    fps, ppu = opts["fps"], opts["pixels_per_unit"]
    frame_camera(cam, w, h, ppu, opts["anchor"])

    act = bpy.data.actions[name]
    arm.animation_data.action = act
    if arm.animation_data.action_slot is None and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    offset = root_motion(act, arm.animation_data.action_slot, ppu)
    start, end = (int(round(x)) for x in act.frame_range)
    if opts.get("loop"):
        end -= 1  # last frame repeats the first

    set_output("color")
    keys, frames, ticks, offsets = [], [], [], []
    for f in range(start, end + 1):
        scene.frame_set(f)
        px = np.round(render_frame(os.path.join(tmp, f"{name}_{f}.png")) * 255).astype(np.uint8)
        if frames and offset(f) == offsets[-1] and np.array_equal(px, frames[-1]):
            ticks[-1] += 1
        else:
            keys.append(f)
            frames.append(px)
            ticks.append(1)
            offsets.append(offset(f))

    outline = opts["outline"]
    ids = depth = None
    if outline and outline.get("mode", "outer") == "inner":
        set_output("ids")
        ids, depth = [], []
        for f in keys:
            scene.frame_set(f)
            px = render_frame(os.path.join(tmp, f"{name}_{f}_ids.exr"))
            ids.append(np.where(px[..., 3] > 0.5, np.round(px[..., 0]), 0).astype(np.int32))
            depth.append(np.where(px[..., 3] > 0.5, px[..., 1], np.inf))
        set_output("color")

    palette = post.load_palette(opts["palette"], char_dir)
    for i, px in enumerate(frames):
        px = post.binarize_alpha(px)
        if palette is not None:
            px = post.quantize(px, palette)
        if opts["despeckle"]:
            px = post.despeckle(px)
        if outline:
            px = post.outline(px, outline.get("color", "#000000"),
                              ids[i] if ids else None, depth[i] if depth else None,
                              outline.get("depth", 1.0))
        frames[i] = px

    clipped = [i for i, px in enumerate(frames) if post.touches_edge(px)]
    if clipped:
        print(f"WARNING {name}: frames {clipped} touch the frame edge; consider a larger frame")

    if opts["expand_holds"]:
        rep = lambda xs: [x for x, t in zip(xs, ticks) for _ in range(t)]  # noqa: E731
        frames, offsets, ticks = rep(frames), rep(offsets), [1] * sum(ticks)

    sheet, pos = post.pack(frames, opts["columns"])
    save_png(os.path.join(out_dir, name + ".png"), sheet)
    has_motion = any(o != (0.0, 0.0) for o in offsets)
    entries = []
    for i, ((x, y), t, (ox, oy)) in enumerate(zip(pos, ticks, offsets)):
        e = {"filename": f"{name} {i}", "frame": {"x": x, "y": y, "w": w, "h": h},
             "duration": round(1000 * t / fps)}
        if has_motion:
            e["rootMotion"] = {"x": ox, "y": oy}
        entries.append(e)
    meta = {
        "frames": entries,
        "meta": {
            "app": "pseudo-pixel",
            "image": name + ".png",
            "size": {"w": sheet.shape[1], "h": sheet.shape[0]},
            "frameTags": [{"name": name, "from": 0, "to": len(frames) - 1,
                           "direction": "forward"}],
        },
    }
    with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"rendered {name}: {len(frames)} frames, ticks {ticks}")


missing = [n for n in only if n not in cfg["animations"]]
if missing:
    sys.exit(f"unknown animation(s) {missing}; character.json has {list(cfg['animations'])}")
output = {**DEFAULTS, **cfg["output"]}
cam = setup_scene()
toon_materials(output["shading_steps"], output["light"])
with tempfile.TemporaryDirectory() as tmp:
    for name, anim in cfg["animations"].items():
        if not only or name in only:
            render_animation(cam, name, {**output, **anim}, tmp)
