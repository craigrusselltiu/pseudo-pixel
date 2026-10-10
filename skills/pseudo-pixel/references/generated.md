# Generated low-poly pipeline

The way to make sprites of anything: a character, a creature, a vehicle, a prop. Generate a mesh from
the reference, rig what moves, colour it, turn it into a PS1-style low-poly model, animate it, render
it. Each step is one numbered script (or a few), run with `pp.py run`, then previewed and reviewed.

## 1. Generate and import

```
python pp.py new characters/<name> <reference image>
python pp.py generate characters/<name>
```

`generate` cuts the subject out of the reference (unless the image already has a transparent
background) into `analysis/mask.png`, measures it into `character.json` (`reference_scale` ground and
top rows, a `references` entry with the column at the middle of its base as the centre line), and makes
`model/generated.glb` (several minutes on the GPU). Look at `analysis/cutout.png`: it must be the
subject alone. If a floor, a shadow, scenery or a second subject came along (busy backgrounds do that),
make a clean cutout yourself: a copy of the reference at the same size, transparent everywhere but the
subject (start from `analysis/cutout.png` and erase what doesn't belong; don't crop or resize, since
colouring reads the reference at the mask's pixel positions). Then run `generate` again on it,
`pp.py generate characters/<name> characters/<name>/analysis/clean.png`; the mask and measurements
come from its transparency. Set `reference_scale.height` (its real height in
units: about 1.6-2.2 for a person, 1.4 for a car), then `scripts/001_model.py`:

```python
import os
import rig
from model import Blueprint, import_mesh

B = Blueprint()
rig.custom({"root": ((0, 0, 0), (0, 0, 0.2), None)})
import_mesh(os.path.join(B.dir, "model", "generated.glb"), "body", height=B.height, faces=40000)
```

`import_mesh` turns it to face +x, scales it, drops loose fragments, and stands it with the middle of
its base on the origin. The generator treats the image as a front view: whatever faces the camera in
the reference faces +x. Check `--compare` (the mesh should cover the reference's silhouette) and
`--turnaround` (black until coloured). **Checkpoint 1: the shape.** If it's wrong (a missing part, two
parts fused into a lump), try another seed (`generate ... --seed 7`) before working around it.

## 2. Rig what moves

Bones go where the subject bends or turns, named for what they are:

- **A person or humanoid creature:** the humanoid bone names (rig.md), so animations and the library
  work across characters, plus chains for what else it has (`tail.1-3`, `ear.L`, `wing.L.1`).
- **A creature:** a spine chain, legs (`thigh/shin/foot.L/R`, with `.F`/`.B` names for four legs),
  neck, head, tail.
- **A vehicle or machine:** a `body` bone, and a bone for each part that moves on its own (`wheel.FL`,
  a turret, a door, a rotor).
- **A rigid object:** `root` and one `body` bone (it can still bob, squash and spin).

Place each joint on the reference (a column and row; `B.k` units per pixel, `B.ground` the ground row,
`B.views["reference"]["center"]` the centre line column) and put it in the middle of the mesh there:

- `model.front(body, y, z)`: the x of the surface the reference shows at (y, z). A joint inside a limb
  lies about half the limb's thickness behind it.
- `model.centre(body, point, normal, radius)`: the middle of the mesh's cross-section through `point`
  across `normal` (within `radius`). A spine: one x for all its joints, centred at each height. A limb:
  each joint centred across the limb (normal along it), twice, as the directions settle:

```python
def chain(pixels, width):
    pts = [Vector((front(body, *px(c, r)) - width / 2, *px(c, r))) for c, r in pixels]
    for _ in range(2):
        dirs = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
        pts = [centre(body, p, d, radius=width) for p, d in zip(pts, dirs)]
    return pts
```

Parts the reference doesn't show well (a tail behind, the far wheels) are placed from the turnaround's
views. The rest pose is the reference's pose. Then:

```python
rig.add_bones(arm, bones)
rig.add_foot_ik(arm)                 # anything with humanoid legs: planted feet
arm.data.bones["root"].use_deform = False
print("unweighted:", auto_weights(body, arm, voxel=0.015))       # should be 0
limb_weights(body, arm, [["upper_arm.R", "forearm.R", "hand.R"], ["upper_arm.L", "forearm.L", "hand.L"]])
```

- `limb_weights` frees limbs the generated surface fused to whatever they touch (arms against a
  torso, legs inside a skirt): it cuts the bridging faces, closes both sides, and weights each limb to
  its own chain only. Give it every limb that hangs against something. `(bones, radius)` for a limb
  thicker than 0.16 units.
- Rigid parts (wheels, a turret, a helmet that must not bend) take 100% of their bone: pick their
  vertices by position and set the weights directly
  (`group.add([v.index], 1.0, "REPLACE")` after removing them from the other groups).
- Check the weights by posing: a quick script that bends each joint to its extreme, `--turnaround`,
  then put the pose back. Nothing should tear or drag along.

## 3. Colour

The reference shows one side of the subject; the model has every side. Colouring is painting what the
reference shows, then deciding everything it doesn't, and checking it from every direction.

**a. Palette.** One flat mid-tone per material the reference shows (skin, cloth, paint, glass, metal,
rubber, markings), never a light and a dark version of the same material: the toon shader shades.
Markings are their own colour.

**b. Paint.** `model.flatten` turns the reference into flat palette areas (list a material's shading
tones that sit nearer another colour under `shades`); point `references[0].image` at it. Then
`model.paint` (modelling.md, section 6):

```python
paint(body, Blueprint(), PALETTE, bake=False, facing=0.05, no_fill=[<small-feature colours>],
      regions={<bone prefix>: [<colours that part may have>], ...})
```

`regions` keeps each part of the rig to its own colours (a wheel can't turn body-paint red because the
body is red beside it); a single-bone subject needs none. Faces the reference shows are coloured from
it. Faces it doesn't show take the colour of the nearest visible edge of their region, then fill from
neighbours: a guess, which the review corrects.

**c. Review.** `pp.py preview --turnaround` and look at all 8 views, large and at sprite size. Write
down every patch whose colour is wrong. The causes, on any subject:

- **Hidden sides** (back, far side, top, underside) guessed wrong. Decide what is there: materials
  usually continue around (a car's paint and windows wrap to the far side, a coat continues around
  the back, a symmetric subject's far side mirrors its near side). Where the reference gives no clue,
  ask the user, or ask for another view (a side or back image, added to `references` with `view` 0 or
  270, is painted from directly).
- **Bleed** where parts meet or overlap in the reference: something drawn in front of another part
  paints its colour onto the surface behind it (a weapon over a leg, a mirror over a door), and edges
  catch the neighbouring colour.
- **Parts on one bone with different materials** (headgear on a head, windows on a car body, a
  backpack on a back): pick them out by position.
- **Small features** (eyes, lights, badges, buttons) smeared, misplaced or missing: they must cover
  several faces to survive the low-poly step.
- **Faint markings** (rings, stripes, panel lines) that paint didn't pick up.

**d. Fix.** Write the next paint script as the whole colouring again (it repaints from scratch, so the
latest paint script is always the complete recipe) with rules after `paint`:

```python
def rule(c, n):              # c: face centre, n: face normal (world, rest pose); None keeps the colour
    if n.x > 0.5:
        return None          # faces looking at the reference's camera were painted from it
    if PART_LOW < c.z < PART_HIGH and abs(c.y) < PART_HALF_WIDTH:
        return PART_COLOUR   # a part picked out by its measured extent
    if n.x < -0.3 and c.z > BACK_FROM:
        return BACK_COLOUR   # what the back of that area is
    return None

color_faces(body, rule)
stripes(body, [<bone chain>], DARK, 5, base=LIGHT)   # rings around a chain, when the reference shows them
```

Measure every number: on the reference (rows and columns through `B.k`, `B.ground` and the centre line)
and on the mesh (numpy over `body.data.vertices`, `model.centre`). Never guess a boundary; a wrong guess
moves the colour edge to the wrong place on every frame.

**e. Repeat** c and d until every view is right, up to 5 rounds, then report what still differs.

## 4. Parts the generator got wrong

Thin or hard parts often come out as mushy shapes fused to what they touch: weapons, tools, antennas,
mirrors, handles, thin wheels. Cut them out and model them as clean low-poly pieces on their own bone:

```python
cut(body, lambda c, n, color: <inside the part's measured box>)     # delete the faces, close the hole
rig.add_bones(arm, {"sword": (grip, tip, "hand.R")})
loft("sword_blade", [ring(p, Y, Z, (0.02, 0.02, 0.06, 0.06), n=4) for p in (grip, tip)], "sword",
     STEEL, smooth=0)                                                  # 4-sided, flat shaded
```

`loft` with `smooth=0` and `ring(..., n=4 to 8)` gives PS1-style pieces; `build.part` works too. Keep
every piece over 1.5 px thick at sprite size. A part on its own bone can spin and be aimed with
`anim.aim`.

## 5. Low poly

```python
from model import lowpoly
lowpoly("body")                                        # tubes={"tail": ["tail.1", "tail.2", "tail.3"]}
```

The generated mesh becomes the guide (hidden as `body_hi`): a copy is smoothed and reduced to about 1400
triangles, every triangle takes the guide's majority colour and is flat shaded, and the weights come
from the guide. Colour borders are kept: the reduction collapses vertices where two colours meet last,
so borders stay straight runs of edges and small features keep their own polygons; that is why the
colouring comes first. With a head bone, the budget is split so the face gets the most
(`budget={"face": 450, "head": 300, "body": 650}`); without one it is all `body`. Raise it for a busy
subject, lower it for a simple one. `tubes` rebuilds long round parts (tails, tentacles, trunks, hoses)
as 8-sided tubes along their bones, with a ring of edges on every colour boundary.

Review the colours again on the low-poly model, from all 8 views at sprite size: a triangle takes its
majority colour, so small features can vanish and edges can shift. Fix with `color_faces` on `body` (the
same rules work), or fix the guide's colouring and run `lowpoly` again (it rebuilds from `body_hi`).
**Checkpoint 2: the colours.**

## 6. Animate

As animation.md. The rest pose is the reference pose, so rotations start from there: aim limbs and
props with `anim.aim` in world directions rather than guessed angles. Vehicles and machines animate too
(wheels spinning at the speed they travel, a body bobbing on its suspension, a turret turning). Review
every action from several directions (`--anim run --view E`, `--view N`): a pose that reads from the
front can push a limb through the body from the side. **Checkpoint 3: the motion.**

## 7. Render

`pp.py render`. The defaults `pp.py new` writes are the PS1 look: 64x64 frames, 8 directions from 30
degrees above, 5 dithered tones with a little hue shift, no outline, supersampled. Read the warnings:
frames touching the edge need a larger `frame` or a smaller `pixels_per_unit` (render.md).
