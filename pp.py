"""pseudo-pixel CLI. Finds Blender and runs the scripts in pp/ inside it.

  python pp.py run    <character_dir> <script.py>   apply a script to the character's .blend and save
  python pp.py render <character_dir> [animation]   render spritesheets to <character_dir>/out
"""
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
INSTALL_GLOBS = [
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    "/Applications/Blender.app/Contents/MacOS/Blender",
]


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


def blender(script, char_dir, *args):
    blend = blend_path(char_dir)
    cmd = [find_blender(), "-b"]
    if os.path.exists(blend):
        cmd.append(blend)
    cmd += ["--python-exit-code", "1", "-P", os.path.join(ROOT, "pp", script), "--", char_dir, *args]
    sys.exit(subprocess.call(cmd))


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("run", "render"):
        sys.exit(__doc__)
    cmd, char_dir, rest = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3:]
    if cmd == "run":
        blender("run.py", char_dir, os.path.abspath(rest[0]))
    else:
        blender("render.py", char_dir, *rest)


if __name__ == "__main__":
    main()
