# Rig reference

Every character has one armature. Each mesh part is parented to a single bone (no weight painting).
Build skeletons with `pp/rig.py` so the axis convention below always holds.

## Space

- The character faces **+X**. Its left is **+Y**, up is **+Z**. Always build and animate in these
  axes, whatever the camera angle.
- The camera is set by `views` and `elevation` in `character.json` (see `rig.view_axes`). At yaw 0 it
  looks along +Y: +X is screen right and the right side (.R) is nearest. At 90 it looks at the
  character's front (along -X), with its right side on screen left. Between 0 and 180 the .R side is
  the nearer one, so a weapon hand on .R stays in front.
- The `root` bone sits at the origin on the ground. The origin maps to the frame's anchor pixel.
- Units: `pixels_per_unit` in `character.json` converts to pixels. At 32 px per unit, one pixel is
  0.03125 units.

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
| X | swing forward and back (what a side view shows) | the bone's tip moves **forward** (+X). Horizontal bones (feet, tails): the tip moves **down** |
| Y | twist along the bone: turns a head or torso | upright bones turn toward the character's **left** (+Y) |
| Z | sideways swing (what a front view shows) | .L/.R bones: tip moves **outward**, away from the body. Centre bones: toward the character's right |

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
| Arm out to the side | `upper_arm: (0, 0, +angle)` |
| Turn the head or torso toward its left | `head` or `chest: (0, +angle, 0)` |

Rotations accumulate down the chain: a sword on `weapon` follows hand, forearm and upper arm. To
point the sword forward while the arm is raised, counter-rotate the hand.

## Locations

`{"loc": (x, y, z)}` is in world-aligned units: x forward, y left, z up (y mirrored on .R bones so +y
is outward). Use it on `hips` for body bob (one pixel is `1 / pixels_per_unit`) and on `root` for
root motion. Root location is not rendered: it becomes per-frame `rootMotion` offsets in the JSON.

`{"scale": (x, y, z)}` scales a bone (and its children) along the world axes. Use it for squash and
stretch on bones whose head sits where the squash should pivot, such as a slime's body on the ground.

## Foot IK

`rig.add_foot_ik()` gives a humanoid game-rig legs: a `foot_ik.L/R` control at each ankle (a child of
`root`, so it stays planted when the hips move) and a `knee_ik.L/R` pole in front of each knee (a
child of its foot control). The shins solve IK to the controls and the feet copy their rotation.

- An action that keys a `foot_ik` bone uses IK for that leg; thigh and shin rotations are then
  ignored. Actions that don't stay plain FK, so walk cycles keyed with thigh rotations still work.
- Key the controls like any bone, in world-aligned units: `"foot_ik.L": {"loc": (0.1, 0.05, 0),
  "rot": (0, 0, 10)}` puts the left foot 0.1 forward and 0.05 outward, toes turned 10 degrees out.
  `rot` X lifts the heel (toe down, with a little `loc` z); Z turns the toes out.
- Then move the body freely: hips location and rotation (bounce, sway, crouch, recoil) bend the knees
  and keep the feet on the ground.
- Call it right after `rig.humanoid(...)`. It gives straight legs a slight forward knee bend in the
  rest pose, which the solver needs.

`anim.leg_ik(...)` (animation.md) is the FK alternative: it computes plain leg rotations that put an
ankle where you want it.
