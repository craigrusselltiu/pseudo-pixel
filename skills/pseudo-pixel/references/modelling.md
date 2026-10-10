# Modelling reference

Building a character from parts, for when the generator isn't available (the default pipeline is
[generated.md](generated.md)), and the details of painting a generated mesh (section 6). Props on a
generated character are built the same way, with `part` or `model.loft`.

Build a 3D model that looks like the reference: from the reference's own angle, the model should
line up with the drawing in silhouette, proportions, features and colours. Use as many parts as that
takes. Each part has one flat colour and is parented to one bone.

## 1. Read the reference

Before writing any code, write down:

- **Angle.** Where the camera is relative to the character. Characters face +X, so `yaw` is 0 when
  the reference shows the character's right side facing screen right, 90 when it faces the camera,
  180 for its left side facing screen left, 270 from behind. A three-quarter view facing the camera
  and turned toward screen right is about 60-75; turned toward screen left, about 105-120. Judge
  `elevation` from how much of the tops of things you see (hat brims, shoulders, feet): 0 at eye
  level, 10-30 for the usual slightly-from-above game view. Put them in `character.json` as
  `views: [yaw]` and `elevation`.
- **Scale.** The pixel under the character's origin (on the ground, between the feet), the y of its
  highest pixel (decide whether hats, plumes and ears count), and its height in units (about 1.6-2.2
  for a humanoid). Put them in `character.json` as `reference_scale`.
- **Proportions.** Hip height, head size, shoulder height and width, arm length, as fractions of the
  height. Pass them to `rig.humanoid(...)`. Keep the reference's proportions, however stylised.
- **Parts.** Every region that moves with one bone, and every visible feature on it: hat, brim, band,
  ears and their inner colour, eyes, brows, muzzle, nose, cheek patches, collar, scarf, lapels, shirt,
  buttons, badges, belt and buckle, pockets, sleeves, cuffs, gloves, coat tails, trousers, boots,
  weapons, tails and their stripes. Note each one's colour and where it sits.
- **Near and far.** A far limb that looks darker in the reference is shaded, not a different colour:
  give both sides the same colour.
- **Pose.** References are rarely in the rest pose (standing, arms down). Model parts where they sit
  in the rest pose, then reproduce the reference pose as the first pose of the idle animation.

## 2. Measure with `Ref`

`Ref` turns reference pixels into units in the reference's view. With `reference_scale`, `views` and
`elevation` set in `character.json`, `Ref()` needs no arguments.

```python
from build import Ref, mirror, part
R = Ref()                                   # or Ref(ground=(630, 1170), top=185, height=2.2, yaw=70)
at, (w, h) = R.box(510, 185, 790, 345)      # a pixel rectangle: its world centre and on-screen size
part("crown", "cylinder", (0.55, 0.6, h), at, "head", "#5e3424", taper=0.85)
nose = R.at(680, 485, depth=0.35)           # the world point drawn at that pixel, 0.35 toward the camera
```

- `R.pt(x, y)` gives screen units (right of and above the ground point), `R.len(px)` a length.
- `R.at(x, y, depth)` and `R.box(..., depth=)` place a point on the line of sight through that
  pixel. A picture has no depth, so choose it: about 0 for things on the body's centre line, and
  toward the camera (positive) for things on the near surface (a nose, a badge, the near arm).
- Sizes are in world axes (x forward, y left, z up), not screen axes. In a front view the screen
  width of a part is its y size; in a three-quarter view it mixes x and y. Choose the sizes, then let
  `--compare` show whether the part covers the right pixels.
- `R.points(polygon, at)` turns a reference pixel polygon into a `profile` part's points; pass
  `rotate=R.facing` so the flat shape faces the camera. Profiles are the most exact way to match an
  outline: coat tails, capes, hair, ears, hat brims, blades.

## 3. Parts

```python
part(name, shape, size, at, bone, color, bevel=0, taper=1, rotate=(0, 0, 0), segments=10, points=None,
     smooth=0)
mirror("forearm.L")            # creates forearm.R on the mirrored bone
```

