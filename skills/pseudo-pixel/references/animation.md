# Animation reference

Animate the model the way you would for a 3D game: key poses on Blender's timeline (24 fps), smooth
interpolation between them, and the usual principles (anticipation, follow-through, overlap, easing,
secondary motion). The renderer then samples the finished motion at the sprite `fps` (12 by
default): one sprite frame every `1 / fps` seconds, from the game view. Don't plan sprite frames;
plan motion in seconds, and the sheet follows from the length.

## Writing an action

```python
from anim import action, mirrored

a = action("attack")                         # replaces an existing action of that name
a.key(0, {"upper_arm.R": (20, 0, 0)})        # (x, y, z) degrees, see rig.md
a.key(6, {"upper_arm.R": (-40, 0, 0), "chest": (-10, 0, 0)})            # anticipation
a.key(9, {"upper_arm.R": (95, 0, 0), "chest": (15, 0, 0),
          "root": {"loc": (0.25, 0, 0)}})                                # strike, fast
a.key(12, {"upper_arm.R": (110, 0, 0)})                                  # follow-through
a.key(22, "rest")                                                       # settle
a.end(24)                                    # last frame: 24 timeline frames = 1 second
```

- **Frames are timeline frames at 24 fps** (the .blend's rate; `inspect` shows it as
  `timeline_fps`). Keys go on whole frames. Seconds = frames / 24.
- **Interpolation is smooth (Bezier)** by default, with easing into and out of every key. A fast move
  is keys close together; a hold is the same pose keyed twice, or two poses close enough that the
  motion drifts (a "moving hold" reads better than a dead stop). `action(..., interpolation=
  "LINEAR")` and `"CONSTANT"` (stepped) exist but are rarely what you want.
- **Keys carry over.** Each key starts from the previous key's pose and changes only the bones it
  lists. A bone first keyed at frame 10 is at rest in earlier keys.
- **Key the whole body.** A shot is not just an arm: the chest twists and leans, the head follows a
  beat later, the hips shift, the knees absorb, the free arm reacts, tails, coats and ears lag behind
  and overshoot. Offset these by 1-3 frames so the body doesn't move as one block: key the hips on
  the beat, the chest two frames later, the head three, arms and tail four.
- **Plant the feet.** Whenever the feet should stay on the ground (idles, attacks from a stance,
  shots, hits), key the `foot_ik` controls (rig.md) and move the hips. Moving the hips with FK legs
  moves the feet too, and the character floats.
- **Give it life, calmly.** An idle is a slow, steady loop the player sees for seconds at a time:
  a breath (hips up and down about a pixel, chest lifting, shoulders rising, head a beat later), soft
  knees, a tail or cloth drifting out of phase, and at most one slow weight shift per loop. Busy idles
  (bounces twice a second, heels popping, the head nodding with every beat) read as twitching at
  sprite size. Save the bounce for combat stances that need it, and even then one beat per second.
- **Loops:** `action("walk", loop=True)` and `"loop": true` in `character.json`. `end(n)` adds a key
  at `n` equal to the first pose and makes the curves cyclic, so the motion flows through the loop
  point; frame `n` is left out of the sheet. Make loop lengths a multiple of `24 / fps` frames (2 at
  12 fps) or the loop hitches; the preview warns when it is not.
- **In place:** never move the root to travel. Key `root` location for lunges and dashes; it becomes
  `rootMotion` in the JSON for the engine to apply.
