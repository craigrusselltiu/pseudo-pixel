"""Walk: contact, down, passing, up, then mirrored; 2 frames each. The sword arm stays in guard."""
from anim import action, mirrored

PX = 1 / 20
LEGS = [
    {"hips": {"loc": (0, 0, 0)}, "thigh.L": (28, 0, 0), "shin.L": (-6, 0, 0), "foot.L": (-10, 0, 0),
     "thigh.R": (-22, 0, 0), "shin.R": (-12, 0, 0), "foot.R": (14, 0, 0)},                    # contact
    {"hips": {"loc": (0, 0, -PX)}, "thigh.L": (16, 0, 0), "shin.L": (-18, 0, 0), "foot.L": (0, 0, 0),
     "thigh.R": (-12, 0, 0), "shin.R": (-40, 0, 0), "foot.R": (18, 0, 0)},                    # down
    {"hips": {"loc": (0, 0, 0)}, "thigh.L": (-2, 0, 0), "shin.L": (-2, 0, 0), "foot.L": (0, 0, 0),
     "thigh.R": (22, 0, 0), "shin.R": (-48, 0, 0), "foot.R": (6, 0, 0)},                      # passing
    {"hips": {"loc": (0, 0, PX)}, "thigh.L": (-16, 0, 0), "shin.L": (-4, 0, 0), "foot.L": (18, 0, 0),
     "thigh.R": (34, 0, 0), "shin.R": (-26, 0, 0), "foot.R": (-6, 0, 0)},                     # up
]
SWING = [-14, -8, 0, 8]  # shield arm swings against the near (left) leg

a = action("walk", loop=True)
for half in (0, 1):
    for i, legs in enumerate(LEGS):
        pose = mirrored(legs) if half else dict(legs)
        s = SWING[i] if not half else -SWING[i]
        pose.update({"upper_arm.L": (s, 0, 0), "forearm.L": (12, 0, 0),
                     "upper_arm.R": (14 - s / 2, 0, 0), "forearm.R": (76, 0, 0), "hand.R": (-78, 0, 0),
                     "chest": (5, 0, 0)})
        a.key(8 * half + 2 * i, pose)
a.end(16)
