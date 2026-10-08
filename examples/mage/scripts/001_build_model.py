"""Mage: robe over hidden legs, a cape, a pointed hat and a staff with a gem. Rendered from above
(views [45], elevation 45: the mage faces south-east), so the robe and cape are soft 3D shapes.

Measured from reference.png: robe bottom centre at (124, 232), hat tip at y=2, 1.8 units tall
overall. The humanoid's height is the top of the face, since the hat sits on top of the head.
"""
import rig
from build import Ref, mirror, part

R = Ref(ground=(124, 232), top=2, height=1.8, yaw=0, elevation=0)  # the reference is a side view
ROBE, CAPE, SKIN, HAT, WOOD, GEM = "#604696", "#3c2c64", "#e8ba96", "#463478", "#825a32", "#5adcd2"

face_top = R.pt(0, 44)[1]
arm = rig.humanoid(height=face_top, head=(face_top - R.pt(0, 90)[1]) / face_top, legs=0.42, arms=0.42,
                   shoulders=0.13)
b = arm.data.bones

at, (sx, sz) = R.box(104, 44, 150, 90)
part("face", "sphere", (sx, 0.34, sz), at, "head", SKIN, segments=10)
at, (sx, sz) = R.box(92, 2, 162, 54)
part("hat", "cone", (sx * 0.8, sx * 0.8, sz), (at[0] - 0.05, 0, at[2]), "head", HAT, rotate=(0, -20, 0),
     segments=10)
at, (sx, sz) = R.box(88, 50, 166, 60)
part("brim", "cylinder", (sx * 0.85, sx * 0.8, 0.08), (at[0] - 0.05, 0, at[2] + 0.02), "head", HAT,
     rotate=(0, -18, 0), segments=12)  # tilted back so the face shows from above

# Robe: a tapered top on the chest and a flared skirt on the hips, covering the legs
at, (sx, sz) = R.box(98, 80, 150, 152)
part("robe_top", "box", (sx, 0.4, sz), at, "chest", ROBE, taper=0.85, bevel=0.03, smooth=2)
at, (sx, sz) = R.box(88, 150, 162, 232)
part("skirt", "box", (sx, 0.5, sz), at, "hips", ROBE, taper=0.7, rotate=(180, 0, 0), bevel=0.03,
     smooth=2)  # wide at the bottom

# Cape hangs from the shoulders behind the body: a soft, thin panel widening toward the hem, tilted back
top, bottom = R.pt(0, 80)[1], R.pt(0, 232)[1]
part("cape", "box", (0.1, 0.62, top - bottom), (-0.24, 0, (top + bottom) / 2), "chest", CAPE, taper=0.7,
     rotate=(0, 10, 0), bevel=0.03, smooth=2)

# Arms hang in the rest pose; the idle animation raises the near forearm to hold the staff out
y = b["upper_arm.L"].head_local.y
sh, el, wr = (b[n].head_local.z for n in ("upper_arm.L", "forearm.L", "hand.L"))
part("upper_arm.L", "box", (0.14, 0.13, sh - el + 0.04), (0, y, (sh + el) / 2), "upper_arm.L", ROBE)
part("forearm.L", "box", (0.13, 0.12, el - wr), (0, y, (el + wr) / 2), "forearm.L", ROBE)
part("hand.L", "sphere", 0.13, (0, y, wr - 0.05), "hand.L", SKIN, segments=8)
for n in ("upper_arm.L", "forearm.L", "hand.L"):
    mirror(n)

# Staff in the near hand, upright; exaggerated to 0.12 units thick so it never drops out
hz, hy = wr - 0.05, -y - 0.08
low, high = R.pt(0, 236)[1] - R.pt(0, 136)[1], R.pt(0, 40)[1] - R.pt(0, 136)[1]
part("staff", "cylinder", (0.12, 0.12, high - low), (0.02, hy, hz + (high + low) / 2), "hand.R", WOOD,
     segments=6)
part("gem", "sphere", 0.17, (0.02, hy, hz + high + 0.06), "hand.R", GEM, segments=8)
