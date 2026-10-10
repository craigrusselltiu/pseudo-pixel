# Render settings

Render settings live in the character's `character.json` under `output`, and each animation can
override them in its own entry (`"attack": {"loop": false, "frame": [96, 64]}`). Changing them only
needs `pp.py render`. `pp.py new` writes the PS1 look (the values in the second column where they
differ from the renderer's defaults).

| Key | `pp.py new` (renderer default) | Meaning |
|---|---|---|
| `frame` | `[64, 64]` (required) | Frame size in pixels, `[w, h]` |
| `pixels_per_unit` | `17` (required) | Scale: pixels per Blender unit, the same for every animation |
| `fps` | `12` (required) | Sprite frame rate: how many frames are sampled per second of animation (the Blender timeline runs at 24 fps) |
| `anchor` | `[32, 52]` (renderer: `"bottom-center"`) | Pixel the root's ground position maps to: `bottom-center`, `center`, `bottom-left`, or `[x, y]`. Raise it from the bottom when the camera looks down: parts toward the camera draw below the ground point |
| `shading_steps` | `5` (renderer: `4`) | Toon tones per material (`1` is flat colour) |
| `dither` | `0.6` (renderer: `0.35`) | Ordered (Bayer) dithering between neighbouring tones: `0` is hard bands, `1` dithers across each whole band |
| `hue_shift` | `0.15` (renderer: `0.5`) | How far darker tones lean cool (blue-purple) and the lit tone warm; `0` keeps every tone the base hue |
| `light` | `[-1, -0.6, 0.7]` (renderer: `[-1, -1, 1]`) | Direction toward the key light, relative to the camera (+x screen right, -y toward the camera, +z up) |
| `palette` | none | List of hex colours, or a `.hex` / `.gpl` file relative to the character folder |
| `despeckle` | `false` | Remove isolated single pixels |
| `outline` | none | `{"color": "#1a1c2c", "mode": "outer" or "inner", "depth": 1}`; `inner` also draws lines between overlapping parts |
| `columns` | one row | Frames per row in the sheet |
| `merge_holds` | `false` | Merge identical consecutive frames into one frame with a longer duration |
| `supersample` | `4` (renderer: `1`) | Samples per pixel along each axis. Each pixel takes its dominant colour and keeps it from frame to frame until a new colour clearly takes over, so pixels stop flickering as the model moves |
| `normals` | `false` | Also write a normal-map sheet (`<name>_n.png`, OpenGL convention) for lighting sprites in the engine |
| `views` | 8 directions (renderer: `[0]`) | Camera angles in degrees around the character: 0 its right side (facing screen right), 90 its front, 180 its left side, 270 its back. More than one writes `<name>_<angle>` sheets; a `{name: angle}` object names them: `{"S": 90, "SE": 45, "E": 0, "NE": 315, "N": 270, "NW": 225, "W": 180, "SW": 135}` writes `idle_S`, `idle_SE`, ... |
| `elevation` | `30` (renderer: `0`) | Camera height in degrees: how far it looks down on the character |
| `loop` | `false` | Per animation: the last frame repeats the first and is left out |

Common changes: a side-view platformer is `"views": [0], "elevation": 0`; a classic pixel-art look is
`"shading_steps": 4, "dither": 0.35, "hue_shift": 0.5, "outline": {"color": "#1a1c2c", "mode": "inner"}`;
bigger sprites are a larger `frame` and `pixels_per_unit` together.