**Smooth forms.** `smooth=2` adds a subdivision surface with smooth shading: the shape becomes a
rounded, organic version of itself, the way 3D game characters are box-modelled. Use it for
everything soft: coats, sleeves, trousers, boots, hats, fur, tails, bodies. Add a small `bevel`
(0.03-0.08) to a smoothed box to keep it near its full size; without one it shrinks into a pebble.
Leave hard props (blades, guns, buckles, badges) unsmoothed. Unsmoothed boxes are what make a model
look blocky.

| Shape | Use for |
|---|---|
| `box` | torsos, limbs, belts, boots. Add `bevel` (about 0.02-0.05) to soften corners; `taper` for a frustum |
| `sphere` | heads, hands, muzzles, cheeks, eyes, fluffy volumes (stretch it with a non-uniform size) |
| `dome` | anything with a flat base: slimes, caps, round helmets, hat crowns |
| `cylinder` | arms and legs seen end-on, hat brims, barrels, staffs, shields (rotate so the face points at the camera) |
| `cone` | hats, spikes, horns, scarf points |
| `profile` | flat shapes traced from the reference: blades, capes, coat tails, plumes, ears, hair, tails. `points` are (x, z) in units around `at`, and `size` is the thickness |

- **Match, don't simplify.** Build each region from as many parts as its shape needs: a head is a
  skull plus cheeks plus a muzzle plus ears; a coat is a torso plus lapels plus tails plus sleeves.
  Use segments 12-16 on round parts that are big on screen.
- **Model all around.** Build every part in full 3D, not as a cheat for one view: features go where
  they are on the character (eyes on the front, not both on one side), so any camera angle works.
- **Markings are parts too.** Stripes, patches, eye markings, buttons and badges are thin parts that
  sit just outside the surface they are on (stripes on a tail: slightly larger rings around it).
- **Build parts in the rest pose**, along their bones. Sizes are full extents (x forward, y left,
  z up) and `at` is the centre.
- **Keep everything over 1.5 px thick** in the game view (`1.5 / pixels_per_unit` units). `part()`
  prints a warning when a part is thinner. Thicken thin things (sword blades, whiskers, straps)
  rather than drop them.
- **Layering in depth.** Parts behind the body (capes, tails, far arms) must sit behind it from the
  game view, or they cover it. Parts on the surface must stick out of it, or they are hidden.
- **Props on extra bones.** Weapons go on a `weapon` bone that is a child of the hand, so the
  animation can swing the weapon by rotating the hand.
- **Colours.** Sample flat base colours from the reference. Toon shading adds the light and dark
  tones, so pick the mid tone, not the highlight or the shadow.
- Calling `part()` again with the same name replaces that part. Use it in edit scripts
  ("make the helmet bigger"). `recolor(name, hex)` and `remove(name)` also exist.

**Reusing parts.** `library.load_parts("../../library/parts/great_helm.json", scale=0.9)` adds saved
parts on the bones of the same names, placed relative to each bone, so they fit other proportions.
Save a character's parts with `library.save_parts(path, [names])`.

**Game-ready skins.** Parts are how you build; the finished character should be one sculpted mesh
per region, not parts glued together. `build.smooth_skin(name, parts, voxel, relax, faces, bones)`
fuses the listed parts with a voxel remesh (seams blend into one surface, like sculpting them
together), relaxes and decimates it to a face budget, gives each face the colour of the nearest
part, and skins it to the armature with automatic weights:

```python
smooth_skin("torso_skin", ["coat", "collar", "belt", "coat_back"], voxel=0.018, relax=6, faces=4000,
            bones=["hips", "spine", "chest", "neck"])
```

- Make one skin per region that moves together: head, hat, torso and coat, each arm, each leg, tail.
  Never fuse an arm into the body it hangs against: the voxel remesh welds whatever touches.
