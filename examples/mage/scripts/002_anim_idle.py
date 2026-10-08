"""Idle: the staff planted upright at the mage's side, the arm out so it clears the body and face from
the 45 degree view, with a slow breathing bob and the head and staff hand settling a beat later."""
from anim import action

HOLD = {"upper_arm.R": (-5, 0, 32), "forearm.R": (25, 0, 0), "hand.R": (-15, -10, -30)}  # staff upright
a = action("idle", loop=True)
a.key(0, {**HOLD, "hips": {"loc": (0, 0, 0)}, "head": (0, 0, 0)})
a.key(16, {"hips": {"loc": (0, 0, -1 / 28)}})
a.key(20, {"head": (4, 0, 0), "forearm.R": (28, 0, 0)})
a.end(32)
