"""Attack: guard, overhead windup, anticipation, a fast strike with a lunge, follow-through, recover."""
from anim import action

GUARD = {"upper_arm.R": (10, 0, 0), "forearm.R": (80, 0, 0), "hand.R": (-80, 0, 0),
         "upper_arm.L": (-10, 0, 0), "forearm.L": (10, 0, 0), "chest": (0, 0, 0), "head": (0, 0, 0),
         "thigh.L": (8, 0, 0), "shin.L": (-8, 0, 0), "thigh.R": (-6, 0, 0), "root": {"loc": (0, 0, 0)}}

a = action("attack")
a.key(0, GUARD)
a.key(4, {"upper_arm.R": (190, 0, 0), "forearm.R": (40, 0, 0), "hand.R": (-80, 0, 0),  # sword back over the shoulder
          "upper_arm.L": (20, 0, 0), "chest": (-12, 0, 0), "head": (-6, 0, 0),
          "thigh.L": (18, 0, 0), "shin.L": (-10, 0, 0), "thigh.R": (-10, 0, 0)})              # windup
a.key(10, {"upper_arm.R": (200, 0, 0), "hand.R": (-85, 0, 0), "chest": (-15, 0, 0)})        # ease
a.key(12, {"upper_arm.R": (95, 0, 0), "forearm.R": (0, 0, 0), "hand.R": (-70, 0, 0),
          "upper_arm.L": (-35, 0, 0), "chest": (18, 0, 0), "head": (8, 0, 0),
          "thigh.L": (38, 0, 0), "shin.L": (-36, 0, 0), "thigh.R": (-28, 0, 0), "shin.R": (-6, 0, 0),
          "root": {"loc": (0.3, 0, 0)}})                                                     # strike
a.key(14, {"upper_arm.R": (70, 0, 0), "hand.R": (-60, 0, 0)})                                 # follow
a.key(20, {**GUARD, "root": {"loc": (0.3, 0, 0)}, "chest": (6, 0, 0)})                       # recover
a.end(24)
