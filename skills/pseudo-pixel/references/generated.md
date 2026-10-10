# Generated low-poly pipeline

The default way to make a character: generate a mesh from the reference with TripoSG, rig it, paint it,
turn it into a PS1-style low-poly model, animate it, render it. Each step below is one numbered script
(or a few), run with `pp.py run`, then previewed and reviewed. Everything works for any character:
humanoids, animals, robots, monsters. The examples use a sheriff red panda (revolver, hat, striped
tail).

## 1. Generate and import

```
python pp.py new characters/<name> <reference image>
python pp.py generate characters/<name>
```

`generate` cuts the character out of the reference (RMBG, unless the image already has a transparent
background) into `analysis/mask.png`, measures it into `character.json` (`reference_scale` ground and
top rows, and a `references` entry with the column between the feet as the centre line), and makes
`model/generated.glb` (a few minutes on the GPU). Set `reference_scale.height` (the character's height
in units, about 1.6-2.2 for a humanoid), then `scripts/001_model.py`:

```python
import os
import rig
from model import Blueprint, import_mesh

B = Blueprint()
rig.custom({"root": ((0, 0, 0), (0, 0, 0.2), None)})
import_mesh(os.path.join(B.dir, "model", "generated.glb"), "body", height=B.height, faces=40000)
```

`import_mesh` faces it along +x, scales it, drops loose fragments, and stands it with the point between
its feet on the origin. Check `--compare` (the mesh should cover the reference's silhouette) and
`--turnaround` (it is black until painted). **Checkpoint 1: the shape.** If it's wrong (a missing limb,
a weapon fused into a lump), try another seed: `generate ... --seed 7`.

## 2. Rig

Pick each joint on the reference (column, row; `B.k` units per pixel, `B.ground` the ground row,
`B.views["reference"]["center"]` the centre line column) and put it in the middle of the mesh there:

- `model.front(body, y, z)`: the x of the surface the reference shows at (y, z). A limb's joint lies
  about half the limb's thickness behind it.
- `model.centre(body, point, normal, radius)`: the middle of the mesh's cross-section through `point`
  across `normal` (within `radius`). The spine: one x for all its joints, `centre(body, (0, 0, z))`,
  straight up. Limb joints: centred across the limb (normal along it), twice, as the directions settle.

```python
def limb(pixels, width):
    pts = [Vector((front(body, *px(c, r)) - width / 2, *px(c, r))) for c, r in pixels]
    for _ in range(2):
        dirs = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
        pts = [centre(body, p, d, radius=width) for p, d in zip(pts, dirs)]
    return pts
```

Use the humanoid bone names (rig.md) so animations and the library work across characters; add extra
chains (`tail.1-3`, `ear.L`, `wing.L.1`, ...) for what the character has, placed from the turnaround's
side views. The rest pose is the reference pose (arms where the reference has them). Then:

```python
rig.add_bones(arm, bones)
rig.add_foot_ik(arm)                     # also bends knees fitted behind the hip-ankle line forward
arm.data.bones["root"].use_deform = False
print("unweighted:", auto_weights(body, arm, voxel=0.015))       # should be 0
limb_weights(body, arm, [["upper_arm.R", "forearm.R", "hand.R"], ["upper_arm.L", "forearm.L", "hand.L"]])
```

`limb_weights` frees limbs the generated surface fused to the body (arms against a coat, legs inside
a dress): it cuts the faces bridging limb and body below the armpit, closes both sides, and weights
each limb to its own chain only, so raising an arm doesn't tear the coat. Give it every limb that hangs
against something; a limb much thicker than 0.16 units needs its own radius, `(bones, radius)`.

## 3. Paint

Paint the generated mesh with flat colours from the reference, by region (modelling.md has the
details of `paint` and `flatten`):

