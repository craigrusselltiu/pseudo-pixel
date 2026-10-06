"""Slime: a non-humanoid on a two-bone custom rig.

Measured from reference.png: base centre at (128, 206), top of the dome at y=90, 0.9 units tall.
Only the side view is rendered, so both eyes sit on the near side where the reference draws them.
"""
import rig
from build import Ref, part

R = Ref(ground=(128, 206), top=90, height=0.9)
GOO, GOO_D, EYE, SHINE = "#6ec85a", "#3c8c46", "#1a1c2c", "#fafaf0"

rig.custom({"root": ((0, 0, 0), (0, 0, 0.2), None),
            "body": ((0, 0, 0), (0, 0, 0.6), "root")})

_, (sx, sz) = R.box(40, 90, 216, 194)
a, b, c, d = sx / 2, sx * 0.375, 0.1, sz  # dome half-sizes and base height


def near_surface(x, z):
    """y of the dome's near (camera-side) surface above (x, z), so features sit on it."""
    t = 1 - (x / a) ** 2 - ((z - c) / d) ** 2
    return -b * max(t, 0) ** 0.5


part("dome", "dome", (2 * a, 2 * b, d), (0, 0, c + d / 2), "body", GOO, segments=16)
part("base", "cylinder", (2 * a + 0.04, 2 * b + 0.04, 0.1), (0, 0, 0.05), "body", GOO_D, segments=16)
for x in (159, 191):
    ex, ez = R.pt(x, 148)
    part(f"eye{x}", "sphere", (0.15, 0.1, 0.2), (ex, near_surface(ex, ez), ez), "body", EYE, segments=8)
hx, hz = R.pt(85, 121)
part("shine", "sphere", (0.24, 0.08, 0.13), (hx, near_surface(hx, hz), hz), "body", SHINE, segments=8)
