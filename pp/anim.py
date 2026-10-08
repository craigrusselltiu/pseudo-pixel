"""Animation helpers: one Blender Action per animation, animated as for a 3D game.

Keys sit on whole frames of the .blend's timeline (24 fps unless changed in Blender) and are smoothly
interpolated (Bezier) by default. The renderer samples the finished motion at the sprite fps, so the
animation's length in seconds sets how many sprite frames it gets.

    a = action("attack")
    a.key(0, {"upper_arm.R": (-30, 0, 0), "chest": (0, 0, 10)})    # ready
    a.key(8, {"upper_arm.R": (-45, 0, 0), "chest": (0, 0, 14)})    # anticipation
    a.key(11, {"upper_arm.R": (110, 0, 0), "chest": (0, 0, -15)})  # strike
    a.key(20, "rest")
    a.end(24)                                                     # one second at 24 fps

Pose values follow the rig convention in rig.py: (x, y, z) Euler degrees, or a dict with any of
"rot", "loc" and "scale".
Each key carries over the previous key's pose and changes only the bones it lists. Keys are written
when end() is called.
"""
import math

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
    def __init__(self, name, loop=False, interpolation="BEZIER", armature=None):
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
        for side in ("L", "R"):  # foot IK (rig.add_foot_ik) is on for a leg when its foot_ik bone is keyed
            shin, foot = self.arm.pose.bones.get(f"shin.{side}"), self.arm.pose.bones.get(f"foot.{side}")
            cons = [c for pb in (shin, foot) if pb for c in pb.constraints if c.name in ("IK", "Copy Rotation")]
            for c in cons:
                c.influence = 1.0 if f"foot_ik.{side}" in bones else 0.0
                c.keyframe_insert("influence", frame=first)
        set_interpolation(act, self.interpolation)
        if self.loop:  # cyclic curves get smooth handles across the loop point
            for fc in fcurves(act):
                fc.modifiers.new("CYCLES")
                fc.update()
        for pb in self.arm.pose.bones:  # leave the armature in its rest pose
            pb.rotation_euler = (0, 0, 0)
            pb.location = (0, 0, 0)
            pb.scale = (1, 1, 1)
        return act


def aim(pose, bone, direction, axis, up=None, armature=None):
    """The rotation of `bone` (convention degrees, for a key) that, with the rest of `pose` applied,
    turns `axis` to point along `direction`. Both are world directions: `axis` as it points in the rest
    pose, for example a blade or barrel on the bone. With `up` = (axis2, direction2), it then also turns
    the prop about `direction` so axis2 comes as close to direction2 as it can (keeps a gun upright).

        GRIP = {"upper_arm.R": (60, 0, -10), "forearm.R": (30, 0, 0)}
        a.key(8, {**GRIP, "hand.R": aim(GRIP, "hand.R", (1, -0.2, -0.6), axis=(0, 0, -1))})
    """
    from mathutils import Vector
    arm = armature or rig.armature()
    ad = arm.animation_data
    act = ad.action if ad else None
    if ad:
        ad.action = None  # or evaluating the scene would pose the armature from the action
    for pb in arm.pose.bones:
        ch = _channels(pose.get(pb.name, "rest"))
        euler, loc, _ = rig.to_pose(pb.bone, ch.get("rot", (0, 0, 0)), ch.get("loc", (0, 0, 0)))
        pb.rotation_euler, pb.location = euler, loc
    bpy.context.view_layer.update()
    pb = arm.pose.bones[bone]
    rest = arm.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()
    now = arm.matrix_world.to_3x3() @ pb.matrix.to_3x3()
    turn = now @ rest.inverted()  # rest pose -> current, in world space
    a = turn @ Vector(axis).normalized()
    d = Vector(direction).normalized()
    delta = a.rotation_difference(d)
    if up:
        a2 = delta @ (turn @ Vector(up[0]))
        want = Vector(up[1])
        p, q = a2 - d * a2.dot(d), want - d * want.dot(d)
        if p.length > 1e-6 and q.length > 1e-6:
            delta = p.rotation_difference(q) @ delta
    world = delta.to_matrix() @ now
    m = (arm.matrix_world.to_3x3().inverted() @ world).to_4x4()
    m.translation = pb.matrix.translation
    pb.matrix = m
    bpy.context.view_layer.update()
    rot, _, _ = rig.from_pose(pb.bone, pb.rotation_euler, pb.location)
    for p in arm.pose.bones:
        p.rotation_euler, p.location = (0, 0, 0), (0, 0, 0)
    if ad:
        ad.action = act
    return tuple(round(v, 2) for v in rot)


def action(name, loop=False, interpolation="BEZIER", armature=None):
    """Start (or replace) the action `name`. interpolation: BEZIER (smooth, the default), LINEAR or
    CONSTANT (stepped: each pose holds until the next key)."""
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


def retime(factor, actions=None):
    """Stretch the timing of actions (names; default all) by `factor`: 2 plays half as fast, 0.5 twice
    as fast. Keys snap to whole frames; when two land on the same frame, the later one wins."""
    ratio = factor
    acts = [bpy.data.actions[n] for n in actions] if actions else list(bpy.data.actions)
    for act in acts:
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


