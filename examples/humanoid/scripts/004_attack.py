"""Attack: overhead windup, ease, strike with a lunge (root motion), hold, recover."""
from anim import action

a = action("attack")
a.key(0, {"upper_arm.R": (20, 0, 0), "forearm.R": (30, 0, 0), "hand.R": (-20, 0, 0),
          "thigh.L": (14, 0, 0), "shin.L": (-14, 0, 0), "thigh.R": (-10, 0, 0)})        # ready
a.key(2, {"upper_arm.R": (200, 0, 0), "forearm.R": (30, 0, 0), "hand.R": (0, 0, 0),
          "chest": (-10, 0, 0), "head": (-5, 0, 0)})                                     # windup
a.key(5, {"upper_arm.R": (210, 0, 0), "chest": (-14, 0, 0)})                             # ease in
a.key(6, {"upper_arm.R": (85, 0, 0), "forearm.R": (5, 0, 0), "hand.R": (-60, 0, 0),
          "chest": (16, 0, 0), "head": (6, 0, 0),
          "thigh.L": (34, 0, 0), "shin.L": (-34, 0, 0), "thigh.R": (-26, 0, 0),
          "root": {"loc": (0.25, 0, 0)}})                                                # strike
a.key(7, {"upper_arm.R": (60, 0, 0), "hand.R": (-70, 0, 0)})                             # follow
a.key(11, {"upper_arm.R": (20, 0, 0), "forearm.R": (30, 0, 0), "hand.R": (-20, 0, 0),
           "chest": (0, 0, 0), "head": (0, 0, 0),
           "thigh.L": (14, 0, 0), "shin.L": (-14, 0, 0), "thigh.R": (-10, 0, 0)})        # recover
a.end(13)
