"""Run inside Blender: review images and text checks (pp.py preview). Never saves the .blend.

    --anim NAME     contact sheets for that animation (repeatable); with no options, every animation
    --turnaround    the model in its rest pose next to the reference image
    --compare       the model over the reference image, at the reference's scale and view
    --view NAME     animation previews from that entry of `views` (a name like E, or a yaw) instead of the
                    first; they are then written as previews/<name>_<view>.png

The turnaround (previews/turnaround.png) has the reference first, then the model from the game view
(the first of `views`), then from the side (0), front (90), other side (180) and back (270): the top
row rendered at 4x resolution, the bottom row at sprite resolution, upscaled.

The comparison (previews/compare.png) renders the idle's first pose (or the rest pose) at the
reference's own scale (reference_scale in character.json) from the game view: the reference, the
model drawn over it, and the two blended half and half (labelled 1, 2, 3), so differences in shape and
placement show.

For each animation it writes previews/<name>.png (every sprite frame at 4x, labelled with the timeline
frame it was sampled at) and previews/<name>_hires.png (the same frames rendered at 4x the resolution,
to judge poses), then prints checks: frame count, clipped frames, colours used, the character's size in
pixels and parts too thin to render reliably.
"""
import os
import sys
import tempfile

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post  # noqa: E402
import sprite  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
char_dir, opts_args = args[0], args[1:]
view = opts_args[opts_args.index("--view") + 1] if "--view" in opts_args else None
anims, after_anim = [], False  # --anim takes one or more names: --anim walk --anim hit, or --anim walk hit
for a in opts_args:
    if a.startswith("--"):
        after_anim = a == "--anim"
    elif after_anim:
        anims.append(a)
turnaround = "--turnaround" in opts_args
compare = "--compare" in opts_args
cfg = sprite.load_config(char_dir)
missing = [n for n in anims if n not in cfg["animations"]]
if missing:
    sys.exit(f"unknown animation(s) {missing}; character.json has {list(cfg['animations'])}")
anims = anims or ([] if turnaround or compare else list(cfg["animations"]))
out_dir = os.path.join(char_dir, "previews")
os.makedirs(out_dir, exist_ok=True)


def preview_animation(r, name):
    opts = sprite.anim_options(cfg, name)
    if view is not None:
        if view not in opts["view_names"]:
            sys.exit(f"no view {view!r}; views: {opts['view_names']}")
        opts["views"] = [opts["views"][opts["view_names"].index(view)]]
        name_out = f"{name}_{view}"
    else:
        name_out = name
    res = r.animation(name, opts)
    frames, keys, ticks = res["frames"], res["keys"], res["ticks"]
    labels = [f"{k:g} x{t}" if t > 1 else f"{k:g}" for k, t in zip(keys, ticks)]
    path = os.path.join(out_dir, name_out + ".png")
    sprite.save_png(path, post.contact_sheet(frames, labels, scale=4))
    hires = r.stills(name, keys, opts, scale=4)
    hires_path = os.path.join(out_dir, name_out + "_hires.png")
    sprite.save_png(hires_path, post.contact_sheet(hires, [f"{k:g}" for k in keys], scale=1, columns=6))

    s = post.stats(frames)
    clipped = [f"{k:g}" for k, f in zip(keys, frames) if post.touches_edge(f)]
    held = f"; held {ticks}" if any(t > 1 for t in ticks) else ""
    print(f"{name}: {len(frames)} sprite frames at {opts['fps']} fps ({sum(ticks) / opts['fps']:.2f} s){held}")
    print(f"  size up to {s['width']}x{s['height']} px in a {opts['frame'][0]}x{opts['frame'][1]} frame; "
          f"{s['colors']} colours")
    if clipped:
        print(f"  CLIPPED at timeline frames {clipped}: opaque pixels touch the frame edge")
    if any(o != (0.0, 0.0) for o in res["offsets"]):
        print(f"  root motion (px): {res['offsets']}")
    print(f"  {path}\n  {hires_path}")


def fit(img, w, h):
    """Nearest-neighbour scale to fit inside w x h, centred on a transparent cell."""
    ih, iw = img.shape[:2]
    k = min(w / iw, h / ih)
    nw, nh = max(1, int(iw * k)), max(1, int(ih * k))
    ys = (np.arange(nh) / k).astype(int).clip(0, ih - 1)
    xs = (np.arange(nw) / k).astype(int).clip(0, iw - 1)
    cell = np.zeros((h, w, 4), dtype=np.uint8)
    y0, x0 = (h - nh) // 2, (w - nw) // 2
    cell[y0:y0 + nh, x0:x0 + nw] = img[ys][:, xs]
    return cell


