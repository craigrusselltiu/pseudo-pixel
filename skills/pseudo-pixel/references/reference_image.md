# Making the reference image

TripoSG builds the mesh from one image, and paint colours it from the same image, so the image decides
most of the result. A pixel-art sprite, a character in an action pose, a busy scene or a flat line drawing
makes a poor mesh: pixel stair-steps and dithering come out as bumps and grain on the surface (the
"static" that survives into the low-poly model), limbs drawn across the body fuse into it, and foreshortened
parts come out squashed. When the user has no clean image of the subject, or only one of those, make one
with an image model first: a clean, neutral model sheet of the subject that the generator can read.

## 1. The brief

Gather what the subject is before writing the prompt:

- **Name and setting**: what it is, the world and place it lives in (a desert outlaw, a swamp creature, a
  sci-fi drone), the period and the tone.
- **What it does**: its moves and animations. They decide which parts must exist and be separate: a
  claw swipe needs claws clear of the body, a wing beat needs full wings, a sword attack a sword held
  away from the legs, a bite a jaw.
- **Any existing art**: an old sprite or a sketch, as a guide to design and colours (pass it to the image
  model as an input image, not as the thing to copy pose for pose).
- **The user's notes**, if they gave any: colours, clothes, props, build, mood. They override the
  rest.

From these, decide the design in a few lines: silhouette and proportions, the main materials and their
colours (a few clear blocks), props, and the two or three features that make it recognisable at sprite
size. Small sprites read through chunky shapes: a larger head, hands, feet and props than life, no thin
dangling parts.

## 2. The prompt

Write the prompt from the design and these rules. Each one is there because the generator or the rig
needs it:

| Rule | Why |
|---|---|
| One subject, the whole of it in frame with a margin, nothing else | the cutout and the mesh are of everything in the image |
| Straight front view at the subject's mid height, little perspective | the generator treats the image as a front view; paint projects it straight on |
| Neutral rest pose: a person in an A-pose (arms 30-45 degrees down and clear of the body, legs a little apart, feet flat); four legs standing, all visible and apart; wings spread out to the sides; tails and necks held out, not curled behind | parts drawn against the body fuse into it; the rest pose is where every animation starts |
| Props held clear of the body, in full | a sword across the legs becomes part of the legs |
| Flat, even, frontal light; no cast shadows, rim light, glow, bloom or reflections | painted light and shadow end up as colours on the model; the renderer shades it instead |
| Matte materials in a few solid colour blocks, crisp borders between them | each block becomes one palette colour; gradients and texture become speckle |
| A clean stylised 3D render or painted look, not pixel art, line art or a photo | pixel edges and line strokes become surface noise |
| Transparent background (or plain white), no ground, no shadow under it | the cutout is clean without fixing it by hand |
| Square, 1024 px or larger, no text, logos, borders or effects (motion lines, sparks, smoke) | effects become geometry |

A template, filled in from the brief:

```
Full-body character model sheet of <subject: what it is, build, notable features>, from <setting>.
<Clothing, gear and props, each with its colour and material>. <Two or three recognisable features>.
Straight front view, orthographic, camera at mid height. Neutral rest pose: <the pose for its body
type, from the table>, <props> held clear of the body. Whole body in frame with a margin.
Stylised low-detail 3D game character, chunky readable proportions, matte materials, a few solid
colour blocks with crisp borders. Flat even frontal lighting, no shadows, no rim light, no glow.
Transparent background, no ground. No text, no effects.
```

## 3. Generating it

- **With an image tool** (an image model you can call, such as GPT Image): generate with the prompt at
  1024x1024 or larger with a transparent background, and the existing art as an input image when there
  is some. Make two to four candidates and pick the one that best follows the rules in the checklist
  below; regenerate with a corrected prompt if none does.
- **Without one**: give the user the prompt (and say which existing image to attach), and wait for them
  to bring back the image from whatever generator they use. Don't continue without it.

Check the image before using it:

- one subject, whole, with a margin; a clean background;
- front view, rest pose, limbs and props clear of the body with background showing between them;
- no painted shadows or highlights strong enough to read as a second colour;
- every part the moves need, with no thin part under about 1/40 of the subject's height;
- the design matches the brief and the user's notes.

Then it is the character's reference: `pp.py new <char_dir> <image>` and `pp.py generate` as usual
(generated.md). A transparent image is used as its own cutout.

## 4. More views for colouring (optional)

Paint colours what the front shows and guesses the rest. A side and a back view of the same design make
the guess unnecessary. With an image tool, edit the front image into each view ("the same character,
same design, colours, scale and position on the canvas, in exact profile facing the right edge of the
image / seen exactly from behind, same rest pose, same lighting and background"). Check that the design really is the same (colours,
props, markings); a view that differs is worse than none.

Each view must line up with the front: same canvas size, the subject the same height, its feet on the
same row. Cut it out, scale it so its top and ground rows match the front's (`reference_scale` in
`character.json`), and place it on a canvas of the front's size. Save it in the character's `analysis/`
folder with a mask (opaque where the subject is) and add it to `references`:

```json
{"image": "analysis/side.png", "mask": "analysis/side_mask.png", "view": 0, "center": <its centre column>}
```

`view` is 0 for the right side (the profile facing the image's right edge) and 270 for the back (90 is
the front). `paint` then colours each face
from the view it faces most (modelling.md, section 6).
