# scripts/

Standalone experiments, one file each. All expect the `lerobot` conda env and `ROBOT_PORT`
style values from `../env.sh` (most still hardcode the port at the top; edit it if yours differs).

## Diagnostics (no movement)

| Script | Purpose |
|---|---|
| `scan.py` | List motor IDs on the Feetech bus |
| `ping.py` | Read every motor position (proves comms) |
| `limp.py` | Torque off on all joints. **Soft e-stop.** |
| `camprobe.py` | Save one frame per camera index so you can tell cameras apart |
| `status3.py`, `compare23.py`, `current3.py` | Motor 3 (elbow) overload debugging: registers, current draw vs load |

## Movement

| Script | Purpose |
|---|---|
| `hello.py`, `demo.py` | Small moves through the high-level `SOFollower` API |
| `moveall.py`, `spin.py`, `spinall.py`, `test_motor.py`, `test3.py` | Low-level bus writes, one or all motors |
| `dance.py`, `beat.py` | Velocity-capped staggered moves / metronome oscillation |
| `teach_k.py` → `touch_k.py` | Record joint angles by hand, then ease back to them |

## Vision (wrist camera, red X target)

`vision.py` holds the shared HSV red detector.

| Script | Purpose |
|---|---|
| `track.py` / `aim.py` | Visual servoing: P-control on `shoulder_pan` + `wrist_flex` to center the X, then creep forward until the blob reaches a target area. Dry-run by default, `--live` to move |
| `teach.py` → `touch.py` | Record what the camera sees when the gripper touches the X, then drive until the live view matches it |
| `homography_calibration.py` | Click 4+ image points, enter table (X, Y) in mm, save the homography `H` |

## Kinematics (IKPy, never moves the arm)

```bash
python ik_play.py --info               # chain, joint limits, reach at home
python ik_play.py --fk 0 -30 40 0 0    # 5 angles in degrees → tip pose
python ik_play.py --ik 0.20 0.00 0.10  # target XYZ in meters → joint angles (--plot saves a 3D view)
python ik_play.py --selftest           # FK→IK→FK round trip, passes under 2 mm
python fk_check.py --verify            # read the live arm and confirm URDF FK matches reality
```

Chain: `base_link → shoulder_pan → shoulder_lift → elbow_flex → wrist_flex → wrist_roll → gripper tip`.
Coordinates are base-frame meters, Z up. Max reach is about 45 cm.
