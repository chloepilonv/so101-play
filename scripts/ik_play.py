#!/usr/bin/env python
"""
ik_play.py - beginner inverse-kinematics sandbox for the SO-101 (no ROS, no GPU).

Pure kinematics with IKPy:
  * FK (forward kinematics): given 5 joint angles -> where does the gripper tip end up?
  * IK (inverse kinematics): given a 3D target point -> what 5 joint angles get there?

*** THIS SCRIPT NEVER MOVES THE ARM. ***
It only does math (and an optional 3D plot). Pushing these angles to the real motors
is a separate, deliberate step we'll add later, with limp.py ready as the e-stop.

Chain (matches your motors):
    base_link
      -> shoulder_pan  (motor1)
      -> shoulder_lift (motor2)
      -> elbow_flex    (motor3)
      -> wrist_flex    (motor4)
      -> wrist_roll    (motor5)
      -> gripper tip   (gripper_frame_link)
The gripper jaw (the `gripper` joint / motor6) is NOT part of reaching, so we strip it
out to give IKPy a clean serial chain.

Frame: everything is in base_link coordinates, in METERS. (Origin at the base motor.)

Usage  (first: conda activate lerobot):
    python ik_play.py --home                  # tip position at the all-zeros pose
    python ik_play.py --info                  # print the chain + joint limits
    python ik_play.py --fk 0 -30 40 0 0       # FK: 5 angles in DEGREES -> tip pose
    python ik_play.py --ik 0.20 0.00 0.10     # IK: target X Y Z (m) -> joint angles
    python ik_play.py --ik 0.20 0 0.10 --plot # ...and draw the arm at the solution
    python ik_play.py --selftest              # FK->IK->FK round-trip sanity check
"""
import argparse
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from ikpy.chain import Chain

# Default URDF: the calibrated SO-101 sitting in the ROBOT/ folder (two levels up).
DEFAULT_URDF = Path(__file__).resolve().parents[1] / "so101_new_calib.urdf"

# Arm joints in chain order, with the motor each one drives (for when we wire up the
# real arm later). The jaw (motor6) is intentionally absent.
ARM_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"]
MOTOR_OF = {
    "shoulder_pan": "motor1",
    "shoulder_lift": "motor2",
    "elbow_flex": "motor3",
    "wrist_flex": "motor4",
    "wrist_roll": "motor5",
}


def strip_gripper(urdf_path: Path) -> str:
    """Return a path to a copy of the URDF with the jaw branch removed.

    IKPy needs a single serial chain. gripper_link has two children (the fixed tip
    frame AND the moving jaw); removing the jaw joint + link guarantees IKPy follows
    the arm to the tip instead of wandering down the jaw.
    """
    tree = ET.parse(urdf_path)
    root = tree.getroot()
    for tag, name in (
        ("joint", "gripper"),
        ("joint", "gripper_trans"),
        ("link", "moving_jaw_so101_v1_link"),
        ("transmission", "gripper_trans"),
    ):
        for el in root.findall(tag):
            if el.get("name") == name:
                root.remove(el)
    out = Path(tempfile.gettempdir()) / "so101_arm_only.urdf"
    tree.write(out)
    return str(out)


