"""pseudo-pixel CLI. Finds Blender and runs the scripts in pp/ inside it.

  python pp.py new     <character_dir> <reference_image>    create a character folder and character.json
  python pp.py run     <character_dir> <script.py>          apply a script to the .blend and save it
  python pp.py inspect <character_dir>                      print the .blend's state as JSON
  python pp.py preview <character_dir> [--anim NAME ...]    contact sheets + checks in previews/
  python pp.py render  <character_dir> [animation ...]      spritesheets + JSON in out/

Add --verbose to see all of Blender's output.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

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
    "frame": [48, 48],
    "pixels_per_unit": 20,
    "anchor": "bottom-center",
    "fps": 12,
    "shading_steps": 3,
    "light": [-1, -1, 1],
    "outline": {"color": "#1a1c2c", "mode": "inner"},
    "despeckle": True,
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
    cfg = {"name": os.path.basename(os.path.normpath(char_dir)), "reference": ref_name, "rig": "humanoid",
           "output": DEFAULT_OUTPUT, "animations": {}}
    with open(os.path.join(char_dir, "character.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    print(f"created {char_dir}: {ref_name}, character.json, scripts/")


def main():
    argv = sys.argv[1:]
    verbose = "--verbose" in argv
    argv = [a for a in argv if a != "--verbose"]
    if len(argv) == 3 and argv[0] == "new":
        return new_character(os.path.abspath(argv[1]), argv[2])
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
