# Modelling reference

Turn the reference image into a few dozen low-poly parts, each a flat colour, each parented to one
bone. Detail that renders smaller than a pixel is wasted, so model for the target resolution, not for
the reference.

## 1. Read the reference

Before writing any code, write down:

- **Facing.** Characters face right (+X). If the reference faces left, mirror your measurements.
- **Ground and top.** The pixel where the feet touch the ground (centre of the stance) and the
  topmost pixel of the body (the head; decide whether hats, plumes and ears count).
- **Proportions.** Hip height, head size, shoulder height, arm length, as fractions of the height.
  Pass them to `rig.humanoid(...)`.
- **Parts.** Every region of one colour that moves with one bone: helmet, visor, plume, chest, belt,
  upper arm, forearm, hand, thigh, shin, foot, weapon, shield, cape. Note each part's colour.
- **Near and far.** The side camera sees the character's right side (.R) up close. A far limb that
  looks darker in the reference is shaded, not a different colour: give both sides the same colour.
- **Pose.** References are rarely in the rest pose (standing, arms down). Model parts where they sit in
  the rest pose, then reproduce the reference pose in the idle animation.

## 2. Measure with `Ref`

```python
from build import Ref, mirror, part
R = Ref(ground=(128, 234), top=14, height=1.6)     # reference pixels -> units
at, (sx, sz) = R.box(100, 14, 158, 66)             # a rectangle's centre and side-view size
part("helmet", "box", (sx, 0.4, sz), at, "head", "#9aa6ba", bevel=0.05)
```

`R.pt(x, y)` converts one pixel, `R.len(px)` a length, and `R.points(polygon, at)` turns a
reference polygon into a `profile` part's points. The reference only shows x and z. Choose depth
(y) from what the part is: about 0.8 of the width for heads and torsos, the same as the width for
limbs. Look at the front view in the turnaround to check depths.

## 3. Parts

```python
part(name, shape, size, at, bone, color, bevel=0, taper=1, rotate=(0, 0, 0), segments=10, points=None)
mirror("forearm.L")            # creates forearm.R on the mirrored bone
```

| Shape | Use for |
|---|---|
| `box` | torsos, limbs, helmets, belts, boots. Add `bevel` (about 0.02-0.05) to soften corners |
| `sphere` | heads, hands, gems, eyes |
| `dome` | anything with a flat base: slimes, mushroom caps, round helmets |
| `cylinder` | staffs, shields (with `rotate=(90, 0, 0)` so the face points at the camera), barrels |
| `cone` | hats, spikes, horns. `taper` on a box gives a frustum instead |
| `profile` | flat shapes seen from the side: blades, axes, capes, plumes, ears, tails. `points` are (x, z) in units around `at`, and `size` is the thickness |

- Build parts in the **rest pose**, along their bones. Sizes are full extents (x forward, y left,
  z up) and `at` is the centre.
- **Keep everything over 1.5 px thick** from the side (`1.5 / pixels_per_unit` units). `part()`
  prints a warning when a part is thinner. Exaggerate swords, staffs, limbs and visors.
- **Visible from the side means sticking out in y.** A feature on the front of a head (a visor, a
  nose) only shows from the side if it is deeper than the head, or protrudes forward past it.
- **Layering in depth.** Parts behind the body (capes, far arms, shields on the far arm) must be
  shallower than the body or sit at larger y, or they cover the body in the side view.
- **Model for the camera.** Only the side view is rendered. If the reference draws both eyes on a
  side view, put both on the near side. Cheats like this are normal in 3D-for-2D pipelines.
- **Props on extra bones.** Weapons go on a `weapon` bone that is a child of the hand, so the
  animation can swing the weapon by rotating the hand.
- **Colours.** Sample flat base colours from the reference. Toon shading adds the light and dark tones,
  so pick the mid tone, not the highlight or the shadow.
- Calling `part()` again with the same name replaces that part. Use it in edit scripts
  ("make the helmet bigger"). `recolor(name, hex)` and `remove(name)` also exist.

Typical counts: a humanoid has 15-25 parts. More than about 40 at 48 px is usually wasted.

## 4. Non-humanoids

Use `rig.custom({"root": (...), "body": (...), ...})` with `root` first, at the origin on the
ground. Describe the bones in `character.json` under `"rig"` so later edits know what each one is
for. Squash and stretch uses `{"scale": (x, y, z)}` keys on a bone whose head is on the ground.

## 5. Review loop

1. `python pp.py preview <character> --turnaround`.
2. Look at `previews/turnaround.png`: the reference, then the model from the side (0), front (90),
   other side (180) and back (270), at 4x resolution and at sprite size.
3. Compare the side view with the reference. Check silhouette and proportions, that every part
   reads at sprite size, that features are visible, and that nothing pokes through where it
   shouldn't. Read the printed checks: size in pixels and thin parts.
4. Fix with a new edit script that calls `part()` for the parts that change, then preview again.
5. Stop after 3 rounds and report what still differs from the reference.