def build_chain(urdf_path: Path) -> Chain:
    """Load the arm-only chain. Tip = gripper_frame_link."""
    import warnings

    trimmed = strip_gripper(urdf_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # quiet the fixed-joint-axis URDF note
        chain = Chain.from_urdf_file(trimmed, base_elements=["base_link"])
    # IKPy wrongly marks the fixed base + tip frame as active, which would shift the
    # angle->joint mapping. Force the mask to exactly our 5 revolute joints, in order.
    chain.active_links_mask = [link.name in ARM_JOINTS for link in chain.links]
    return chain


def active_idx(chain: Chain):
    """Indices into chain.links of the movable (active) joints, in order."""
    return [i for i, active in enumerate(chain.active_links_mask) if active]


def degs_to_full(chain: Chain, degs):
    """Map 5 joint angles (degrees) -> the full radian vector IKPy expects."""
    full = np.zeros(len(chain.links))
    for i, d in zip(active_idx(chain), degs):
        full[i] = np.radians(d)
    return full


def full_to_degs(chain: Chain, full):
    """Pull the 5 active joint angles (degrees) out of a full IKPy vector."""
    return [np.degrees(full[i]) for i in active_idx(chain)]


def fk(chain: Chain, degs):
    """Forward kinematics: 5 angles (deg) -> 4x4 tip transform in base frame."""
    return chain.forward_kinematics(degs_to_full(chain, degs))


def describe_pose(T):
    pos = T[:3, 3]
    return f"x={pos[0]:+.4f}  y={pos[1]:+.4f}  z={pos[2]:+.4f}  (m)"


def print_joint_table(chain: Chain, degs):
    print(f"  {'joint':<14}{'motor':<8}{'angle (deg)':>12}{'limits (deg)':>22}")
    for name, d in zip(ARM_JOINTS, degs):
        link = chain.links[active_idx(chain)[ARM_JOINTS.index(name)]]
        lo, hi = link.bounds
        lo_d = "-inf" if lo is None else f"{np.degrees(lo):.1f}"
        hi_d = "+inf" if hi is None else f"{np.degrees(hi):.1f}"
        flag = ""
        if lo is not None and hi is not None and not (lo - 1e-6 <= np.radians(d) <= hi + 1e-6):
            flag = "  <-- OUT OF RANGE"
        print(f"  {name:<14}{MOTOR_OF[name]:<8}{d:>12.2f}{f'[{lo_d}, {hi_d}]':>22}{flag}")


def cmd_info(chain: Chain):
    print("Chain links (active = movable joint):")
    for i, link in enumerate(chain.links):
        mark = "active " if chain.active_links_mask[i] else "fixed  "
        print(f"  [{i}] {mark} {link.name}")
    print(f"\nActive DoF: {sum(chain.active_links_mask)}  (expected 5)")
    home = fk(chain, [0, 0, 0, 0, 0])
    print(f"Tip at all-zeros pose: {describe_pose(home)}")
    reach = np.linalg.norm(home[:3, 3])
    print(f"(Tip is {reach*100:.1f} cm from the base origin at this pose.)")


def cmd_home(chain: Chain):
    T = fk(chain, [0, 0, 0, 0, 0])
    print("All-zeros pose (your calibration's 'straight' pose):")
    print(f"  tip: {describe_pose(T)}")


def cmd_fk(chain: Chain, degs):
    if len(degs) != 5:
        sys.exit("--fk needs exactly 5 angles (degrees), one per arm joint.")
    T = fk(chain, degs)
    print("Forward kinematics:")
    print_joint_table(chain, degs)
    print(f"\n  => gripper tip: {describe_pose(T)}")


def cmd_ik(chain: Chain, target, plot: bool):
    target = np.asarray(target, dtype=float)
    print(f"Target point: x={target[0]:+.4f}  y={target[1]:+.4f}  z={target[2]:+.4f} (m)\n")
    # Seed from the home pose so the solver converges to a sane, near-home posture.
    seed = degs_to_full(chain, [0, 0, 0, 0, 0])
    sol = chain.inverse_kinematics(target_position=target, initial_position=seed)
    degs = full_to_degs(chain, sol)

    # How close did we actually get? (5-DoF arms can't always hit a point exactly.)
    reached = chain.forward_kinematics(sol)[:3, 3]
    err_mm = np.linalg.norm(reached - target) * 1000.0

    print("Inverse kinematics solution:")
    print_joint_table(chain, degs)
    print(f"\n  => tip lands at:  x={reached[0]:+.4f}  y={reached[1]:+.4f}  z={reached[2]:+.4f} (m)")
    print(f"  => position error: {err_mm:.1f} mm", end="")
    print("   (good)" if err_mm < 5 else "   (target may be outside the workspace / unreachable pose)")

    if plot:
        import matplotlib  # lazy import so non-plot runs don't need it

        matplotlib.use("Agg")  # save-to-file backend; works with no display
        import matplotlib.pyplot as plt

        ax = plt.figure().add_subplot(111, projection="3d")
        chain.plot(sol, ax, target=target)
        ax.set_title("SO-101 IK solution")
        out = Path(__file__).with_name("ik_solution.png")
        plt.savefig(out, dpi=120)
        print(f"\n  (saved plot -> {out})")


def cmd_selftest(chain: Chain):
    """FK->IK->FK: pick a known pose, recover it from its tip point, check the error."""
    truth = [10.0, -25.0, 35.0, 15.0, 0.0]
    tip = fk(chain, truth)[:3, 3]
    seed = degs_to_full(chain, [0, 0, 0, 0, 0])
    sol = chain.inverse_kinematics(target_position=tip, initial_position=seed)
    tip2 = chain.forward_kinematics(sol)[:3, 3]
    err_mm = np.linalg.norm(tip2 - tip) * 1000.0
    print(f"FK of {truth} -> tip {describe_pose(fk(chain, truth))}")
    print(f"IK recovered tip within {err_mm:.2f} mm")
    print("SELFTEST PASS" if err_mm < 2.0 else "SELFTEST FAIL")
    return err_mm < 2.0


def main():
    p = argparse.ArgumentParser(description="SO-101 IK sandbox (no motion).")
    p.add_argument("--urdf", type=Path, default=DEFAULT_URDF, help="URDF path")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--info", action="store_true", help="print chain + limits + reach")
    g.add_argument("--home", action="store_true", help="tip at all-zeros pose")
    g.add_argument("--fk", nargs=5, type=float, metavar="DEG", help="5 joint angles -> tip")
    g.add_argument("--ik", nargs=3, type=float, metavar=("X", "Y", "Z"), help="target -> joints")
    g.add_argument("--selftest", action="store_true", help="FK/IK round-trip check")
    p.add_argument("--plot", action="store_true", help="(with --ik) save a 3D plot PNG")
    args = p.parse_args()

    if not args.urdf.exists():
        sys.exit(f"URDF not found: {args.urdf}\nPass --urdf /path/to/so101_new_calib.urdf")

    chain = build_chain(args.urdf)

    if args.info:
        cmd_info(chain)
    elif args.home:
        cmd_home(chain)
    elif args.fk:
        cmd_fk(chain, args.fk)
    elif args.ik:
        cmd_ik(chain, args.ik, args.plot)
    elif args.selftest:
        sys.exit(0 if cmd_selftest(chain) else 1)


if __name__ == "__main__":
    main()
