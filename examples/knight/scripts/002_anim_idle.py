"""Idle, 1 s loop with foot IK: the reference pose (sword held forward, shield back) breathing on bent
knees. The feet stay planted while the hips sink a pixel on the exhale, the chest rises and leans back
on the inhale, the head and sword arm follow a few frames later, and the shield arm hangs loose."""
from anim import action

PX = 1 / 20  # one pixel at 20 pixels per unit
FEET = {"foot_ik.L": {"loc": (0.07, 0, 0), "rot": (0, 0, 0)},
        "foot_ik.R": {"loc": (-0.06, 0, 0), "rot": (0, 0, 0)}}
GUARD = {"upper_arm.R": (10, 0, 0), "forearm.R": (80, 0, 0), "hand.R": (-80, 0, 0),
         "upper_arm.L": (-10, 0, 0), "forearm.L": (10, 0, 0)}

a = action("idle", loop=True)
a.key(0, {**FEET, **GUARD, "hips": {"loc": (0, 0, -PX)}, "chest": (3, 0, 0), "head": (2, 0, 0)})
a.key(10, {"hips": {"loc": (0, 0, -2 * PX)}, "chest": (-2, 0, 0)})            # inhale: chest up and back
a.key(13, {"head": (-1, 0, 0), "forearm.R": (76, 0, 0), "hand.R": (-76, 0, 0), "upper_arm.L": (-6, 0, 0)})
a.key(22, {"hips": {"loc": (0, 0, -PX)}, "chest": (3, 0, 0)})                 # exhale
a.end(24)