- Always pass `bones`, the region's own bones. Automatic weights otherwise let nearby bones pull on
  the skin (raised arms lifting a coat).
- `voxel` about 0.015-0.025 units (smaller keeps more detail), `relax` 4-8, `faces` 2000-6000 per
  region. Parts thinner than about two voxels may break up: leave them out.
- Leave small and hard details out (eyes, noses, brows, markings, badges, buckles, blades, guns,
  thin brims and flat cloth): they stay crisp rigid parts on their bones.
- The parts stay in the .blend, hidden. Edit them with `part()` and call `smooth_skin()` again with
  the same name to rebuild that skin.

## 4. Non-humanoids

Use `rig.custom({"root": (...), "body": (...), ...})` with `root` first, at the origin on the
ground. Describe the bones in `character.json` under `"rig"` so later edits know what each one is
for. Squash and stretch uses `{"scale": (x, y, z)}` keys on a bone whose head is on the ground.

## 5. Review loop

1. `python pp.py preview <character> --compare --turnaround`.
2. Look at `previews/compare.png`: the reference, the model drawn over it, and the two blended, at
   the reference's scale and angle. Every part should cover the same pixels as in the reference.
   Note each place where the outline, a proportion, a feature's position or a colour differs.
3. Look at `previews/turnaround.png`: the game view at 4x and at sprite size, then four sides.
   Check that every feature still reads at sprite size and that nothing pokes through from the sides.
4. Fix with a new edit script that calls `part()` for the parts that change, then preview again.
5. Stop after 5 rounds and report what still differs from the reference.

## 6. Painting a generated mesh

The default pipeline ([generated.md](generated.md)) paints the generated mesh before turning it into the
low-poly model, which takes each triangle's colour from it. A mesh from `pp.py generate` is one lumpy
surface; these keep its colours clean:

- **Flat colours.** Give `model.paint` one colour per material (fur, coat, hat, steel), never a light
  and a dark version of the same one: the toon shader does the shading, and shaded pairs scatter
  speckles over every surface. Markings are not shading: a tail's dark rings get their own colour.
- **Flatten a shaded reference first.** `model.flatten(image, mask, palette, out, shades={...})`
  maps every pixel to its palette colour and takes the majority around it, so shading and outlines
  melt into flat areas; list a material's shading tones that sit nearer another colour under
  `shades` (a vest's shadow tan, a scarf's dark red). Point the reference's `image` at the result.
- **Paint after rigging, by region.** Projection alone paints a tail behind the legs with the
  trousers. `paint(..., bake=False, regions={...}, facing=0.05)` uses the skin weights: each region (a
  bone name or prefix) lists the colours it may take, and fills the faces no view sees from itself
  only. A low `facing` lets grazing faces (a hat's crown) still read the front:

  ```python
  paint(body, B, PALETTE, bake=False, facing=0.05, no_fill=["black", "gold"], regions={
      "tail.": ["fur", "fur_dark", "cream"],
      "head": ["fur", "cream", "black", "hat", "gold"],
      "upper_arm": ["coat"], "hand": ["paw", "coat"], "foot": ["boots"], ...})
  ```

  Every pixel around a sample votes for its nearest allowed colour, so the reference's outlines
  lose. `no_fill` (eyes, nose, badges): unseen faces never take small-feature colours, or one dark
  outline caught under a brim floods the back of the head. Regions whose bones also carry the edge
  of a neighbouring part (the chest under the chin) must allow its colours too.
- **The unseen sides.** Faces no view sees take the colour that wraps around from the silhouette's
  edge in their region (`wrap`), then fill from neighbours. Check every side with `--turnaround` and
  correct with `model.color_faces(obj, rule)` (`rule(center, normal)` returns a colour or None to
  keep), measuring heights and widths on the mesh. Add a `side` or `rear` sheet to `references` when
  the user has one (`view` 0 or 270).
- **Small features** (eyes, buttons, badges) must cover several faces to survive the low-poly
  reduction. Check them in the sprite-size preview; paint them bigger if they vanish.
