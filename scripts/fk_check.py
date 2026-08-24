#!/usr/bin/env python
"""
fk_check.py - confirm the URDF forward-kinematics matches the REAL arm.

The calibrator's whole trick is: touch a spot -> read the arm's joint angles -> FK ->
base-frame (X, Y). That only works if lerobot's calibrated joint degrees use the SAME
zero/sign convention as the URDF. This reads the LIVE arm pose (applying your saved
calibration) and prints where the URDF FK *thinks* the gripper tip is.

GENUINELY READ-ONLY: low-level bus, handshake off, NO torque enable, no writes, no
motion. (Same pattern as ping.py / the probe -- not SOFollower, whose connect() enables
torque, which is what failed on motor 5.)

Run (torque off first so you can pose it by hand):
    conda activate lerobot && cd scripts
    python limp.py               # torque off (then it exits)
    python fk_check.py --verify  # GUIDED: 3 moves, prints a plain verdict   <-- start here
    python fk_check.py           # freeform live readout (move arm, watch tip)
    python fk_check.py --once     # single reading and exit
"""
import argparse
import json
import time
from pathlib import Path

import ik_play  # reuse the exact same chain + FK as the IK sandbox
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

PORT = "/dev/tty.usbmodem5B3D0433471"  # same port as your other scripts; edit if it changed
CALIB = Path.home() / ".cache/huggingface/lerobot/calibration/robots/so_follower/follower.json"


def read_deg(bus, joint, tries=3):
    """Read one joint in calibrated degrees, retrying past transient dropped packets."""
    for _ in range(tries):
        try:
            return float(bus.read("Present_Position", joint, normalize=True))
        except Exception:
            time.sleep(0.02)
    raise ConnectionError(f"no reply from {joint} after {tries} tries")


def read_pose(bus, chain):
    """Return (joint_degrees_list, tip_xyz)."""
    degs = [read_deg(bus, j) for j in ik_play.ARM_JOINTS]
    tip = ik_play.fk(chain, degs)[:3, 3]
    return degs, tip


def biggest_mover(a, b):
    """Which joint changed most between two pose readings."""
    return max(zip((abs(y - x) for x, y in zip(a, b)), ik_play.ARM_JOINTS))[1]


def open_bus(chain_needed=True):
    raw = json.loads(CALIB.read_text())
    calibration = {name: MotorCalibration(**vals) for name, vals in raw.items()}
    motors = {n: Motor(raw[n]["id"], "sts3215", MotorNormMode.DEGREES) for n in ik_play.ARM_JOINTS}
    motors["gripper"] = Motor(raw["gripper"]["id"], "sts3215", MotorNormMode.RANGE_0_100)
    bus = FeetechMotorsBus(port=PORT, motors=motors, calibration=calibration)
    bus.connect(handshake=False)  # does NOT enable torque
    return bus


def line(degs, tip):
    joints = "  ".join(f"{j[:8]:>8}{d:+7.1f}" for j, d in zip(ik_play.ARM_JOINTS, degs))
    return f"{joints}   ->  tip  x={tip[0]:+.3f}  y={tip[1]:+.3f}  z={tip[2]:+.3f} m"


def cmd_verify(bus, chain):
    print("\nCONVENTION CHECK — torque should be OFF (run ../limp.py first if the arm is stiff).")
    print("I'll have you make 3 moves and tell you whether FK agrees with reality.\n")

    def snap(msg):
        input(msg)
        return read_pose(bus, chain)

    d0, t0 = snap("1) Put the arm in a comfortable mid-range pose, then press Enter. ")
    results = []

    d1, t1 = snap("2) Raise the GRIPPER straight UP a good few cm. Hold it, press Enter. ")
    dz = (t1[2] - t0[2]) * 100
    results.append(("lift up  -> tip z should rise", dz > 2,
                    f"z moved {dz:+.1f} cm  (you mainly moved {biggest_mover(d0, d1)})"))

    d2, t2 = snap("3) Now swing the BASE to one side. Hold it, press Enter. ")
    horiz = ((t2[0] - t1[0]) ** 2 + (t2[1] - t1[1]) ** 2) ** 0.5 * 100
    results.append(("base swing -> tip sweeps sideways", horiz > 2,
                    f"tip moved {horiz:.1f} cm sideways  (you mainly moved {biggest_mover(d1, d2)})"))

    d3, t3 = snap("4) Finally STRAIGHTEN the arm to reach OUT away from the base. Press Enter. ")
    r2 = (t2[0] ** 2 + t2[1] ** 2) ** 0.5
    r3 = (t3[0] ** 2 + t3[1] ** 2) ** 0.5
    dr = (r3 - r2) * 100
    results.append(("reach out -> distance from base grows", dr > 2,
                    f"reach moved {dr:+.1f} cm  (you mainly moved {biggest_mover(d2, d3)})"))

    print("\n=== verdict ===")
    all_ok = True
    for name, ok, detail in results:
        print(f"  [{'MATCHES' if ok else ' ??? '}] {name}: {detail}")
        all_ok = all_ok and ok
    if all_ok:
        print("\nAll three matched FK -> lerobot degrees line up with the URDF. Safe to calibrate.")
    else:
        print("\nA line shows '???' -> either the move was too small, or that direction is")
        print("inverted/offset. Tell me which line, and I'll fix that joint's sign/offset.")


def cmd_live(bus, chain, once):
    if not once:
        print("Connected (READ-ONLY, no torque). Move the arm by hand. Ctrl-C to stop.\n")
    try:
        while True:
            degs, tip = read_pose(bus, chain)
            if once:
                print(line(degs, tip))
                break
            print("\r" + line(degs, tip) + "   ", end="", flush=True)
            time.sleep(0.3)
    except KeyboardInterrupt:
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="guided 3-move convention check")
    ap.add_argument("--once", action="store_true", help="print one reading and exit")
    args = ap.parse_args()

    chain = ik_play.build_chain(ik_play.DEFAULT_URDF)
    bus = open_bus()
    try:
        if args.verify:
            cmd_verify(bus, chain)
        else:
            cmd_live(bus, chain, args.once)
    finally:
        bus.disconnect()


if __name__ == "__main__":
    main()
