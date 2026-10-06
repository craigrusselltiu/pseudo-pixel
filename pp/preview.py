"""Run inside Blender: review images and text checks (pp.py preview). Never saves the .blend.

    --anim NAME     contact sheets for that animation (repeatable); with no options, every animation
    --turnaround    the model in its rest pose next to the reference image

The turnaround (previews/turnaround.png) has the reference first, then the model seen from the side
(the game view, labelled 0), front (90), other side (180) and back (270): the top row rendered at 4x
resolution, the bottom row at sprite resolution, upscaled.

For each animation it writes previews/<name>.png (every sprite frame at 4x, labelled with its timeline
frame and how many frames it is held) and previews/<name>_hires.png (the same frames rendered at 4x the
resolution, to judge poses), then prints checks: frame count, held ticks, clipped frames, colours used,
the character's size in pixels and parts too thin to render reliably.
"""
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post  # noqa: E402
import sprite  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
char_dir, opts_args = args[0], args[1:]
anims = [opts_args[i + 1] for i, a in enumerate(opts_args) if a == "--anim"]
turnaround = "--turnaround" in opts_args
cfg = sprite.load_config(char_dir)
missing = [n for n in anims if n not in cfg["animations"]]
if missing:
    sys.exit(f"unknown animation(s) {missing}; character.json has {list(cfg['animations'])}")
anims = anims or ([] if turnaround else list(cfg["animations"]))
out_dir = os.path.join(char_dir, "previews")
os.makedirs(out_dir, exist_ok=True)


def preview_animation(r, name):
    opts = sprite.anim_options(cfg, name)
    res = r.animation(name, opts)
    frames, keys, ticks = res["frames"], res["keys"], res["ticks"]
    labels = [f"{k} x{t}" if t > 1 else str(k) for k, t in zip(keys, ticks)]
    path = os.path.join(out_dir, name + ".png")
    sprite.save_png(path, post.contact_sheet(frames, labels, scale=4))
    hires = r.stills(name, keys, opts, scale=4)
    hires_path = os.path.join(out_dir, name + "_hires.png")
    sprite.save_png(hires_path, post.contact_sheet(hires, [str(k) for k in keys], scale=1, columns=6))

    s = post.stats(frames)
    clipped = [k for k, f in zip(keys, frames) if post.touches_edge(f)]
    print(f"{name}: {len(frames)} sprite frames over {sum(ticks)} ticks at {opts['fps']} fps; "
          f"held {ticks}")
    print(f"  size up to {s['width']}x{s['height']} px in a {opts['frame'][0]}x{opts['frame'][1]} frame; "
          f"{s['colors']} colours")
    if clipped:
        print(f"  CLIPPED at frames {clipped}: opaque pixels touch the frame edge")
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
    views = (0, 90, 180, 270)
    hires, small = [], []
    for yaw in views:
        r.frame_camera(size * 4, size * 4, ppu * 4, "bottom-center", yaw)
        hires.append(r.still(0, out, 4, f"turn{yaw}"))
        r.frame_camera(size, size, ppu, "bottom-center", yaw)
        small.append(r.still(0, out, 1, f"turn{yaw}s"))
    ref_path = os.path.join(char_dir, cfg.get("reference", "reference.png"))
    blank = np.zeros_like(hires[0])
    ref = fit(sprite.load_png(ref_path), size * 4, size * 4) if os.path.exists(ref_path) else blank
    cells = [ref, *hires, blank, *[c.repeat(4, 0).repeat(4, 1) for c in small]]
    labels = ["", *map(str, views), "", *map(str, views)]
    path = os.path.join(out_dir, "turnaround.png")
    sprite.save_png(path, post.contact_sheet(cells, labels, scale=1, columns=len(views) + 1))
    s = post.stats([small[0]])
    print(f"turnaround: side view {s['width']}x{s['height']} px at {ppu} px per unit "
          f"({s['colors']} colours) in a {out['frame'][0]}x{out['frame'][1]} frame")
    if not os.path.exists(ref_path):
        print(f"  no reference image at {ref_path}")
    print(f"  {path}")
    r.arm.data.pose_position = "POSE"


with tempfile.TemporaryDirectory() as tmp:
    r = sprite.Renderer(char_dir, cfg, tmp)
    if turnaround:
        preview_turnaround(r)
    for name in anims:
        preview_animation(r, name)
    r.arm.data.pose_position = "REST"
    r.scene.frame_set(0)
    thin = sprite.thin_parts(r.meshes, cfg["output"]["pixels_per_unit"])
    if thin:
        print("THIN parts (under 1.5 px from the side, may flicker): "
              + ", ".join(f"{n} {s} px" for n, s in thin))