- **Aiming props:** a sword or gun is a rigid object on a hand bone. To point it, don't guess hand
  angles: `aim(pose, "hand.R", direction, axis, up=(axis2, direction2))` returns the hand rotation
  that, with the rest of `pose` applied, turns the prop's `axis` (its blade or barrel, as it points in
  the rest pose) along `direction` (world), and keeps `axis2` (a guard, a gun's top) near `direction2`.
- `a.pose_at(frame)` returns a keyed pose; `mirrored(pose)` swaps .L and .R. Use them for the second
  half of walk and run cycles.
- **Planting feet:** `leg_ik(side, ankle=(x, z), hips=(0, 0, dz), toe=0)` returns thigh, shin and foot
  values that put the ankle at (x, z) with the knee bent forward and the foot level (tilted by `toe`
  degrees, positive toe-down). Pass the same hips location you key. They are ordinary keys, so
  `inspect` shows plain rotations. Use it for crouches, landings and walks whose feet slide:

  ```python
  a.key(8, {"hips": {"loc": (0, 0, -0.2)}, **leg_ik("L", (0.1, 0.06), hips=(0, 0, -0.2)),
            **leg_ik("R", (-0.1, 0.06), hips=(0, 0, -0.2), toe=15)})
  ```

## Timing

Lengths and beats as in a 3D action game. At 12 fps, every second is 12 sprite frames.

| Animation | Length | Beats |
|---|---|---|
| idle | 2-3 s loop | one slow breath on soft knees (the hips about a pixel up and down), chest and shoulders lifting, head and arms settling a beat later, tail or cloth swaying slowly out of phase; at most one gentle weight shift |
| walk | 0.8-1.2 s loop | contact, down, passing, up for each foot, with arm swing, hip sway and a little head bob |
| run | 0.5-0.7 s loop | the walk's beats with more lean, bigger stride and a flight phase |
| attack / shoot | 0.5-1.2 s | anticipation (0.15-0.3 s), a fast action (2-4 frames at 24 fps), follow-through and recoil, recovery back to the ready pose |
| hit | 0.4-0.7 s | a sharp reaction away from the hit in 2-3 frames, a short hold, a recovery with overshoot |
| death | 1-2 s | reaction, fall with overlap, settle on the ground, hold |

## Readability at sprite size

- Poses must read as silhouettes from the game view. Swing limbs where the camera sees the motion: in
  a front view a forward swing is foreshortened, so add sideways motion, twist or lean.
- Push extremes a little further than for a full-size 3D game; small motions vanish at 64 px.
- Few strong poses, eased. As in Dead Cells' pipeline: get the motion right with the fewest key poses
  that read, then let the in-betweens sit next to the keys (ease in and out), not evenly between
  them. Put every key pose on a sampled frame (even timeline frames at 12 fps) so it is drawn.
- Think in pixels: bobs, sways and recoils of whole pixels (`1 / pixels_per_unit` units) read; a third
  of a pixel only adds noise.
- Keep the head steady. Turning or tilting it a few degrees shifts every pixel of the face, which
  reads as twitching; turn it only when the action is about looking somewhere.
- Keep small secondary parts (tails, straps, ears) from popping in and out of the silhouette every
  other frame: swing them slowly, or keep them behind the body.
- Keep motion smooth (Bezier). Don't step an animation (`CONSTANT`) to hide flickering pixels; that
  is what `supersample` in `character.json` is for (README).
- Effects (muzzle flashes, slashes, sparks, dust) are not part of the character. Leave them to the
  engine.

## Review loop

1. `python pp.py preview <character> --anim <name>`.
2. Look at `previews/<name>.png` (every sprite frame at 4x, labelled with the timeline frame it was
   sampled at) and `previews/<name>_hires.png` (the same moments at 4x resolution).
3. Check the motion frame to frame: arcs, spacing (fast moves have big gaps, eases small ones), that
   the anticipation and the key pose land on sampled frames, overlap, clipping warnings, and that
   loops join smoothly. If an important pose falls between samples, move its key to a frame that is
   sampled (an even frame at 12 fps).
4. Fix with a new script that rewrites the action, then preview again. Stop after 5 rounds and
   report what still looks wrong.

## Speed

`anim.retime(factor, ["attack"])` stretches an action's timing (2 is half speed, 0.5 double). The
sprite `fps` in `character.json` only sets how often the motion is sampled.
