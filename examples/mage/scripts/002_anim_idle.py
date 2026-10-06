"""Idle: the reference pose (staff held out in front), with a slow two-pose bob."""
from anim import action

HOLD = {"upper_arm.R": (15, 0, 0), "forearm.R": (75, 0, 0), "hand.R": (-90, 0, 0)}
a = action("idle", loop=True)
a.key(0, {**HOLD, "hips": {"loc": (0, 0, 0)}, "head": (0, 0, 0)})
a.key(8, {**HOLD, "forearm.R": (78, 0, 0), "hand.R": (-93, 0, 0),
          "hips": {"loc": (0, 0, -1 / 16)}, "head": (4, 0, 0)})
a.end(16)
