"""teach_k.py — record the arm's JOINT angles (move it by hand, press Enter).

No camera, no kinematics. Torque is turned OFF so you can move the arm freely; the encoders
still report position, so we just read and save the angles. touch_k.py replays them.
"""
import os, json
from datetime import datetime
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

PORT = '/dev/tty.usbmodem5B3D0433471'
TICKS_PER_DEG = 4096 / 360          # ~11.38
HERE = os.path.dirname(os.path.abspath(__file__))
POSE = os.path.join(HERE, 'pose_k.json')

motors = {f'm{i}': Motor(i, 'sts3215', MotorNormMode.DEGREES) for i in range(1, 7)}  # 1-6 (incl gripper)
bus = FeetechMotorsBus(port=PORT, motors=motors)
bus.connect()

# torque OFF -> move the arm by hand
for k in motors:
    try:
        bus.disable_torque(k)
    except Exception:
        pass

print("Arm is LOOSE. By hand, move the gripper to TOUCH the red X.")
input("  > hold it on the X and press Enter to record the pose ")

pose = {}
for k in motors:
    try:
        pose[k] = bus.read('Present_Position', k, normalize=False)
    except Exception:
        pass            # skip any motor not on the bus (e.g. gripper not set up)
bus.disconnect()

json.dump({'pose': pose, 'taught_at': f"{datetime.now():%Y-%m-%d %H:%M:%S}"}, open(POSE, 'w'), indent=2)
print(f"Recorded {len(pose)} joints -> {POSE}")
for k, v in pose.items():
    print(f"   {k}: {v} ticks  (~{v / TICKS_PER_DEG:.1f} deg)")
