"""Idle: a two-pose breathing loop, each pose held 6 frames."""
from anim import action

a = action("idle", loop=True)
a.key(0, {"hips": {"loc": (0, 0, 0)}, "chest": (0, 0, 0),
          "upper_arm.L": (5, 0, 0), "upper_arm.R": (10, 0, 0), "forearm.R": (15, 0, 0)})
a.key(6, {"hips": {"loc": (0, 0, -0.0625)}, "chest": (-4, 0, 0),
          "upper_arm.L": (3, 0, 0), "upper_arm.R": (6, 0, 0), "forearm.R": (20, 0, 0)})
a.end(12)
