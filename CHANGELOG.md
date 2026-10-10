# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## v0.5.2 - 2026-10-10

### Fixed

- `pp.py generate` on a cleaner cutout updates the reference's mask and centre line (it kept the first
  run's), and the skill says to check the cutout and how to make a clean one when the background left
  something behind.

## v0.5.1 - 2026-10-10

### Changed

- The skill covers any subject (characters, creatures, vehicles, props), not only humanoids: rigging
  what moves, and colouring as a general method (paint, review all 8 views, fix every wrong patch with
  measured `color_faces` rules in one complete paint script, review again on the low-poly model).
- A face's part, for `paint` regions, `stripes` and `lowpoly` tubes, is its weighted bone unless the face
  looks toward that bone (another part's surface pressed against a limb, which automatic weights give
  to the limb); then it is the nearest bone it looks away from.

### Fixed

- `model.lowpoly` works on rigs without a head bone (one zone with the whole budget).

## v0.5.0 - 2026-10-10

The generated PS1 low-poly pipeline is now the default: reference -> TripoSG mesh -> rig -> paint ->
low-poly model -> animations -> spritesheets.

### Added

- `model.lowpoly()`: turns a rigged, painted generated mesh into a PS1-style low-poly model (about 1400
  triangles by zone budget, one flat colour per triangle, weights from the generated mesh, which stays
  hidden as the guide); `tubes` rebuilds tails and other long round parts as striped 8-sided tubes.
- `model.centre()` and `model.front()`: place joints in the middle of the mesh's cross-section.
- `model.limb_weights()`: frees limbs a generated mesh fused to the body (arms against a coat) and
  weights each to its own bones.
- `model.cut()`: removes a generated prop and closes the hole, for a modelled low-poly one.
- `model.stripes()`: paints rings around a tail (or any part on a bone chain).
- `pp.py generate` cuts the character out of the reference itself (RMBG-1.4), measures the silhouette
  into `character.json` (`reference_scale` and `references`), and defaults to the character's reference.
- `skills/pseudo-pixel/references/generated.md` (the pipeline step by step) and `render.md` (every render
  setting).

### Changed

- `pp.py new` writes the PS1 look: 8 directions from 30 degrees above, 5 dithered tones, no outline,
  supersampled.
