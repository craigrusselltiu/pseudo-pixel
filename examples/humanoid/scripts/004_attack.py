"""Attack, made for the battle view (views [110]: facing the camera, turned slightly to screen left):
a diagonal slash at an enemy on the camera's side. The sword rises up and out to the right with the
torso wound back, holds a beat, cuts down and across the body toward the camera with a lunge (root
motion), follows through low on the left, and recovers to the ready pose. 1.1 s at 24 fps."""
from anim import action

READY = {"upper_arm.R": (25, 0, 10), "forearm.R": (35, 0, 0), "hand.R": (-25, 0, 0),
         "upper_arm.L": (10, 0, 12), "forearm.L": (20, 0, 0), "chest": (4, 0, 0), "spine": (0, 0, 0),
         "head": (0, 0, 0), "hips": {"loc": (0, 0, 0)},
         "thigh.L": (14, 0, 6), "shin.L": (-14, 0, 0), "thigh.R": (-10, 0, 6), "shin.R": (-4, 0, 0),
         "root": {"loc": (0, 0, 0)}}

a = action("attack")
a.key(0, READY)
a.key(6, {"upper_arm.R": (112, 0, 34), "forearm.R": (28, 0, 0), "hand.R": (0, 0, 0),               # windup:
          "upper_arm.L": (30, 0, 25), "chest": (-4, -14, 0), "spine": (0, -6, 0), "head": (-2, 8, 0),    # sword up
          "hips": {"loc": (0, 0, -0.03)}, "thigh.R": (-16, 0, 6), "shin.R": (-10, 0, 0)})        # and back
a.key(10, {"upper_arm.R": (118, 0, 38), "chest": (-6, -17, 0)})                                    # hold
a.key(13, {"upper_arm.R": (70, 0, -35), "forearm.R": (5, 0, 0), "hand.R": (-35, 0, 0),           # strike:
           "upper_arm.L": (-25, 0, 30), "chest": (16, 28, 0), "spine": (6, 12, 0), "head": (8, -10, 0),  # cut across
           "hips": {"loc": (0, 0, -0.06)}, "thigh.L": (40, 0, 6), "shin.L": (-38, 0, 0),
           "thigh.R": (-26, 0, 6), "shin.R": (-10, 0, 0), "root": {"loc": (0.28, 0, 0)}})
a.key(16, {"upper_arm.R": (40, 0, -45), "hand.R": (-45, 0, 0), "chest": (20, 32, 0)})             # follow-through
a.key(22, {"upper_arm.R": (30, 0, -10), "hand.R": (-30, 0, 0), "chest": (8, 8, 0), "spine": (2, 2, 0),
           "head": (2, -2, 0), "hips": {"loc": (0, 0, -0.02)}})                                    # settle
a.key(26, {**READY, "root": {"loc": (0.28, 0, 0)}})                                                # recover
a.end(26)
