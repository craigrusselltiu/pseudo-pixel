"""Idle: the reference pose (sword held forward, shield back) with a one-pixel breathing bob."""
from anim import action

PX = 1 / 20  # one pixel at 20 pixels per unit
GUARD = {"upper_arm.R": (10, 0, 0), "forearm.R": (80, 0, 0), "hand.R": (-80, 0, 0),
         "upper_arm.L": (-10, 0, 0), "forearm.L": (10, 0, 0),
         "thigh.L": (8, 0, 0), "shin.L": (-8, 0, 0), "thigh.R": (-6, 0, 0)}

a = action("idle", loop=True)
a.key(0, {**GUARD, "hips": {"loc": (0, 0, 0)}, "chest": (0, 0, 0)})
a.key(6, {**GUARD, "hips": {"loc": (0, 0, -PX)}, "chest": (3, 0, 0), "forearm.R": (76, 0, 0),
          "hand.R": (-76, 0, 0)})
a.end(12)
