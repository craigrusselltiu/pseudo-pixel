"""Pixel post-processing on uint8 RGBA arrays (rows top-down). Pure numpy, so it also runs outside Blender.

Order used by render.py: binarize alpha -> quantize -> despeckle -> outline -> pack.
"""
import os

import numpy as np

# 4-neighbour and 8-neighbour offsets (dy, dx)
N4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
N8 = N4 + ((-1, -1), (-1, 1), (1, -1), (1, 1))


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def load_palette(spec, base_dir="."):
    """A list of hex colours, or a path to a .hex (one rrggbb per line) or .gpl (GIMP) palette."""
    if spec is None:
        return None
    if isinstance(spec, list):
        return np.array([hex_rgb(c) for c in spec], dtype=np.uint8)
    path = os.path.join(base_dir, spec)
    colors = []
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if path.lower().endswith(".gpl"):
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
                colors.append(tuple(int(p) for p in parts[:3]))
    else:
        colors = [hex_rgb(line.strip()) for line in lines if line.strip() and not line.startswith(";")]
    if not colors:
        raise ValueError(f"no colours in palette {path}")
    return np.array(colors, dtype=np.uint8)


def oklab(rgb):
    """uint8 sRGB (..., 3) -> OKLab float (..., 3)."""
    c = rgb.astype(np.float64) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    lms = c @ np.array([[0.4122214708, 0.2119034982, 0.0883024619],
                        [0.5363325363, 0.6806995451, 0.2817188376],
                        [0.0514459929, 0.1073969566, 0.6299787005]])
    return np.cbrt(lms) @ np.array([[0.2104542553, 1.9779984951, 0.0259040371],
                                    [0.7936177850, -2.4285922050, 0.7827717662],
                                    [-0.0040720468, 0.4505937099, -0.8086757660]])


def _blocks(a, s):
    """(h*s, w*s, ...) -> (h, w, s*s, ...): each output pixel's s x s samples."""
    h, w = a.shape[0] // s, a.shape[1] // s
    b = a.reshape(h, s, w, s, *a.shape[2:]).swapaxes(1, 2)
    return b.reshape(h, w, s * s, *a.shape[2:])


def _mode(keys, valid):
    """Index of the most common valid key in each block (keys, valid: (h, w, n))."""
    counts = (keys[..., :, None] == keys[..., None, :]).sum(-1)
    return np.where(valid, counts, 0).argmax(-1)


def _key(rgb):
    return (rgb[..., 0].astype(np.int32) << 16) | (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2]


def downsample(img, s, prev=None, keep=0.25):
    """Supersampled RGBA uint8 (h*s, w*s, 4) -> (h, w, 4). A pixel is opaque when at least half of its
    s x s samples are, and takes their most common colour, so sub-pixel motion only changes a pixel
    when most of it changes.

    prev (the previous animation frame, downsampled) adds hysteresis: a pixel keeps its previous colour
    while that colour still covers `keep` of its samples, and its previous coverage while the share of
    covered samples stays within keep..1-keep. Noise then can't flip pixels back and forth from frame
    to frame, while real motion, which sweeps a colour off its pixels, still moves them."""
    if s == 1:
        return img
    b = _blocks(img, s)
    valid = b[..., 3] >= 128
    keys = _key(b)
    out = np.take_along_axis(b, _mode(keys, valid)[..., None, None], axis=2)[:, :, 0].copy()
    cover = valid.mean(-1)
    opaque = cover >= 0.5
    if prev is not None:
        was = prev[..., 3] > 0
        opaque = np.where(was, cover >= keep, cover > 1 - keep)
        share = ((keys == _key(prev)[..., None]) & valid).mean(-1)
        stay = was & (share >= keep)
        out[stay, :3] = prev[stay, :3]
    out[..., 3] = np.where(opaque, 255, 0)
    out[~opaque, :3] = 0
    return out


