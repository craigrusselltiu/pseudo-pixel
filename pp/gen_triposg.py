"""Run TripoSG (image -> 3D shape) on one reference image: pp.py generate. Runs in TripoSG's own Python
environment, not Blender's.

    python gen_triposg.py <image> <output.glb> [--seed N] [--steps N]

The image should have a transparent background (an alpha mask); then TripoSG uses it as is. The repo
is found through PP_TRIPOSG; the weights download into it on first use (VAST-AI/TripoSG on Hugging
Face, MIT licence).
"""
import argparse
import os
import sys

import numpy as np
import torch
import trimesh

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
parser.add_argument("output")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--steps", type=int, default=50)
args = parser.parse_args()

weights = os.path.join(REPO, "pretrained_weights", "TripoSG")
snapshot_download(repo_id="VAST-AI/TripoSG", local_dir=weights)
pipe = TripoSGPipeline.from_pretrained(weights).to("cuda", torch.float16)

image = prepare_image(args.image, bg_color=np.array([1.0, 1.0, 1.0]), rmbg_net=None)
with torch.no_grad():
    out = pipe(image=image, generator=torch.Generator(device="cuda").manual_seed(args.seed),
               num_inference_steps=args.steps, guidance_scale=7.0, use_flash_decoder=flash).samples[0]
mesh = trimesh.Trimesh(out[0].astype(np.float32), np.ascontiguousarray(out[1]))
os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
mesh.export(args.output)
print(f"generated {args.output}: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
