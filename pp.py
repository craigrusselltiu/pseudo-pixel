"""pseudo-pixel CLI. Finds Blender and runs the scripts in pp/ inside it.

  python pp.py new     <character_dir> <reference_image>    create a character folder and character.json
  python pp.py run     <character_dir> <script.py>          apply a script to the .blend and save it
  python pp.py inspect <character_dir>                      print the .blend's state as JSON
  python pp.py preview <character_dir> [--anim NAME ...] [--turnaround] [--compare]   review images + checks
  python pp.py render  <character_dir> [animation ...]      spritesheets + JSON in out/
  python pp.py view                                         open every sheet in characters/ and examples/ in the viewer
  python pp.py generate <character_dir> <image> [--seed N]  a 3D model from one image (TripoSG) -> model/generated.glb

Add --verbose to see all of Blender's output.
"""
import base64
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
INSTALL_GLOBS = [
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    "/Applications/Blender.app/Contents/MacOS/Blender",
]
SCRIPTS = {"run": "run.py", "inspect": "info.py", "preview": "preview.py", "render": "render.py"}
# Blender's own chatter: startup banner, per-frame render progress, timestamped log lines.
NOISE = re.compile(r"^(Blender \d|Read blend|Fra:|Saved: |\s*Time: |Info: Saved|Blender quit|"
                   r"\d\d:\d\d\.\d{3} |EGL Error|$)")


def find_blender():
    exe = os.environ.get("BLENDER") or shutil.which("blender")
    if exe:
        return exe
    for pattern in INSTALL_GLOBS:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    sys.exit("Blender not found. Set the BLENDER environment variable to its executable.")


def blend_path(char_dir):
    return os.path.join(char_dir, os.path.basename(os.path.normpath(char_dir)) + ".blend")


def blender(script, char_dir, args, verbose=False):
    blend = blend_path(char_dir)
    if script != "run.py" and not os.path.exists(blend):
        sys.exit(f"{blend} does not exist yet; build it with: python pp.py run {char_dir} <script.py>")
    cmd = [find_blender(), "-b"]
    if os.path.exists(blend):
        cmd.append(blend)
    cmd += ["--python-exit-code", "1", "-P", os.path.join(ROOT, "pp", script), "--", char_dir, *args]
    if verbose:
        return subprocess.call(cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    for line in proc.stdout:
        if not NOISE.match(line):
            sys.stdout.write(line)
    return proc.wait()


DEFAULT_OUTPUT = {
    "frame": [64, 64],
    "pixels_per_unit": 32,
    "anchor": "bottom-center",
    "fps": 12,
    "shading_steps": 4,
    "dither": 0.35,
    "hue_shift": 0.5,
    "light": [-1, -1, 1],
    "outline": {"color": "#1a1c2c", "mode": "inner"},
    "despeckle": True,
    "views": [0],
    "elevation": 0,
}


def new_character(char_dir, reference):
    """Create <char_dir>/ with the reference image, scripts/ and a default character.json."""
    if os.path.exists(os.path.join(char_dir, "character.json")):
        sys.exit(f"{char_dir} already has a character.json")
    if not os.path.isfile(reference):
        sys.exit(f"no reference image at {reference}")
    os.makedirs(os.path.join(char_dir, "scripts"), exist_ok=True)
    ref_name = "reference" + os.path.splitext(reference)[1].lower()
    shutil.copyfile(reference, os.path.join(char_dir, ref_name))
    cfg = {"name": os.path.basename(os.path.normpath(char_dir)), "reference": ref_name,
           "reference_scale": None, "rig": "humanoid", "output": DEFAULT_OUTPUT, "animations": {}}
    with open(os.path.join(char_dir, "character.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    print(f"created {char_dir}: {ref_name}, character.json, scripts/")


def view():
    """Write characters/viewer.html: the viewer with the sheets of every character in characters/ (in
    the current folder) and of the examples embedded, and open it in the browser."""
    sources = [("", os.path.abspath("characters")), ("examples/", os.path.join(ROOT, "examples"))]
    data = {}
    for prefix, folder in sources:
        for meta_path in sorted(glob.glob(os.path.join(folder, "*", "out", "*.json"))):
            out_dir = os.path.dirname(meta_path)
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            png = os.path.join(out_dir, meta.get("meta", {}).get("image", ""))
            if "frames" not in meta or not os.path.isfile(png):
                continue
            with open(png, "rb") as f:
                image = "data:image/png;base64," + base64.b64encode(f.read()).decode()
            char = prefix + os.path.basename(os.path.dirname(out_dir))
            name = os.path.splitext(os.path.basename(meta_path))[0]
            data.setdefault(char, {})[name] = {"image": image, "meta": meta}
    if not data:
        sys.exit("no sheets in characters/*/out or examples/*/out; render a character first")
    with open(os.path.join(ROOT, "viewer", "index.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("<script>", f"<script>window.PP_DATA = {json.dumps(data)};</script>\n<script>", 1)
    os.makedirs("characters", exist_ok=True)
    path = os.path.abspath(os.path.join("characters", "viewer.html"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {path}: {sum(len(a) for a in data.values())} animations of {len(data)} characters")
    webbrowser.open("file:///" + path.replace(os.sep, "/").lstrip("/"))


def generate(char_dir, image, seed):
    """Run TripoSG on an image (transparent background) in its own Python environment and write
    <char_dir>/model/generated.glb. PP_GEN_PYTHON and PP_TRIPOSG locate the environment and the repo;
    the defaults are ../pp-gen/venv and ../pp-gen/TripoSG next to this repository."""
    gen = os.path.join(os.path.dirname(ROOT), "pp-gen")
    python = os.environ.get("PP_GEN_PYTHON") or next(
        (p for p in (os.path.join(gen, "venv", "Scripts", "python.exe"), os.path.join(gen, "venv", "bin", "python"))
         if os.path.exists(p)), None)
    if not python:
        sys.exit("TripoSG's Python environment not found; set PP_GEN_PYTHON (see README)")
    env = {**os.environ, "PP_TRIPOSG": os.environ.get("PP_TRIPOSG", os.path.join(gen, "TripoSG"))}
    out = os.path.join(char_dir, "model", "generated.glb")
    cmd = [python, os.path.join(ROOT, "pp", "gen_triposg.py"), os.path.abspath(image), out, "--seed", str(seed)]
    sys.exit(subprocess.call(cmd, env=env))


def main():
    argv = sys.argv[1:]
    verbose = "--verbose" in argv
    argv = [a for a in argv if a != "--verbose"]
    if len(argv) == 3 and argv[0] == "new":
        return new_character(os.path.abspath(argv[1]), argv[2])
    if argv == ["view"]:
        return view()
    if len(argv) >= 3 and argv[0] == "generate":
        opts = dict(zip(argv[3::2], argv[4::2]))
        if set(opts) - {"--seed"}:
            sys.exit(__doc__)
        return generate(os.path.abspath(argv[1]), argv[2], int(opts.get("--seed", 42)))
    if len(argv) < 2 or argv[0] not in SCRIPTS:
        sys.exit(__doc__)
    cmd, char_dir, rest = argv[0], os.path.abspath(argv[1]), argv[2:]
    if cmd == "run":
        if len(rest) != 1:
            sys.exit(__doc__)
        rest = [os.path.abspath(rest[0])]
    sys.exit(blender(SCRIPTS[cmd], char_dir, rest, verbose))


if __name__ == "__main__":
    main()