def downsample_ids(ids, depth, s, opaque=None):
    """Supersampled (object ids, depth) -> the most common id of each pixel's hit samples and its
    nearest depth; misses are id 0, depth inf. A pixel is hit where `opaque` (the downsampled colour
    frame's coverage) says so, or else where half its samples are."""
    if s == 1:
        return ids, depth
    bi, bd = _blocks(ids, s), _blocks(depth, s)
    valid = bi > 0
    pick = np.take_along_axis(bi, _mode(bi, valid)[..., None], axis=2)[..., 0]
    hit = (valid.mean(-1) >= 0.5) if opaque is None else opaque & valid.any(-1)
    d = np.where(bi == pick[..., None], bd, np.inf).min(-1)
    return np.where(hit, pick, 0).astype(np.int32), np.where(hit, d, np.inf)


def binarize_alpha(img):
    img = img.copy()
    opaque = img[..., 3] >= 128
    img[..., 3] = np.where(opaque, 255, 0)
    img[~opaque, :3] = 0
    return img


def quantize(img, palette):
    """Map every opaque pixel to the nearest palette colour in OKLab."""
    img = img.copy()
    opaque = img[..., 3] > 0
    src = img[opaque, :3]
    uniq, inv = np.unique(src, axis=0, return_inverse=True)
    d = ((oklab(uniq)[:, None, :] - oklab(palette)[None, :, :]) ** 2).sum(-1)
    img[opaque, :3] = palette[d.argmin(1)][inv.ravel()]
    return img


def _shift(a, dy, dx, fill):
    """a shifted so out[y, x] = a[y + dy, x + dx]; out-of-range cells get `fill`."""
    out = np.full_like(a, fill)
    h, w = a.shape[:2]
    ys, yd = (slice(dy, h), slice(0, h - dy)) if dy >= 0 else (slice(0, h + dy), slice(-dy, h))
    xs, xd = (slice(dx, w), slice(0, w - dx)) if dx >= 0 else (slice(0, w + dx), slice(-dx, w))
    out[yd, xd] = a[ys, xs]
    return out


def _keys(img):
    """One int per pixel identifying its RGBA value (transparent pixels all share key 0)."""
    k = img.astype(np.int64)
    return np.where(k[..., 3] > 0, (k[..., 0] << 24) | (k[..., 1] << 16) | (k[..., 2] << 8) | 255, 0)


def despeckle(img):
    """Replace opaque pixels that share their colour with none of their 8 neighbours.

    They take the most common colour among their opaque 4-neighbours (ties go to the first in N4
    order), or become transparent if they have none. 8-neighbour isolation keeps 1 px diagonal lines.
    """
    keys = _keys(img)
    opaque = keys != 0
    isolated = opaque.copy()
    for dy, dx in N8:
        isolated &= _shift(keys, dy, dx, -1) != keys
    if not isolated.any():
        return img
    out = img.copy()
    nbrs = [_shift(img, dy, dx, 0) for dy, dx in N4]
    nkeys = [_keys(n) for n in nbrs]
    for y, x in zip(*np.nonzero(isolated)):
        cands = [k[y, x] for k in nkeys if k[y, x] != 0]
        if not cands:
            out[y, x] = 0
            continue
        best = max(cands, key=cands.count)
        out[y, x] = nbrs[[k[y, x] for k in nkeys].index(best)][y, x]
    return out


def outline(img, color, ids=None, depth=None, threshold=1.0):
    """1 px outline in `color` (hex).

    Outer: transparent pixels 4-adjacent to opaque ones. Inner (when ids and depth are given): opaque
    pixels with a 4-neighbour on a different part that is closer to the camera by more than
    `threshold` (same units as depth), so the farther part carries the line.
    """
    rgba = np.array(hex_rgb(color) + (255,), dtype=np.uint8)
    opaque = img[..., 3] > 0
    mask = np.zeros_like(opaque)
    for dy, dx in N4:
        mask |= ~opaque & _shift(opaque, dy, dx, False)
    if ids is not None and depth is not None:
        for dy, dx in N4:
            nid = _shift(ids, dy, dx, 0)
            ndepth = _shift(depth, dy, dx, np.inf)
            mask |= opaque & (nid != ids) & (nid != 0) & (ndepth < depth - threshold)
    out = img.copy()
    out[mask] = rgba
    return out


