"""Tests for pp/post.py. Needs only numpy: python -m unittest discover tests"""
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pp"))
import post  # noqa: E402

RED, BLUE, CLEAR = (255, 0, 0, 255), (0, 0, 255, 255), (0, 0, 0, 0)


def img(rows):
    """Build an RGBA image from strings: '.' clear, 'r' red, 'b' blue."""
    lut = {".": CLEAR, "r": RED, "b": BLUE}
    return np.array([[lut[c] for c in row] for row in rows], dtype=np.uint8)


def chars(a):
    lut = {CLEAR: ".", RED: "r", BLUE: "b", (0, 0, 0, 255): "o"}
    return ["".join(lut[tuple(int(v) for v in p)] for p in row) for row in a]


class PostTest(unittest.TestCase):
    def test_binarize_alpha(self):
        a = np.array([[[10, 20, 30, 127], [10, 20, 30, 128]]], dtype=np.uint8)
        self.assertEqual(post.binarize_alpha(a).tolist(), [[[0, 0, 0, 0], [10, 20, 30, 255]]])

    def test_quantize_picks_nearest_and_keeps_clear(self):
        pal = np.array([[0, 0, 0], [255, 255, 255], [200, 30, 30]], dtype=np.uint8)
        a = np.array([[[250, 240, 245, 255], [180, 40, 50, 255], [9, 9, 9, 0]]], dtype=np.uint8)
        out = post.quantize(a, pal)
        self.assertEqual(out[0, :, :3].tolist(), [[255, 255, 255], [200, 30, 30], [9, 9, 9]])

    def test_load_palette_formats(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "p.hex"), "w") as f:
                f.write("ff0000\n00ff00\n")
            with open(os.path.join(d, "p.gpl"), "w") as f:
                f.write("GIMP Palette\nName: x\n#\n255   0   0\tRed\n  0   0 255\tBlue\n")
            self.assertEqual(post.load_palette("p.hex", d).tolist(), [[255, 0, 0], [0, 255, 0]])
            self.assertEqual(post.load_palette("p.gpl", d).tolist(), [[255, 0, 0], [0, 0, 255]])
        self.assertEqual(post.load_palette(["#010203"]).tolist(), [[1, 2, 3]])
        self.assertIsNone(post.load_palette(None))

    def test_despeckle(self):
        a = img(["rrrr",
                 "rbrr",
                 "rrrr",
                 "...b"])
        self.assertEqual(chars(post.despeckle(a)), ["rrrr", "rrrr", "rrrr", "...r"])

    def test_despeckle_keeps_diagonal_lines(self):
        a = img(["b...",
                 ".b..",
                 "..b."])
        self.assertEqual(chars(post.despeckle(a)), ["b...", ".b..", "..b."])

    def test_despeckle_removes_floating_pixel(self):
        self.assertEqual(chars(post.despeckle(img(["...", ".r.", "..."]))), ["...", "...", "..."])

    def test_outer_outline(self):
        a = img(["....",
                 ".rr.",
                 "...."])
        self.assertEqual(chars(post.outline(a, "#000000")), [".oo.", "orro", ".oo."])

    def test_inner_outline_on_far_part(self):
        a = img(["rrbb"])
        ids = np.array([[1, 1, 2, 2]])
        far = np.array([[10.0, 10.0, 5.0, 5.0]])  # blue is 5 px closer
        self.assertEqual(chars(post.outline(a, "#000000", ids, far)), ["robb"])
        near = np.array([[10.0, 10.0, 9.5, 9.5]])  # within threshold: no line
        self.assertEqual(chars(post.outline(a, "#000000", ids, near)), ["rrbb"])

    def test_touches_edge_ignores_ground_row(self):
        self.assertFalse(post.touches_edge(img(["...", "...", ".r."])))
        self.assertTrue(post.touches_edge(img([".r.", "...", "..."])))
        self.assertTrue(post.touches_edge(img(["...", "r..", "..."])))

    def test_pack_grid(self):
        frames = [np.full((2, 3, 4), i, dtype=np.uint8) for i in range(5)]
        sheet, pos = post.pack(frames, columns=2)
        self.assertEqual(sheet.shape, (6, 6, 4))
        self.assertEqual(pos, [(0, 0), (3, 0), (0, 2), (3, 2), (0, 4)])
        self.assertEqual(sheet[4, 0, 0], 4)
        self.assertEqual(post.pack(frames)[0].shape, (2, 15, 4))

    def test_text(self):
        t = post.text("1x", scale=1)
        self.assertEqual(t.shape, (5, 7, 4))
        self.assertEqual((t[..., 3] > 0)[:, 1].tolist(), [True] * 5)  # the 1's stem

    def test_contact_sheet_layout(self):
        cells = [img(["r.", ".r"])] * 3
        sheet = post.contact_sheet(cells, ["0", "1", "2 x3"], scale=4, columns=2)
        # 2 columns of 8 px cells with 4 px padding; 2 rows of 14 px label + 8 px cell + 4 px padding
        self.assertEqual(sheet.shape, (2 * (14 + 8 + 4) + 4, 2 * (8 + 4) + 4, 4))
        self.assertEqual(tuple(sheet[4 + 14, 4]), RED)  # first cell's top-left pixel, upscaled

    def test_stats(self):
        s = post.stats([img(["r..", "rb.", "..."]), img(["...", "...", "bbb"])])
        self.assertEqual(s, {"colors": 2, "height": 2, "width": 3})


if __name__ == "__main__":
    unittest.main()