def preview_turnaround(r):
    out = cfg["output"]
    size = max(out["frame"])
    ppu = out["pixels_per_unit"]
    r.arm.data.pose_position = "REST"
    views = list(dict.fromkeys([*out["views"], 0, 90, 180, 270]))
    elev = out["elevation"]
    hires, small = [], []
    for yaw in views:
        e = elev if yaw in out["views"] else 0
        r.frame_camera(size * 4, size * 4, ppu * 4, "bottom-center", yaw, e)
        hires.append(r.still(0, out, 4, f"turn{yaw}"))
        r.frame_camera(size, size, ppu, "bottom-center", yaw, e)
        small.append(r.still(0, out, 1, f"turn{yaw}s"))
    ref_path = os.path.join(char_dir, cfg.get("reference", "reference.png"))
    blank = np.zeros_like(hires[0])
    ref = fit(sprite.load_png(ref_path), size * 4, size * 4) if os.path.exists(ref_path) else blank
    cells = [ref, *hires, blank, *[c.repeat(4, 0).repeat(4, 1) for c in small]]
    labels = ["", *map(str, views), "", *map(str, views)]
    path = os.path.join(out_dir, "turnaround.png")
    sprite.save_png(path, post.contact_sheet(cells, labels, scale=1, columns=len(views) + 1))
    s = post.stats([small[0]])
    print(f"turnaround: game view ({views[0]}) {s['width']}x{s['height']} px at {ppu} px per unit "
          f"({s['colors']} colours) in a {out['frame'][0]}x{out['frame'][1]} frame")
    if not os.path.exists(ref_path):
        print(f"  no reference image at {ref_path}")
    print(f"  {path}")
    r.arm.data.pose_position = "POSE"


def preview_compare(r):
    """The model over the reference(s) at their own scale and angle: reference, model, and the two blended.

    With a "references" list in character.json (a model sheet: front, side and rear views), each view
    gets a row, rendered in the rest pose. Otherwise the single reference is compared from the game
    view, in the idle's first pose when there is an idle."""
    out = cfg["output"]
    m = cfg.get("reference_scale")
    sheets = cfg.get("references")
    if sheets:
        views = [(os.path.join(char_dir, v["image"]), v["view"], 0, [v["center"], m["ground"]]) for v in sheets]
        ref_ppu = (m["ground"] - m["top"]) / m["height"]
    else:
        ref_path = os.path.join(char_dir, cfg.get("reference", "reference.png"))
        if not m or not os.path.exists(ref_path):
            sys.exit("--compare needs the reference image and reference_scale in character.json")
        views = [(ref_path, out["views"][0], out["elevation"], list(m["ground"]))]
        ref_ppu = (m["ground"][1] - m["top"]) / m["height"]
    if "idle" in bpy.data.actions and not sheets:  # the idle's first pose is the reference pose
        r.root_motion(r.use_action("idle"))
        frame, pose = r.use_action("idle").frame_range[0], "idle frame 0"
    else:
        r.arm.data.pose_position = "REST"
        frame, pose = 0, "rest pose"
    cells = []
    for path, yaw, elevation, anchor in views:
        ref = sprite.load_png(path)
        h, w = ref.shape[:2]
        r.frame_camera(w, h, ref_ppu, anchor, yaw, elevation)
        model = r.still(frame, out, ref_ppu / out["pixels_per_unit"], f"compare{yaw}")
        hit = model[..., 3:] > 0
        over = np.where(hit, model, ref)
        blend = np.where(hit, (ref.astype(np.uint16) + model) // 2, ref).astype(np.uint8)
        cells += [fit(c, 512, 512) for c in (ref, over, blend)]
    r.arm.data.pose_position = "POSE"
    path = os.path.join(out_dir, "compare.png")
    sprite.save_png(path, post.contact_sheet(cells, ["1", "2", "3"] * len(views), scale=1, columns=3))
    print(f"compare: {pose} at the reference's scale ({ref_ppu:.1f} px per unit), views "
          f"{[v[1] for v in views]}\n  {path}")


with tempfile.TemporaryDirectory() as tmp:
    r = sprite.Renderer(char_dir, cfg, tmp)
    if turnaround:
        preview_turnaround(r)
    if compare:
        preview_compare(r)
    for name in anims:
        preview_animation(r, name)
    r.arm.data.pose_position = "REST"
    r.scene.frame_set(0)
    out = cfg["output"]
    thin = sprite.thin_parts(r.meshes, out["pixels_per_unit"], out["views"][0], out["elevation"])
    if thin:
        print("THIN parts (under 1.5 px in the game view, may flicker): "
              + ", ".join(f"{n} {s} px" for n, s in thin))