- `model.import_mesh` stands the mesh with the point between its feet on the origin (not its bounding
  box's centre) and drops loose fragments.
- `model.paint` gives faces no view sees the colour that wraps around from the silhouette's edge of their
  region before filling from neighbours.
- `model.color_faces` keeps a face's colour when its rule returns None.
- `rig.add_foot_ik` also bends knees fitted behind the hip-to-ankle line forward.
- `anim.import_action` reads relative paths from the character's folder.
- The skill and README are rewritten around the pipeline; the README is a short guide to using it.

### Removed

- `PLAN.md`, `examples/test` and the README's knight image.

## v0.4.0 - 2026-10-09

### Added

- `pp.py generate <char> <image>`: the character's mesh from one image with TripoSG (MIT), an
  open-weight image-to-3D model, on the local GPU, via `pp/gen_triposg.py` in its own Python environment.
- `pp/model.py`: `import_mesh` (any GLB/FBX/OBJ: facing +x, scaled, grounded, decimated), `paint` (flat
  colour regions projected from reference sheets, unseen faces filled from neighbours, speckles
  cleaned), `Blueprint` (front/side/rear sheets with silhouette spans), `loft` and `ring`.
- `"references"` in `character.json` for model sheets; `pp.py preview --compare` then compares every view.
- `supersample` output setting: renders n x n samples per pixel and keeps each pixel's dominant colour,
  with frame-to-frame hysteresis in animations, so pixels stop flickering as the model moves.
- `model.smooth_normals()`: shades a lumpy mesh with the normals of a smoothed copy, for clean toon bands.
- `model.paint` regions: on a rigged mesh, each body region (by skin weights) lists the colours it
  may take and which sheets paint it, and unseen faces fill only from their own region; `facing` sets
  how squarely a face must point at a view to be painted from it.
- `model.flatten()`: flattens a shaded reference into flat palette areas (with `shades` for a
  material's shading tones) to paint from; `model.paint(no_fill=...)` keeps small-feature colours
  (eyes, badges) from filling unseen faces.
- `model.color_faces()`: colours a mesh polygon by polygon from a rule, for low-poly characters coloured
  per polygon (as PS1 models like Crash Bandicoot were) instead of textured.
- `model.auto_weights()`: automatic weights for generated meshes, computed on a watertight copy at 10x
  scale (bone heat weighting otherwise fails on them and leaves every vertex unweighted).
- `anim.aim()`: the rotation that points a bone's prop (a blade, a barrel) in a world direction, with an
  optional up direction to keep it level.
- `viewer/view.bat`: double-click to rebuild the viewer and open it (Windows).
- Named views: `views` can be `{name: angle}` (for example `{"S": 90, "E": 0, ...}` for 8-direction
  sprites), and sheets are then named `<anim>_<name>`.
- `pp.py preview --view NAME`: animation previews from another of the character's views.
- The viewer groups `<anim>_<direction>` sheets into one animation with a compass to pick the direction.

### Changed

- `model.paint` skips views that can't see a face (it painted a tail hidden behind the legs with the
  trousers), lets every pixel of a sample vote for its nearest colour (outlines no longer turn into
  black and brown speckles) and fills unseen faces ring by ring.
- The skill stops for the user's approval after the shape, after the colours and before rendering
  (human checkpoints), until the user says to skip them.
- `build.part` places parts in the rest pose even when an action is posing the armature (parts added
  after animating landed offset).
- `pp.py preview --anim` takes several names (`--anim walk hit`); it used to keep only the first.
- Animation guidance: calm idles (one slow breath, at most one weight shift), few strong eased poses,
  motion in whole pixels, a steady head, secondary parts that don't pop in and out of the silhouette.
- Modelling guidance for generated meshes: flat colours, a flat material map for photo references,
  smooth normals and supersampling.

## v0.3.0 - 2026-10-08

### Added

- Foot IK: `rig.add_foot_ik()` adds planted foot controls and knee poles; actions that key them use IK
  for that leg, others stay FK.
- Game-ready skins: `build.smooth_skin()` takes `voxel`, `relax`, `faces` and `bones` to fuse parts into
  one remeshed, decimated surface per region, keep each part's colour, and limit its skin weights to
  the region's bones.

### Changed

- The skill builds fused skins after modelling and animates with planted feet, weight shifts and
  overlap; idle guidance describes an active stance instead of breathing alone.
- The humanoid and knight idles keep their feet planted with foot IK.

## v0.2.0 - 2026-10-07

### Added

- `views` and `elevation` render sprites from the reference's own camera angle, and the light turns
  with the camera.
- `reference_scale` in `character.json`; `build.Ref()` reads it and measures in the reference's view
  (`R.at`, `R.facing` for profile parts that face the camera).
- `pp.py preview --compare`: the model drawn over the reference at the reference's scale and angle.
- `pp.py view`: finds every sheet in `characters/*/out` and `examples/*/out` and opens them in a
  static viewer (`viewer/index.html`) with speed, zoom, stepping, looping, root motion and backgrounds.
- `merge_holds` output option.
- Dithered, hue-shifted toon shading: `dither` (ordered Bayer dithering between tones) and
  `hue_shift` (cool shadows, warm light).
- `smooth` on `build.part()`: subdivision surface with smooth shading, for organic and cloth shapes.
- Examples in four perspectives: side view (knight), battle view (humanoid), 45 degrees from above
  (mage) and 2:1 isometric (slime).
- `characters/` and `library/` are git-ignored in this repository.

### Changed

- Animations are smooth 3D keyframe animation (Bezier by default, cyclic loops) on a 24 fps timeline,
  sampled at the sprite `fps`: a sheet has one frame per `1 / fps` seconds of animation.
- Changing `fps` is a render-only change; the timeline no longer follows it.
- `anim.retime(factor, names)` stretches action timing instead of converting between frame rates.
- New characters default to 64x64 frames at 32 pixels per unit, with 4 toon tones.
- One view writes `<name>.png` whatever its angle; several write `<name>_<angle>.png`.
- The skill models to match the reference as closely as possible instead of keeping models simple,
  and reviews up to 5 rounds.
- Thin-part checks measure in the game view.
- `pp.py inspect` reports `timeline_fps`.
- Example animations converted to the 24 fps timeline.

### Removed

- `expand_holds` (every sampled frame is now its own frame by default).

## v0.1.0 - 2026-10-07

### Added

- Render pipeline, rig and animation helpers, modelling helpers, the agent skill, examples, normal
  maps, extra views, parts and actions library, leg IK, smooth skinning and agent packaging.
