"""Slime: a non-humanoid on a two-bone custom rig.

Measured from reference.png: base centre at (128, 206), top of the dome at y=90, 0.9 units tall.
Built for any angle: the eyes sit on the front, the shine on top.
"""
import rig
from build import Ref, part

R = Ref(ground=(128, 206), top=90, height=0.9, yaw=0, elevation=0)  # the reference is a side view
GOO, GOO_D, EYE, SHINE = "#6ec85a", "#3c8c46", "#1a1c2c", "#fafaf0"

rig.custom({"root": ((0, 0, 0), (0, 0, 0.2), None),
            "body": ((0, 0, 0), (0, 0, 0.6), "root")})

_, (sx, sz) = R.box(40, 90, 216, 194)
a, b, c, d = sx / 2, sx * 0.375, 0.1, sz  # dome half-sizes and base height


part("dome", "dome", (2 * a, 2 * b, d), (0, 0, c + d / 2), "body", GOO, segments=16)
part("base", "cylinder", (2 * a + 0.04, 2 * b + 0.04, 0.1), (0, 0, 0.05), "body", GOO_D, segments=16)
# Eyes on the front of the dome, where the reference's side view shows them, so they read from any
# angle that sees the slime's face (its isometric game view looks at it from the front-left)
_, ez = R.pt(0, 148)
for side in (1, -1):
    ey = side * 0.13
    ex = a * max(1 - (ey / b) ** 2 - ((ez - c) / d) ** 2, 0) ** 0.5
    part(f"eye.{'L' if side > 0 else 'R'}", "sphere", (0.1, 0.13, 0.2), (ex, ey, ez), "body", EYE, segments=8)
part("shine", "sphere", (0.2, 0.2, 0.1), (-0.05, 0.12, c + d * 0.93), "body", SHINE, segments=8)
