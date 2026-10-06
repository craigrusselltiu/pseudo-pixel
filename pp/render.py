"""Run inside Blender: render each animation to a spritesheet PNG + Aseprite-style JSON.

Every timeline frame is rendered; consecutive identical frames are merged into one sprite frame
with a longer duration (stepped animation holds).
"""
import json
import os
import sys
import tempfile

import bpy
import numpy as np

char_dir, *only = sys.argv[sys.argv.index("--") + 1:]
with open(os.path.join(char_dir, "character.json"), encoding="utf-8") as f:
    cfg = json.load(f)
out_dir = os.path.join(char_dir, "out")
os.makedirs(out_dir, exist_ok=True)

scene = bpy.context.scene
arm = next(o for o in scene.objects if o.type == "ARMATURE")


def setup_scene():
    r = scene.render
    engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    r.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 1
    r.filter_size = 0.0
    r.film_transparent = True
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"

    cam = bpy.data.objects.get("pp_camera")
    if cam is None:
        cam = bpy.data.objects.new("pp_camera", bpy.data.cameras.new("pp_camera"))
        scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.rotation_euler = (np.pi / 2, 0, 0)  # looks along +Y, so +X is screen right
    scene.camera = cam
    return cam


def frame_camera(cam, w, h, ppu):
    # Anchor: world origin sits at the bottom-center of the frame.
    cam.data.ortho_scale = max(w, h) / ppu
    cam.location = (0, -20, h / 2 / ppu)
    scene.render.resolution_x, scene.render.resolution_y = w, h


def render_frame(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    w, h = img.size
    bpy.data.images.remove(img)
    return np.round(px.reshape(h, w, 4) * 255).astype(np.uint8)  # bottom-up rows


def save_png(path, rgba):
    h, w = rgba.shape[:2]
    img = bpy.data.images.new("pp_sheet", w, h, alpha=True)
    img.pixels.foreach_set((rgba.astype(np.float32) / 255).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def render_animation(cam, name, opts, tmp):
    w, h = opts["frame"]
    fps = opts["fps"]
    frame_camera(cam, w, h, opts["pixels_per_unit"])

    act = bpy.data.actions[name]
    arm.animation_data.action = act
    if arm.animation_data.action_slot is None and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    start, end = (int(round(x)) for x in act.frame_range)
    if opts.get("loop"):
        end -= 1  # last frame repeats the first

    frames, ticks = [], []
    for f in range(start, end + 1):
        scene.frame_set(f)
        px = render_frame(os.path.join(tmp, f"{name}_{f}.png"))
        if frames and np.array_equal(px, frames[-1]):
            ticks[-1] += 1
        else:
            frames.append(px)
            ticks.append(1)

    # Rows are bottom-up; the bottom row is the ground line the character stands on, so skip it.
    clipped = [i for i, px in enumerate(frames)
               if px[-1, :, 3].any() or px[:, 0, 3].any() or px[:, -1, 3].any()]
    if clipped:
        print(f"WARNING {name}: frames {clipped} touch the frame edge; consider a larger frame")

    sheet = np.concatenate(frames, axis=1)
    save_png(os.path.join(out_dir, name + ".png"), sheet)
    meta = {
        "frames": [
            {"filename": f"{name} {i}", "frame": {"x": i * w, "y": 0, "w": w, "h": h},
             "duration": round(1000 * t / fps)}
            for i, t in enumerate(ticks)
        ],
        "meta": {
            "app": "pseudo-pixel",
            "image": name + ".png",
            "size": {"w": w * len(frames), "h": h},
            "frameTags": [{"name": name, "from": 0, "to": len(frames) - 1, "direction": "forward"}],
        },
    }
    with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"rendered {name}: {len(frames)} frames, ticks {ticks}")


cam = setup_scene()
with tempfile.TemporaryDirectory() as tmp:
    for name, anim in cfg["animations"].items():
        if not only or name in only:
            render_animation(cam, name, {**cfg["output"], **anim}, tmp)
