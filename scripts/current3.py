"""current3.py — drive MOTOR 3 slowly and log how much CURRENT it draws (vs its trip threshold).

Run it TWICE to find the cause:
  run 1: let the arm hang free
  run 2: cradle/support the forearm by hand (remove gravity load)
Compare the peak current.
  - supported current LOW + reaches goal  -> motor healthy, it was just load
  - supported current HIGH / still trips  -> motor 3 is weak (high current for no load = the tell)
"""
import time, argparse
from datetime import datetime
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode

PORT = '/dev/tty.usbmodem5B3D0433471'
ap = argparse.ArgumentParser()
ap.add_argument('--delta', type=int, default=-600, help='ticks to move from current pos (negative = down)')
ap.add_argument('--seconds', type=float, default=4.0, help='how slow to drive (bigger = slower)')
args = ap.parse_args()

bus = FeetechMotorsBus(port=PORT, motors={'m3': Motor(3, 'sts3215', MotorNormMode.DEGREES)})
bus.connect()
start = bus.read('Present_Position', 'm3', normalize=False)
lo = bus.read('Min_Position_Limit', 'm3', normalize=False)
hi = bus.read('Max_Position_Limit', 'm3', normalize=False)
prot = bus.read('Protection_Current', 'm3', normalize=False)
target = max(lo + 10, min(hi - 10, start + args.delta))
print(f"m3 start={start} -> target={target}   (range {lo}-{hi})   trips at current > {prot}")

bus.write('Operating_Mode', 'm3', OperatingMode.POSITION.value, normalize=False)
bus.write('Goal_Velocity', 'm3', 150, normalize=False)
bus.write('Goal_Position', 'm3', start, normalize=False)
bus.enable_torque('m3')

N = max(2, int(args.seconds / 0.05))
peak = 0
tripped = False
try:
    for i in range(1, N + 1):
        tgt = round(start + (target - start) * (i / N))
        bus.write('Goal_Position', 'm3', tgt, normalize=False)
        time.sleep(0.05)
        cur = bus.read('Present_Current', 'm3', normalize=False)
        pos = bus.read('Present_Position', 'm3', normalize=False)
        te = bus.read('Torque_Enable', 'm3', normalize=False)
        peak = max(peak, cur)
        bar = '#' * min(40, int(cur / max(prot, 1) * 40))
        print(f"[{datetime.now():%H:%M:%S}] goal {tgt:4d}  pos {pos:4d}  current {cur:4d}/{prot}  {bar}"
              f"{'  <-- TRIPPED' if te == 0 else ''}")
        if te == 0:
            tripped = True
            print("--> torque cut off (overload). stopping."); break
    if not tripped:
        final = bus.read('Present_Position', 'm3', normalize=False)
        print(f"reached pos {final}  (target {target}, err {final - target:+d})  -- no trip")
finally:
    print(f"PEAK current = {peak} / {prot}  ({100 * peak / max(prot,1):.0f}% of trip threshold)")
    try:
        bus.disable_torque('m3')
    except Exception:
        pass
    bus.disconnect()
