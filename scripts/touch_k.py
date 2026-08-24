"""touch_k.py — smoothly drive the arm to the pose recorded by teach_k.py.

Reads the current angles, eases to the saved angles over ~2 s (smooth, not bang-bang),
then prints the final per-joint error (where it landed vs what was recorded).
"""
import os, json, time, argparse
from datetime import datetime
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode

PORT = '/dev/tty.usbmodem5B3D0433471'
TICKS_PER_DEG = 4096 / 360
HERE = os.path.dirname(os.path.abspath(__file__))
POSE = os.path.join(HERE, 'pose_k.json')

ap = argparse.ArgumentParser()
ap.add_argument('--live', action='store_true', help='actually move (default: dry-run)')
ap.add_argument('--seconds', type=float, default=2.0, help='how long the move takes (bigger = smoother/slower)')
ap.add_argument('--speed', type=int, default=300, help='servo Goal_Velocity cap')
args = ap.parse_args()
DRY = not args.live

if not os.path.exists(POSE):
    print("No pose_k.json found — run teach_k.py first."); raise SystemExit
target = json.load(open(POSE))['pose']                 # {'m1': ticks, ...}

motors = {k: Motor(int(k[1:]), 'sts3215', MotorNormMode.DEGREES) for k in target}
bus = FeetechMotorsBus(port=PORT, motors=motors)
bus.connect()
start = {k: bus.read('Present_Position', k, normalize=False) for k in motors}

print(f"=== touch_k.py run {datetime.now():%Y-%m-%d %H:%M:%S} | {'DRY-RUN (no motion)' if DRY else 'LIVE'} ===")
for k in motors:
    d = target[k] - start[k]
    print(f"   {k}: {start[k]} -> {target[k]}   ({d:+d} ticks, {d / TICKS_PER_DEG:+.1f} deg)")

if DRY:
    print("dry-run: not moving. Add --live to go.")
    bus.disconnect(); raise SystemExit

# prep: position mode + speed cap; write current pos and THEN enable torque (so it holds, no jump)
for k in motors:
    bus.write('Operating_Mode', k, OperatingMode.POSITION.value, normalize=False)
    bus.write('Goal_Velocity', k, args.speed, normalize=False)
    bus.write('Goal_Position', k, start[k], normalize=False)
    bus.enable_torque(k)

# smooth ease from start to target (smoothstep: gentle accelerate then decelerate)
N = max(2, int(args.seconds / 0.02))
def smooth(t): return t * t * (3 - 2 * t)
for i in range(1, N + 1):
    s = smooth(i / N)
    for k in motors:
        tgt = round(start[k] + (target[k] - start[k]) * s)
        bus.write('Goal_Position', k, max(100, min(3995, tgt)), normalize=False)
    time.sleep(0.02)
time.sleep(0.4)

print("--- arrived; final error vs recorded ---")
for k in motors:
    actual = bus.read('Present_Position', k, normalize=False)
    err = actual - target[k]
    print(f"   {k}: target {target[k]}  actual {actual}  err {err:+d} ticks ({err / TICKS_PER_DEG:+.1f} deg)")
bus.disconnect()
print("done")
