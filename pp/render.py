"""Run inside Blender: render each animation to a spritesheet PNG + Aseprite-style JSON (pp.py render).

Every timeline frame is rendered; consecutive identical frames are merged into one sprite frame
with a longer duration (stepped animation holds). Never saves the .blend.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post  # noqa: E402
import sprite  # noqa: E402

char_dir, *only = sys.argv[sys.argv.index("--") + 1:]
cfg = sprite.load_config(char_dir)
missing = [n for n in only if n not in cfg["animations"]]
if missing:
    sys.exit(f"unknown animation(s) {missing}; character.json has {list(cfg['animations'])}")
out_dir = os.path.join(char_dir, "out")
os.makedirs(out_dir, exist_ok=True)


def write_sheet(name, opts, res):
    w, h = opts["frame"]
    fps = opts["fps"]
    frames, ticks, offsets, normals = res["frames"], res["ticks"], res["offsets"], res["normals"]
    clipped = [i for i, px in enumerate(frames) if post.touches_edge(px)]
    if clipped:
        print(f"WARNING {name}: frames {clipped} touch the frame edge; consider a larger frame")

    if opts["expand_holds"]:
        rep = lambda xs: [x for x, t in zip(xs, ticks) for _ in range(t)]  # noqa: E731
        frames, offsets = rep(frames), rep(offsets)
        normals = rep(normals) if normals else None
        ticks = [1] * sum(ticks)

    sheet, pos = post.pack(frames, opts["columns"])
    sprite.save_png(os.path.join(out_dir, name + ".png"), sheet)
    if normals:
        sprite.save_png(os.path.join(out_dir, name + "_n.png"), post.pack(normals, opts["columns"])[0])
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
    if normals:
        meta["meta"]["normalMap"] = name + "_n.png"
    with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"rendered {name}: {len(frames)} frames, ticks {ticks}")


with tempfile.TemporaryDirectory() as tmp:
    r = sprite.Renderer(char_dir, cfg, tmp)
    for name in cfg["animations"]:
        if not only or name in only:
            opts = sprite.anim_options(cfg, name)
            views = opts["views"]
            for yaw in views:
                suffix = "" if list(views) == [0] else f"_{yaw}"
                write_sheet(name + suffix, opts, r.animation(name, opts, yaw=yaw))
