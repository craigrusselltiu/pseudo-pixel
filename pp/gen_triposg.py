"""Cut the character out of its reference and run TripoSG (image -> 3D shape) on it: pp.py generate. Runs
in TripoSG's own Python environment, not Blender's.

    python gen_triposg.py <image> <character_dir> [--seed N] [--steps N]

An image without a transparent background is cut out with BRIA RMBG-1.4 (the background remover TripoSG's
own scripts use). Writes <character_dir>/analysis/mask.png and cutout.png, measures the silhouette into
character.json (reference_scale's ground and top rows, and a "references" entry for the image with the
column between the feet as its centre line), then writes <character_dir>/model/generated.glb. The repo is
found through PP_TRIPOSG; the weights download into it on first use (VAST-AI/TripoSG and briaai/RMBG-1.4
on Hugging Face).
"""
import argparse
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F
import trimesh
from PIL import Image

REPO = os.environ.get("PP_TRIPOSG", os.path.join(os.path.dirname(__file__), "..", "..", "pp-gen", "TripoSG"))
sys.path[:0] = [REPO, os.path.join(REPO, "scripts")]

try:
    import diso  # noqa: F401  (TripoSG's fast GPU surface extractor; optional, needs compiling)
    flash = True
except ImportError:  # fall back to scikit-image marching cubes
    import types
    sys.modules["diso"] = types.SimpleNamespace(DiffDMC=None)
    flash = False

from huggingface_hub import snapshot_download  # noqa: E402
from image_process import prepare_image  # noqa: E402
from triposg.pipelines.pipeline_triposg import TripoSGPipeline  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("image")
parser.add_argument("char_dir")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--steps", type=int, default=50)
args = parser.parse_args()
analysis = os.path.join(args.char_dir, "analysis")
os.makedirs(analysis, exist_ok=True)

# 1. The cutout: the image's own alpha when it has a transparent background, else RMBG's mask
im = Image.open(args.image)
rgb = np.asarray(im.convert("RGB"))
alpha = np.asarray(im.convert("RGBA"))[..., 3]
if (alpha < 16).mean() > 0.01:
    mask = alpha > 127
else:
    from briarmbg import BriaRMBG
    weights = os.path.join(REPO, "pretrained_weights", "RMBG-1.4")
    snapshot_download(repo_id="briaai/RMBG-1.4", local_dir=weights)
    net = BriaRMBG.from_pretrained(weights).to("cuda").eval()
    t = torch.from_numpy(rgb.copy()).permute(2, 0, 1)[None].float().cuda() / 255
    with torch.no_grad():
        m = net(F.interpolate(t, (1024, 1024), mode="bilinear") - 0.5)[0][0]
    m = F.interpolate(m, rgb.shape[:2], mode="bilinear")[0, 0]
    m = ((m - m.min()) / (m.max() - m.min())).cpu().numpy()
    alpha = (m * 255).astype(np.uint8)
    mask = m > 0.5
    del net
    torch.cuda.empty_cache()
Image.fromarray((mask * 255).astype(np.uint8)).save(os.path.join(analysis, "mask.png"))
cutout = os.path.join(analysis, "cutout.png")
Image.fromarray(np.dstack([rgb, np.where(mask, 255, 0).astype(np.uint8)])).save(cutout)

# 2. Measure the silhouette: its top and ground rows, and the column between the feet
rows, cols = np.nonzero(mask)
top, ground = int(rows.min()), int(rows.max()) + 1
feet = rows >= ground - max(2, round(0.03 * (ground - top)))
center = int(round(cols[feet].mean()))
cfg_path = os.path.join(args.char_dir, "character.json")
with open(cfg_path, encoding="utf-8") as f:
    cfg = json.load(f)
scale = cfg.get("reference_scale") or {}
cfg["reference_scale"] = {"ground": ground, "top": top, "height": scale.get("height")}
if not cfg.get("references"):
    cfg["references"] = [{"image": cfg["reference"], "mask": "analysis/mask.png", "view": 90, "center": center}]
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print(f"cutout: top row {top}, ground row {ground}, centre line column {center} -> analysis/, character.json")

# 3. The mesh
weights = os.path.join(REPO, "pretrained_weights", "TripoSG")
snapshot_download(repo_id="VAST-AI/TripoSG", local_dir=weights)
pipe = TripoSGPipeline.from_pretrained(weights).to("cuda", torch.float16)
image = prepare_image(cutout, bg_color=np.array([1.0, 1.0, 1.0]), rmbg_net=None)
with torch.no_grad():
    out = pipe(image=image, generator=torch.Generator(device="cuda").manual_seed(args.seed),
               num_inference_steps=args.steps, guidance_scale=7.0, use_flash_decoder=flash).samples[0]
mesh = trimesh.Trimesh(out[0].astype(np.float32), np.ascontiguousarray(out[1]))
output = os.path.join(args.char_dir, "model", "generated.glb")
os.makedirs(os.path.dirname(output), exist_ok=True)
mesh.export(output)
print(f"generated {output}: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
