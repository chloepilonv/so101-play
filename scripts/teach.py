"""TEACH the touch goal: record where the red X sits in the camera when the gripper touches it.

Camera-only (no arm control needed here). You limp the arm and hand-place the gripper first.
"""
import sys, os, json, cv2
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vision

CAM = 0
HERE = os.path.dirname(os.path.abspath(__file__))
GOAL = os.path.join(HERE, 'goal.json')

print("TEACH the touch pose")
print("  1. In another terminal:  python ../limp.py     (arm goes loose)")
print("  2. By hand, move the gripper until it TOUCHES the red X")
print("  3. Keep the X visible to the camera, then press Enter here")
input("  > press Enter when the gripper is touching the X ")

cap = cv2.VideoCapture(CAM)
det = frame = None
for _ in range(15):                 # warm up, then grab a stable frame
    ok, f = cap.read()
    if ok:
        frame, det = f, vision.find_red(f)
cap.release()

if det is None:
    print("No red X detected — it may be hidden by the gripper. Reposition so the X stays visible, then retry.")
    raise SystemExit

cx, cy, area, c = det
goal = {'goal_cx': cx, 'goal_cy': cy, 'goal_area': area,
        'taught_at': f"{datetime.now():%Y-%m-%d %H:%M:%S}"}
json.dump(goal, open(GOAL, 'w'), indent=2)
cv2.imwrite(os.path.join(HERE, 'goal_view.png'), vision.annotate(frame, det))
print(f"Saved goal -> {GOAL}")
print(f"  X at pixel ({cx:.0f}, {cy:.0f}), area {area:.0f}   (preview: goal_view.png)")
