# Rig reference

Every character has one armature. Each mesh part is parented to a single bone (no weight painting).
Build skeletons with `pp/rig.py` so the axis convention below always holds.

## Space

- The character faces **+X**. Its left is **+Y** (away from the camera), up is **+Z**.
- The side camera looks along +Y, so +X is screen right and the character's **right side (.R) is the
  near side**. Put the weapon hand on .R so it stays in front.
- The `root` bone sits at the origin on the ground. The origin maps to the frame's anchor pixel.
- Units: `pixels_per_unit` in `character.json` converts to pixels. At 16 px per unit, one pixel is
  0.0625 units.

## Standard humanoid

```python
import rig
arm = rig.humanoid(height=1.6, head=0.28, legs=0.4)
```

Bones: `root, hips, spine, chest, neck, head, upper_arm.L/R, forearm.L/R, hand.L/R, thigh.L/R,
shin.L/R, foot.L/R`. Parents: hips -> root; spine -> hips -> ...; arms -> chest; legs -> hips.
Rest pose: standing straight, arms hanging at the sides, feet pointing forward.

Proportions are fractions of `height`: `head` (head height), `legs` (hip height), `arms` (shoulder to
wrist), `shoulders` and `hips` (half widths), `feet` (foot length). Chunky proportions (big head,
short legs) read better at 32 px than realistic ones.

Extra bones (weapon, cape, tail, hair, ...) are added with `rig.add_bones`:

```python
hand = arm.data.bones["hand.R"].head_local
rig.add_bones(arm, {"weapon": (hand + Vector((0, 0, -0.08)), hand + Vector((0.5, 0, -0.08)), "hand.R")})
```

Name extras `weapon`, `cape.1`, `cape.2`, `tail.1`, `hair.1`, ... Non-humanoids use
`rig.custom({name: (head, tail, parent)})` with `root` first; describe the skeleton in
`character.json` under `"rig"`.

## Rotation convention

Pose values are **Euler XYZ in degrees**. `rig.py` sets every bone's roll so the axes always mean
the same thing:

| Axis | Meaning | Positive |
|---|---|---|
| X | swing in the side view (the one you see) | the bone's tip moves **forward** (+X). Horizontal bones (feet, tails): the tip moves **down** |
| Y | twist along the bone | rarely needed at low resolution |
| Z | sideways swing, toward or away from the camera | .L/.R bones: tip moves **outward**, away from the body. Centre bones: toward the character's right |

On .R bones Y and Z are mirrored, so the same numbers mean the same motion on both sides, and
`anim.mirrored(pose)` can swap sides without changing values.

Common motions:

| Motion | Value |
|---|---|
| Raise an arm forward to horizontal | `upper_arm: (90, 0, 0)` |
| Raise an arm straight up | `upper_arm: (180, 0, 0)` |
| Arm back behind the body | `upper_arm: (-30, 0, 0)` |
| Bend the elbow | `forearm: (+angle, 0, 0)` |
| Lift the knee / step forward | `thigh: (+angle, 0, 0)` |
| Bend the knee | `shin: (-angle, 0, 0)` |
| Point the toes (heel up) | `foot: (+angle, 0, 0)` |
| Lean forward / back | `chest` or `spine: (+/-angle, 0, 0)` |
| Nod down | `head: (+angle, 0, 0)` |
| Arm out to the side (seen as shorter from the side) | `upper_arm: (0, 0, +angle)` |

Rotations accumulate down the chain: a sword on `weapon` follows hand, forearm and upper arm. To
point the sword forward while the arm is raised, counter-rotate the hand.

## Locations

`{"loc": (x, y, z)}` is in world-aligned units: x forward, y left, z up (y mirrored on .R bones so +y
is outward). Use it on `hips` for body bob (one pixel is `1 / pixels_per_unit`) and on `root` for
root motion. Root location is not rendered: it becomes per-frame `rootMotion` offsets in the JSON.

## FK only

There is no IK. Feet can slide during walks; keep stride poses consistent and check the contact
sheet.
