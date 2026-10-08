"""Knight: armoured humanoid with a plumed helmet, a sword (near hand) and a round shield (far arm).

Measured from reference.png: feet centre at (128, 234), helmet top at y=14, 1.6 units tall.
The reference holds the sword arm forward; the model is built in the rest pose (arms down) with the
sword pointing forward from the hand, and the idle animation raises the forearm to match.
"""
from mathutils import Vector

import rig
from build import Ref, mirror, part

R = Ref(ground=(128, 234), top=14, height=1.6)
STEEL, DARK, RED, GOLD, BLADE = "#9aa6ba", "#404862", "#be343c", "#deb246", "#e2e6ee"

arm = rig.humanoid(height=1.6, head=0.24, legs=0.38, arms=0.4, shoulders=0.13, hips=0.07)
b = arm.data.bones
hand = b["hand.R"].head_local
rig.add_bones(arm, {"weapon": (hand + Vector((0, 0, -0.07)), hand + Vector((0.5, 0, -0.07)), "hand.R")})

# Head
at, (sx, sz) = R.box(100, 14, 158, 66)
part("helmet", "box", (sx, 0.4, sz), at, "head", STEEL, bevel=0.05)
at, (sx, sz) = R.box(140, 32, 160, 42)
part("visor", "box", (sx, 0.44, 0.1), at, "head", DARK)  # deeper than the helmet: seen from the side
plume = [(104, 16), (84, 4), (70, 24), (98, 30)]
at = (*R.pt(89, 17)[:1], 0.0, R.pt(89, 17)[1])
part("plume", "profile", 0.1, at, "head", RED, points=R.points(plume, at))

# Body
at, (sx, sz) = R.box(96, 64, 160, 132)
part("chest", "box", (sx, 0.42, sz), at, "chest", STEEL, bevel=0.04)
at, (sx, sz) = R.box(94, 132, 160, 156)
part("belt", "box", (sx, 0.38, sz), at, "hips", DARK)

# Arms (rest pose: hanging down along the bones), measured widths from the reference
for side in ("L",):
    y = b[f"upper_arm.{side}"].head_local.y
    sh, el, wr = b[f"upper_arm.{side}"].head_local.z, b[f"forearm.{side}"].head_local.z, b[f"hand.{side}"].head_local.z
    part(f"upper_arm.{side}", "box", (R.len(18), 0.13, sh - el + 0.04), (0, y, (sh + el) / 2), f"upper_arm.{side}", STEEL, bevel=0.02)
    part(f"forearm.{side}", "box", (R.len(16), 0.12, el - wr), (0, y, (el + wr) / 2), f"forearm.{side}", STEEL, bevel=0.02)
    part(f"hand.{side}", "box", (0.1, 0.1, 0.12), (0, y, wr - 0.06), f"hand.{side}", DARK)
    mirror(f"upper_arm.{side}")
    mirror(f"forearm.{side}")
    mirror(f"hand.{side}")

# Legs: the reference's far leg is darker only because it is in shadow, so both use the armour colour
for side in ("L",):
    y = b[f"thigh.{side}"].head_local.y
    hip, knee, ankle = b[f"thigh.{side}"].head_local.z, b[f"shin.{side}"].head_local.z, b[f"foot.{side}"].head_local.z
    part(f"thigh.{side}", "box", (R.len(20), 0.15, hip - knee), (0, y, (hip + knee) / 2), f"thigh.{side}", DARK)
    part(f"shin.{side}", "box", (R.len(20), 0.14, knee - ankle + 0.02), (0, y, (knee + ankle) / 2), f"shin.{side}", STEEL, bevel=0.02)
    at, (sx, sz) = R.box(124, 218, 160, 234)
    part(f"foot.{side}", "box", (sx, 0.15, sz), (at[0], y, at[2]), f"foot.{side}", DARK, bevel=0.02)
    mirror(f"thigh.{side}")
    mirror(f"shin.{side}")
    mirror(f"foot.{side}")

# Sword on the weapon bone, pointing forward from the near hand; exaggerated to stay over 1.5 px thick
wz = b["weapon"].head_local.z
wy = b["weapon"].head_local.y - 0.02
part("guard", "box", (0.1, 0.08, R.len(36)), (0.08, wy, wz), "weapon", GOLD)
blade = [(-0.235, -0.05), (0.2, -0.05), (0.235, 0.0), (0.2, 0.05), (-0.235, 0.05)]
part("blade", "profile", 0.03, (0.36, wy, wz), "weapon", BLADE, points=blade)

# Round shield on the far forearm, held behind the body as in the reference
at, (sx, sz) = R.box(60, 70, 116, 150)
part("shield", "cylinder", (sx, sz, 0.06), (at[0], b["forearm.L"].head_local.y + 0.09, at[2]), "forearm.L",
     GOLD, rotate=(90, 0, 0), segments=12)

# Foot IK: planted feet for the idle (actions that key foot_ik bones); walk and attack stay FK
rig.add_foot_ik(arm)
