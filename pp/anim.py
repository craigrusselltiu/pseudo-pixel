"""Pose-to-pose animation helpers. One Blender Action per animation, keyed on whole frames.

    a = action("attack")
    a.key(0, {"upper_arm.R": (-30, 0, 0), "chest": (0, 0, 10)})   # windup
    a.key(5, {"upper_arm.R": (110, 0, 0), "chest": (0, 0, -15)})  # strike
    a.key(9, "rest")
    a.end(11)

Pose values follow the rig convention in rig.py: (x, y, z) Euler degrees, or a dict with any of
"rot", "loc" and "scale".
Each key carries over the previous key's pose and changes only the bones it lists. Keys are written
when end() is called.
"""
import bpy

import rig

REST = {"rot": (0.0, 0.0, 0.0), "loc": (0.0, 0.0, 0.0), "scale": (1.0, 1.0, 1.0)}


def _channels(value):
    if value == "rest":
        return dict(REST)
    if isinstance(value, dict):
        unknown = set(value) - {"rot", "loc", "scale"}
        if unknown:
            raise ValueError(f"unknown pose keys {unknown}; use 'rot', 'loc' and 'scale'")
        return {k: tuple(float(x) for x in v) for k, v in value.items()}
    return {"rot": tuple(float(x) for x in value)}


def mirrored(pose):
    """Swap .L and .R. With the rig's mirror convention, side bones keep their values; centre bones
    flip their Y/Z rotation and Y location."""
    out = {}
    for name, value in pose.items():
        ch = _channels(value)
        if rig.mirror_name(name) == name:
            if "rot" in ch:
                x, y, z = ch["rot"]
                ch["rot"] = (x, -y, -z)
            if "loc" in ch:
                x, y, z = ch["loc"]
                ch["loc"] = (x, -y, z)
        out[rig.mirror_name(name)] = ch
    return out


class Action:
    def __init__(self, name, loop=False, interpolation="CONSTANT", armature=None):
        self.name, self.loop, self.interpolation = name, loop, interpolation
        self.arm = rig.armature(armature)
        self.keys = {}  # frame -> {bone: channels}
        self.pose = {}  # current carried-over pose
        self.loc_bones, self.scale_bones = set(), set()

    def key(self, frame, pose):
        """Key a pose at a whole frame: a {bone: value} dict, or "rest" for every bone at rest."""
        if frame != int(frame):
            raise ValueError(f"frame {frame} is not a whole frame")
        if pose == "rest":
            self.pose = {b: dict(REST) for b in self.pose}
        else:
            for bone, value in pose.items():
                if bone not in self.arm.pose.bones:
                    raise KeyError(f"no bone {bone!r}; bones: {[b.name for b in self.arm.pose.bones]}")
                ch = _channels(value)
                if "loc" in ch:
                    self.loc_bones.add(bone)
                if "scale" in ch:
                    self.scale_bones.add(bone)
                self.pose[bone] = {**REST, **self.pose.get(bone, {}), **ch}
        self.keys[int(frame)] = {b: dict(c) for b, c in self.pose.items()}
        return self

    def pose_at(self, frame):
        """The pose keyed at `frame` (for reusing it, e.g. mirrored, later in the action)."""
        return {b: dict(c) for b, c in self.keys[frame].items()}

    def end(self, frame):
        """Set the last frame and write the action. Loops get a closing key repeating the first pose."""
        if not self.keys:
            raise ValueError("no keys")
        first = min(self.keys)
        if self.loop and frame not in self.keys:
            self.keys[frame] = self.keys[first]
        if max(self.keys) > frame:
            raise ValueError(f"key at frame {max(self.keys)} is after the end frame {frame}")
        bones = set().union(*self.keys.values())

        old = bpy.data.actions.get(self.name)
        if old:
            bpy.data.actions.remove(old)
        act = bpy.data.actions.new(self.name)
        act.use_fake_user = True
        act.use_frame_range = True
        act.frame_start, act.frame_end = first, frame
        act["pp_loop"] = self.loop
        self.arm.animation_data_create()
        self.arm.animation_data.action = act

        for f in sorted(self.keys):
            for name in bones:
                pb, ch = self.arm.pose.bones[name], self.keys[f].get(name, REST)
                euler, loc, scale = rig.to_pose(pb.bone, ch["rot"], ch["loc"], ch["scale"])
                pb.rotation_euler = euler
                pb.keyframe_insert("rotation_euler", frame=f, group=name)
                if name in self.loc_bones:
                    pb.location = loc
                    pb.keyframe_insert("location", frame=f, group=name)
                if name in self.scale_bones:
                    pb.scale = scale
                    pb.keyframe_insert("scale", frame=f, group=name)
        set_interpolation(act, self.interpolation)
        for pb in self.arm.pose.bones:  # leave the armature in its rest pose
            pb.rotation_euler = (0, 0, 0)
            pb.location = (0, 0, 0)
            pb.scale = (1, 1, 1)
        return act


def action(name, loop=False, interpolation="CONSTANT", armature=None):
    """Start (or replace) the action `name`. interpolation: CONSTANT (stepped), LINEAR or BEZIER."""
    return Action(name, loop, interpolation, armature)


def fcurves(act):
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def set_interpolation(act, mode):
    for fc in fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = mode


def retime(old_fps, new_fps, actions=None):
    """Scale every key (and frame range) by new/old and snap to whole frames. When two keys land on the
    same frame, the later one wins. Review the contact sheets afterwards: holds can change length."""
    ratio = new_fps / old_fps
    for act in actions or list(bpy.data.actions):
        for fc in fcurves(act):
            pts = {}
            for kp in fc.keyframe_points:
                pts[round(kp.co.x * ratio)] = (kp.co.y, kp.interpolation)
            fc.keyframe_points.clear()
            for f, (v, interp) in sorted(pts.items()):
                kp = fc.keyframe_points.insert(f, v)
                kp.interpolation = interp
        if act.use_frame_range:
            act.frame_start, act.frame_end = round(act.frame_start * ratio), round(act.frame_end * ratio)
    bpy.context.scene.render.fps = new_fps