def touches_edge(img):
    """True if any opaque pixel is on the top, left or right edge. The bottom row is the ground line."""
    a = img[..., 3] > 0
    return bool(a[0].any() or a[:, 0].any() or a[:, -1].any())


def pack(frames, columns=None):
    """Frames left to right in one row, or in a grid `columns` wide. Returns (sheet, [(x, y)])."""
    h, w = frames[0].shape[:2]
    cols = min(columns or len(frames), len(frames))
    rows = -(-len(frames) // cols)
    sheet = np.zeros((rows * h, cols * w, 4), dtype=np.uint8)
    pos = []
    for i, f in enumerate(frames):
        x, y = (i % cols) * w, (i // cols) * h
        sheet[y:y + h, x:x + w] = f
        pos.append((x, y))
    return sheet, pos


# --- review sheets -------------------------------------------------------------------------------

FONT = {  # 3x5 bitmap glyphs, rows top to bottom
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111",
    "4": "101101111001001", "5": "111100111001111", "6": "111100111101111", "7": "111001010010010",
    "8": "111101111101111", "9": "111101111001111", "x": "000101010101000", " ": "000000000000000",
    "-": "000000111000000",
}


def text(s, color=(255, 255, 255, 255), scale=2):
    """Render a string of digits, 'x', '-' and spaces as an RGBA image."""
    glyphs = [np.array([int(c) for c in FONT[ch]], dtype=bool).reshape(5, 3) for ch in s]
    mask = np.zeros((5, max(1, 4 * len(s) - 1)), dtype=bool)
    for i, g in enumerate(glyphs):
        mask[:, 4 * i:4 * i + 3] = g
    mask = mask.repeat(scale, 0).repeat(scale, 1)
    out = np.zeros(mask.shape + (4,), dtype=np.uint8)
    out[mask] = color
    return out


def _paste(dst, src, x, y):
    """Alpha-over src onto dst at (x, y), clipped to dst."""
    h, w = src.shape[:2]
    h, w = min(h, dst.shape[0] - y), min(w, dst.shape[1] - x)
    if h <= 0 or w <= 0:
        return
    s = src[:h, :w]
    a = s[..., 3:4] > 0
    dst[y:y + h, x:x + w] = np.where(a, s, dst[y:y + h, x:x + w])


def contact_sheet(cells, labels, scale=4, columns=8):
    """Frames upscaled by `scale` (nearest) on a checkerboard, each with a text label above it."""
    h, w = cells[0].shape[0] * scale, cells[0].shape[1] * scale
    pad, lab = 4, 14
    cols = min(columns, len(cells))
    rows = -(-len(cells) // cols)
    sheet = np.zeros((rows * (h + lab + pad) + pad, cols * (w + pad) + pad, 4), dtype=np.uint8)
    sheet[...] = (40, 40, 48, 255)
    yy, xx = np.mgrid[0:h, 0:w]
    checker = np.where((((yy // 8) + (xx // 8)) % 2 == 0)[..., None],
                       np.array((150, 150, 160, 255), np.uint8), np.array((120, 120, 130, 255), np.uint8))
    for i, (cell, label) in enumerate(zip(cells, labels)):
        x = pad + (i % cols) * (w + pad)
        y = pad + (i // cols) * (h + lab + pad)
        _paste(sheet, text(label), x, y)
        bg = checker.copy()
        _paste(bg, cell.repeat(scale, 0).repeat(scale, 1), 0, 0)
        sheet[y + lab:y + lab + h, x:x + w] = bg
    return sheet


def stats(frames):
    """Text checks for a list of frames: colours used and the opaque bounding box in pixels."""
    colors = set()
    height = width = 0
    for f in frames:
        a = f[..., 3] > 0
        colors |= {tuple(c) for c in f[a][:, :3].tolist()}
        if a.any():
            ys, xs = np.nonzero(a)
            height = max(height, ys.max() - ys.min() + 1)
            width = max(width, xs.max() - xs.min() + 1)
    return {"colors": len(colors), "height": int(height), "width": int(width)}
