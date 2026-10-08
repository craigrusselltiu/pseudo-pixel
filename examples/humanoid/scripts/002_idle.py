"""Idle, 1 s loop with foot IK, in the battle view: a fighter's ready bounce with the sword held low.
Two bounces per loop, the weight shifting onto one foot and then the other (the free heel lifts, the
hips sway), the chest following two frames later, the head three frames later, the sword arm bobbing
and the free arm loose. The feet stay planted, so the body never floats."""
from anim import action

FEET = {"foot_ik.L": {"loc": (0.1, 0.04, 0), "rot": (0, 0, 8)},
        "foot_ik.R": {"loc": (-0.08, 0.05, 0), "rot": (0, 0, 20)}}
READY = {"upper_arm.R": (25, 0, 10), "forearm.R": (35, 0, 0), "hand.R": (-25, 0, 0),
         "upper_arm.L": (10, 0, 12), "forearm.L": (20, 0, 0)}


def heel_up(base):
    x, y, z = base["loc"]
    return {"loc": (x - 0.02, y, z + 0.03), "rot": (16, 0, base["rot"][2])}


a = action("idle", loop=True)
a.key(0, {**FEET, **READY, "foot_ik.R": heel_up(FEET["foot_ik.R"]),
          "hips": {"loc": (0, 0.03, -0.09), "rot": (0, 0, 3)}, "chest": (4, 4, -2), "head": (-2, -3, 2)})
a.key(2, {"chest": (6, 6, -3)})
a.key(3, {"head": (-3, -4, 3)})
a.key(4, {"forearm.R": (42, 0, 0), "upper_arm.L": (14, 0, 15)})
a.key(6, {**FEET, "hips": {"loc": (0.01, 0, -0.04), "rot": (0, 0, 0)}})
a.key(8, {"chest": (2, 0, 0)})
a.key(9, {"head": (0, 0, 0)})
a.key(12, {"foot_ik.L": heel_up(FEET["foot_ik.L"]), "hips": {"loc": (0, -0.03, -0.09), "rot": (0, 0, -3)}})
a.key(14, {"chest": (6, -6, 3)})
a.key(15, {"head": (-3, 4, -3)})
a.key(16, {"forearm.R": (32, 0, 0), "upper_arm.L": (6, 0, 10)})
a.key(18, {**FEET, "hips": {"loc": (0.01, 0, -0.04), "rot": (0, 0, 0)}})
a.key(20, {"chest": (2, 0, 0)})
a.key(21, {"head": (0, 0, 0)})
a.end(24)
