"""Walk: four key poses (contact, down, passing, up), then the same four mirrored, 4 timeline
frames apart (a 0.67 s cycle at 24 fps)."""
from anim import action, mirrored

STEP = 1 / 16  # one pixel at 16 pixels per unit
POSES = [
    # contact: left heel strikes in front, right leg trails
    {"hips": {"loc": (0, 0, 0)}, "chest": (4, 0, 0),
     "thigh.L": (28, 0, 0), "shin.L": (-6, 0, 0), "foot.L": (-10, 0, 0),
     "thigh.R": (-22, 0, 0), "shin.R": (-12, 0, 0), "foot.R": (14, 0, 0),
     "upper_arm.L": (-22, 0, 0), "forearm.L": (10, 0, 0),
     "upper_arm.R": (24, 0, 0), "forearm.R": (24, 0, 0)},
    # down: weight drops onto the left leg
    {"hips": {"loc": (0, 0, -STEP)},
     "thigh.L": (16, 0, 0), "shin.L": (-18, 0, 0), "foot.L": (0, 0, 0),
     "thigh.R": (-12, 0, 0), "shin.R": (-40, 0, 0), "foot.R": (18, 0, 0),
     "upper_arm.L": (-12, 0, 0), "upper_arm.R": (14, 0, 0)},
    # passing: right leg swings past the straight left leg
    {"hips": {"loc": (0, 0, 0)},
     "thigh.L": (-2, 0, 0), "shin.L": (-2, 0, 0), "foot.L": (0, 0, 0),
     "thigh.R": (22, 0, 0), "shin.R": (-48, 0, 0), "foot.R": (6, 0, 0),
     "upper_arm.L": (0, 0, 0), "forearm.L": (12, 0, 0),
     "upper_arm.R": (2, 0, 0), "forearm.R": (18, 0, 0)},
    # up: left leg pushes off, body rises
    {"hips": {"loc": (0, 0, STEP)},
     "thigh.L": (-16, 0, 0), "shin.L": (-4, 0, 0), "foot.L": (18, 0, 0),
     "thigh.R": (34, 0, 0), "shin.R": (-26, 0, 0), "foot.R": (-6, 0, 0),
     "upper_arm.L": (12, 0, 0), "upper_arm.R": (-10, 0, 0)},
]

a = action("walk", loop=True)
for i, pose in enumerate(POSES + [mirrored(p) for p in POSES]):
    a.key(4 * i, pose)
a.end(32)
