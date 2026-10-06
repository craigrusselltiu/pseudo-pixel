# Animation reference

Animate like a 2D animator: key poses on whole frames, held (stepped) between keys, with as few
frames as possible. Dead Cells and Guilty Gear Xrd both animate 3D models this way.

## Writing an action

```python
from anim import action, mirrored

a = action("attack")                       # replaces an existing action of that name
a.key(0, {"upper_arm.R": (20, 0, 0)})      # (x, y, z) degrees, see rig.md
a.key(2, {"upper_arm.R": (200, 0, 0), "chest": (-10, 0, 0)})
a.key(6, {"upper_arm.R": (85, 0, 0), "root": {"loc": (0.25, 0, 0)}})
a.key(9, {"body": {"scale": (1.2, 1.2, 0.8)}})  # squash (world-aligned factors)
a.key(11, "rest")                          # every bone back to rest
a.end(13)                                  # last frame; writes the action
```

- **Frames are sprite frames.** The Blender timeline runs at the sprite `fps`. A key at frame 2 is
  sprite frame 2. Only whole frames are allowed.
- **Keys carry over.** Each key starts from the previous key's pose and changes only the bones it
  lists. A bone first keyed at frame 5 is at rest in earlier keys.
- **Stepped by default.** A pose holds until the next key. To ease into a key, add a key one frame
  before or after it, never in-betweens across the whole move. `action(..., interpolation="LINEAR")`
  exists for things like slow floating, but stepped reads more like pixel art.
- **Loops:** `action("walk", loop=True)` and `"loop": true` in `character.json`. `end(n)` adds a key
  at `n` equal to the first pose, and frame `n` is left out of the sheet.
- **In place:** never move the root to travel. Key `root` location for lunges and dashes; it becomes
  `rootMotion` in the JSON for the engine to apply.
- `a.pose_at(frame)` returns a keyed pose; `mirrored(pose)` swaps .L and .R. Use them for the second
  half of walk and run cycles.

## Timing at 12 fps

| Animation | Keys | Typical holds |
|---|---|---|
| idle | 2-4 poses, loop | 4-8 frames each; 1 px body bob |
| walk | contact, down, passing, up, then mirrored; loop | 2 frames each (16 frames) |
| run | same 4 poses, more lean and bigger stride; loop | 1-2 frames each |
| attack | ready, windup, (ease), strike, follow-through, recover | windup 3-4, strike 1, hold strike 2-4, recover 2-3 |
| hit | flinch, hold, recover | 1, 2-3, 2 |
| death | flinch, fall, ground | 1, 2-3, hold |

Anticipation (windup) sells the attack. The strike pose should come with no in-between from the
windup: the jump is what reads as fast. Hold the strike pose longest after the windup.

## Readability at low resolution

- Poses must read as silhouettes. Swing limbs away from the body rather than across it.
- Exaggerate: 30 degrees is barely visible at 32 px; 60-90 reads.
- Keep 1 px bobs on whole pixels (multiples of `1 / pixels_per_unit`), or they flicker.
- Effects (slashes, sparks, dust) are not part of the character. Leave them to the engine.

## Review loop

1. `python pp.py preview <character> --anim <name>`.
2. Look at `previews/<name>.png` (sprite frames at 4x, labelled `frame xticks`) and
   `previews/<name>_hires.png` (the same poses at 4x resolution).
3. Check silhouettes, timing (holds), clipping warnings, and that loops join smoothly.
4. Fix with a new script that rewrites the action, then preview again. Stop after 3 rounds and
   report what still looks wrong.

## Changing fps

`anim.retime(old_fps, new_fps)` scales every key and snaps it to whole frames. Update `fps` in
`character.json` in the same change, then review every contact sheet: holds can change length.