def import_action(blend_path, name, new_name=None):
    """Copy an action from another character's .blend (same bone names) into this one, replacing any
    action already called `new_name` (default: the same name). Preview it afterwards: keys that depend
    on proportions, such as lunges and bobs, may need adjusting."""
    new_name = new_name or name
    with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
        if name not in src.actions:
            raise KeyError(f"no action {name!r} in {blend_path}; actions: {list(src.actions)}")
        dst.actions = [name]
    act = dst.actions[0]
    old = bpy.data.actions.get(new_name)
    if old and old != act:
        bpy.data.actions.remove(old)
    act.name = new_name
    act.use_fake_user = True
    return act


def _r(v, n=3):
    return [round(x, n) + 0.0 for x in v]


def describe(act, arm=None):
    """An action as JSON-ready data in the anim.py convention: range, loop, interpolation and, for every
    keyed frame, the full pose of every animated bone. load() turns it back into an action."""
    arm = arm or rig.armature()
    bones = arm.data.bones
    curves = {}
    for fc in fcurves(act):
        name = fc.data_path.split('"')[1] if fc.data_path.startswith("pose.bones") else None
        if name in bones:
            curves.setdefault(name, []).append(fc)
    frames = sorted({int(round(kp.co.x)) for fcs in curves.values() for fc in fcs
                     for kp in fc.keyframe_points})
    keys = {}
    for f in frames:
        pose = {}
        for name, fcs in curves.items():
            vals = {"rotation_euler": [0.0] * 3, "location": [0.0] * 3, "scale": [1.0] * 3}
            for fc in fcs:
                if fc.data_path.endswith(("rotation_euler", "location", "scale")):
                    vals[fc.data_path.rsplit(".", 1)[1]][fc.array_index] = fc.evaluate(f)
            rot, loc, scale = rig.from_pose(bones[name], vals["rotation_euler"], vals["location"],
                                            vals["scale"])
            entry = {"rot": _r(rot, 1)}
            if any(fc.data_path.endswith("location") for fc in fcs):
                entry["loc"] = _r(loc)
            if any(fc.data_path.endswith(".scale") for fc in fcs):
                entry["scale"] = _r(scale)
            pose[name] = entry
        keys[f] = dict(sorted(pose.items()))
    interps = sorted({kp.interpolation for fc in fcurves(act) for kp in fc.keyframe_points})
    return {"range": [int(act.frame_range[0]), int(act.frame_range[1])],
            "loop": bool(act.get("pp_loop", False)), "interpolation": interps, "keys": keys}


def load(name, data, armature=None):
    """Recreate an action from describe() data (from inspect output, a library file or another
    character). Bones this armature lacks are skipped with a warning."""
    interps = data.get("interpolation") or ["CONSTANT"]
    a = action(name, data.get("loop", False), interps[0] if len(interps) == 1 else "CONSTANT", armature)
    bones = a.arm.pose.bones
    missing = set()
    for f in sorted(data["keys"], key=int):
        pose = data["keys"][f]
        if pose == "rest":
            a.key(int(f), "rest")
            continue
        missing |= {b for b in pose if b not in bones}
        a.key(int(f), {b: v for b, v in pose.items() if b in bones})
    if missing:
        print(f"WARNING action {name}: skipped bones this rig doesn't have: {sorted(missing)}")
    return a.end(int(data["range"][1]))


def leg_ik(side, ankle, hips=(0, 0, 0), toe=0.0, armature=None):
    """Pose values that put the ankle of leg `side` ("L" or "R") at `ankle` = (x, z) in units.

    Solves the thigh and shin swing in the character's x-z plane (knee bending forward) and keeps the foot level,
    tilted by `toe` degrees (positive: toe down). `hips` is the hips location keyed in the same pose;
    the hips must not be rotated. Use it to plant feet in walks and crouches:
        a.key(0, {"hips": {"loc": (0, 0, -0.05)}, **leg_ik("L", (0.25, 0.06), hips=(0, 0, -0.05))})
    Returns {thigh: (x, 0, 0), shin: (x, 0, 0), foot: (x, 0, 0)}. Out-of-reach targets straighten the leg.
    """
    arm = rig.armature(armature)
    thigh, shin = arm.data.bones[f"thigh.{side}"], arm.data.bones[f"shin.{side}"]
    l1, l2 = thigh.length, shin.length
    hx, hz = thigh.head_local.x + hips[0], thigh.head_local.z + hips[2]
    dx, dz = ankle[0] - hx, ankle[1] - hz
    d = min(max(math.hypot(dx, dz), abs(l1 - l2) + 1e-6), l1 + l2 - 1e-6)
    aim = math.atan2(dx, -dz)  # angle of the hip->ankle line, from straight down toward +X
    hip_angle = math.acos((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))
    knee_angle = math.acos((l1 * l1 + l2 * l2 - d * d) / (2 * l1 * l2))
    t1 = math.degrees(aim + hip_angle)      # thigh swings forward of the line: the knee points forward
    t2 = -math.degrees(math.pi - knee_angle)  # shin folds back
    return {f"thigh.{side}": (round(t1, 2), 0, 0), f"shin.{side}": (round(t2, 2), 0, 0),
            f"foot.{side}": (round(t1 + t2 + toe, 2), 0, 0)}
