"""Idle wobble and a hop: squash, stretch into the air, land with a squash."""
from anim import action

a = action("idle", loop=True)
a.key(0, {"body": {"scale": (1, 1, 1)}})
a.key(6, {"body": {"scale": (1.08, 1.08, 0.9)}})
a.end(12)

h = action("hop")
h.key(0, {"body": {"scale": (1.15, 1.15, 0.8)}})                           # anticipation squash
h.key(3, {"body": {"scale": (0.85, 0.85, 1.25), "loc": (0, 0, 0.3)}})      # launch stretch
h.key(5, {"body": {"scale": (1, 1, 1), "loc": (0, 0, 0.55)}})              # apex
h.key(7, {"body": {"scale": (0.9, 0.9, 1.15), "loc": (0, 0, 0.25)}})       # falling
h.key(9, {"body": {"scale": (1.2, 1.2, 0.75), "loc": (0, 0, 0)}})          # landing squash
h.key(11, "rest")
h.end(13)
