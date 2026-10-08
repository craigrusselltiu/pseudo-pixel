"""Test character for the rig and animation helpers: the standard humanoid with box parts and a sword.

python pp.py run examples/humanoid examples/humanoid/scripts/001_build.py
"""
from mathutils import Vector

import rig
from build import mirror, part

arm = rig.humanoid(height=1.6, head=0.28, legs=0.4)
hand = arm.data.bones["hand.R"].head_local
rig.add_bones(arm, {"weapon": (hand + Vector((0, 0, -0.08)), hand + Vector((0.5, 0, -0.08)), "hand.R")})

ARMOUR, DARK, SKIN, STEEL = "#8b9bb4", "#3a4466", "#e8b796", "#c0cbdc"
part("head", "box", (0.34, 0.32, 0.34), (0.03, 0, 1.32), "head", ARMOUR)
part("visor", "box", (0.1, 0.36, 0.1), (0.2, 0, 1.33), "head", DARK)
part("chest", "box", (0.3, 0.36, 0.26), (0, 0, 0.97), "chest", ARMOUR)
part("belly", "box", (0.26, 0.3, 0.24), (0, 0, 0.76), "hips", DARK)
y, ly = 0.192, 0.112
part("upper_arm.L", "box", (0.11, 0.1, 0.32), (0, y, 0.88), "upper_arm.L", ARMOUR)
part("forearm.L", "box", (0.1, 0.1, 0.3), (0, y, 0.56), "forearm.L", ARMOUR)
part("hand.L", "box", (0.1, 0.1, 0.1), (0, y, 0.36), "hand.L", SKIN)
part("thigh.L", "box", (0.14, 0.13, 0.3), (0, ly, 0.5), "thigh.L", DARK)
part("shin.L", "box", (0.13, 0.12, 0.29), (0, ly, 0.21), "shin.L", ARMOUR)
part("foot.L", "box", (0.22, 0.12, 0.1), (0.05, ly, 0.05), "foot.L", DARK)
for name in ("upper_arm.L", "forearm.L", "hand.L", "thigh.L", "shin.L", "foot.L"):
    mirror(name)
part("blade", "box", (0.5, 0.07, 0.1), (0.35, -0.23, 0.32), "weapon", STEEL)
part("guard", "box", (0.1, 0.07, 0.2), (0.08, -0.23, 0.32), "weapon", DARK)

# Foot IK: planted feet for the idle (actions that key foot_ik bones); walk and attack stay FK
rig.add_foot_ik(arm)