```python
PALETTE = {"fur": "#c0521e", "cream": "#f0dcc6", "black": "#140a09", "hat": "#5e3422", "coat": "#5a3322", ...}
flat = flatten("reference.png", "analysis/mask.png", PALETTE, "analysis/flat.png", shades={...})
# point character.json's references[0].image at `flat`, then:
paint(body, Blueprint(), PALETTE, bake=False, facing=0.05, no_fill=["black", "gold"], regions={
    "head": ["fur", "cream", "black", "hat", "gold"], "upper_arm": ["coat"], "foot": ["boots"], ...})
```

- One flat colour per material; the toon shader adds the shading. Markings are colours, not shading.
- A front reference shows only the front. Faces it can't see take the colour that wraps around from the
  silhouette's edge (the back of a coat from its sides), then fill from their neighbours. That is a
  guess: check every side in `--turnaround`.
- Fix what's wrong with small scripts: `model.color_faces(body, rule)`, where `rule(center, normal)`
  returns a colour or None (keep). The back of a head under a hat brim is fur:
  `lambda c, n: FUR if n.x < -0.2 and NECK < c.z < BRIM else None`. Measure the heights and widths
  of parts on the mesh, not by guessing.
- Markings the reference draws too faintly for paint to pick up (a tail's rings, a snake's bands):
  `model.stripes(body, ["tail.1", "tail.2", "tail.3"], DARK, 5, base=FUR)`.
- Small features (eyes, buttons, badges) should cover several faces, or they vanish in the low-poly
  model: paint them bigger with `color_faces` if needed.

## 4. Props

Generated props (guns, swords, staffs, shields) come out as mushy shapes fused into the hand. Cut them
out and model a crisp low-poly one on its own bone:

```python
cut(body, lambda c, n, color: color == STEEL and c.z < HAND_Z)        # delete the faces, close the hole
rig.add_bones(arm, {"gun": (P, P + X * 0.3, "hand.R")})               # a bone in the hand
loft("gun_barrel", [ring(c, Y, Z, (0.04, 0.04, 0.04, 0.04), n=6) for c in (P, P + X * 0.3)], "gun",
     STEEL, smooth=0)                                                  # 6-sided, flat shaded
```

`loft` with `smooth=0` and `ring(..., n=4 to 8)` gives PS1-style prop pieces; `build.part` works too.
Keep every piece over 1.5 px thick at sprite size. A prop on its own bone can spin and be aimed with
`anim.aim`.

## 5. Low poly

```python
from model import lowpoly
lowpoly("body", tubes={"tail": ["tail.1", "tail.2", "tail.3"]})
```

The generated mesh becomes the guide (hidden as `body_hi`): a copy is smoothed, reduced to about 1400
triangles (`budget={"face": 450, "head": 300, "body": 650}`, the head above the neck bone, the face its
front), every triangle takes the guide's majority colour and is flat shaded, and the weights come from
the guide. `tubes` rebuilds long round parts (tails, tentacles, a long trunk) as 8-sided tubes along
their bones with a ring of edges on every colour boundary; leave it out for characters without one.

Re-run `lowpoly` after changing the guide's paint or weights (it rebuilds from `body_hi`; show it with
`bpy.data.objects["body_hi"].hide_set(False)` and hide `body` to paint it, or paint the low-poly
`body` directly with `color_faces`). Raise the budget for a busy character, lower it for a simple one.
Preview with `--compare --turnaround` and look at the sprite-size row: faces, eyes and markings should
still read. **Checkpoint 2: the colours**, on the low-poly model.

## 6. Animate

As animation.md. The rest pose is the reference pose, so rotations are from there: an arm whose rest
reaches forward is aimed with `anim.aim` in world directions rather than guessed angles. Review every
action from several directions (`--anim run --view E`, `--view N`): a pose that reads from the front can
hide a limb through the body from the side. **Checkpoint 3: the motion.**

## 7. Render

`pp.py render`. The defaults `pp.py new` writes are the PS1 look: 64x64 frames, 8 directions from 30
degrees above, 5 dithered tones with a little hue shift, no outline, supersampled. Read the warnings:
frames touching the edge need a larger `frame` or a smaller `pixels_per_unit`.
