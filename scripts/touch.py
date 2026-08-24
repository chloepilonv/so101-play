"""TOUCH the red X: drive the arm until the camera view matches the taught goal.

Servo so the live X reaches the GOAL pixel + GOAL size that were recorded at touch (teach.py).
Reproducing the goal image reproduces the goal geometry -> the gripper arrives where it touched.
No depth math, no IK: the taught touch-image IS the target.
"""
import sys, os, json, time, argparse, cv2, numpy as np
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vision
from lerobot.robots.so_follower import SOFollower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig

HERE = os.path.dirname(os.path.abspath(__file__))
GOAL = os.path.join(HERE, 'goal.json')

ap = argparse.ArgumentParser()
ap.add_argument('--live', action='store_true', help='actually move (default: dry-run)')
ap.add_argument('--min-area', type=int, default=8000, help='ignore red blobs smaller than this (anti-speck)')
ap.add_argument('--limit', type=int, default=60, help='max degrees a joint may travel from its start pose')
ap.add_argument('--deadband', type=float, default=0.05, help='pixel error (frac of frame) that counts as on-goal')
ap.add_argument('--area-tol', type=float, default=0.10, help='area within this frac of goal = close enough')
ap.add_argument('--sign-pan',   type=int, default=1,  choices=[-1, 1])
ap.add_argument('--sign-wrist', type=int, default=1,  choices=[-1, 1])
ap.add_argument('--sign-lift',  type=int, default=1,  choices=[-1, 1])
ap.add_argument('--sign-elbow', type=int, default=-1, choices=[-1, 1])   # -1 worked on this arm
args = ap.parse_args()
DRY = not args.live

if not os.path.exists(GOAL):
    print("No goal.json found — run teach.py first."); raise SystemExit
g = json.load(open(GOAL))
GX, GY, GAREA = g['goal_cx'], g['goal_cy'], g['goal_area']

PORT = '/dev/tty.usbmodem5B3D0433471'
CAM = 0
KP_PAN = KP_WRIST = 4.0
MAX_STEP = 2.0
SUCCESS_FRAMES = 5

cap = cv2.VideoCapture(CAM)
robot = SOFollower(SO101FollowerConfig(port=PORT, id='follower'))
robot.connect()
home = {k: v for k, v in robot.get_observation().items() if k.endswith('.pos')}
pan, wrist = home['shoulder_pan.pos'], home['wrist_flex.pos']
lift, elbow = home['shoulder_lift.pos'], home['elbow_flex.pos']
hits = 0
prev = None

def ts(): return datetime.now().strftime('%H:%M:%S')
def clamp(v, c): return max(c - args.limit, min(c + args.limit, v))
def ease(cur, tgt, step=1.0): return cur + max(-step, min(step, tgt - cur))

print(f"=== touch.py run {datetime.now():%Y-%m-%d %H:%M:%S} | {'DRY-RUN (no motion)' if DRY else 'LIVE'} | "
      f"goal pixel=({GX:.0f},{GY:.0f}) area={GAREA:.0f} | Ctrl-C to stop ===")

try:
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        det = vision.find_red(frame, min_area=args.min_area, prev=prev)
        if det is None:
            prev = None
            pan = ease(pan, home['shoulder_pan.pos']);   wrist = ease(wrist, home['wrist_flex.pos'])
            lift = ease(lift, home['shoulder_lift.pos']); elbow = ease(elbow, home['elbow_flex.pos'])
            hits = 0
            print(f"[{ts()}] no red X -> easing back to re-find it")
            if not DRY:
                a = dict(home); a['shoulder_pan.pos'] = pan; a['wrist_flex.pos'] = wrist
                a['shoulder_lift.pos'] = lift; a['elbow_flex.pos'] = elbow; robot.send_action(a)
            time.sleep(0.05); continue

        cx, cy, area, c = det
        prev = (cx, cy)
        H, W = frame.shape[:2]
        ex = (cx - GX) / (W / 2)            # error vs the GOAL pixel (not image center)
        ey = (cy - GY) / (H / 2)
        on_pixel = abs(ex) < args.deadband and abs(ey) < args.deadband
        area_err = (area - GAREA) / GAREA   # <0 = too far (small); >0 = too close (big)
        on_area = abs(area_err) <= args.area_tol

        # AIM: move the X toward the goal pixel
        dpan   = args.sign_pan   * np.clip(KP_PAN   * ex, -MAX_STEP, MAX_STEP)
        dwrist = args.sign_wrist * np.clip(KP_WRIST * ey, -MAX_STEP, MAX_STEP)
        pan   = clamp(pan   + dpan,   home['shoulder_pan.pos'])
        wrist = clamp(wrist + dwrist, home['wrist_flex.pos'])

        # REACH: once on the goal pixel, grow/shrink the blob to the goal size
        dlift = delbow = 0.0
        if on_pixel and not on_area:
            d = 1 if area_err < 0 else -1   # too small -> reach forward; too big -> back off
            dlift  = d * args.sign_lift  * MAX_STEP
            delbow = d * args.sign_elbow * MAX_STEP
            lift  = clamp(lift  + dlift,  home['shoulder_lift.pos'])
            elbow = clamp(elbow + delbow, home['elbow_flex.pos'])

        if on_pixel and on_area:
            hits += 1
            print(f"[{ts()}] ON GOAL ({hits}/{SUCCESS_FRAMES}) px=({ex:+.2f},{ey:+.2f}) area_err={area_err:+.0%}")
            if hits >= SUCCESS_FRAMES:
                print(f"[{ts()}] *** TOUCHING THE X ***"); break
        else:
            hits = 0
            print(f"[{ts()}] px=({ex:+.2f},{ey:+.2f}) area_err={area_err:+.0%} -> "
                  f"pan{dpan:+.1f} wrist{dwrist:+.1f} lift{dlift:+.1f} elbow{delbow:+.1f}{'  [DRY]' if DRY else ''}")

        if not DRY:
            a = dict(home); a['shoulder_pan.pos'] = pan; a['wrist_flex.pos'] = wrist
            a['shoulder_lift.pos'] = lift; a['elbow_flex.pos'] = elbow; robot.send_action(a)
        cv2.imwrite(os.path.join(HERE, 'touch_view.png'), vision.annotate(frame, det, target=(GX, GY)))
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    cap.release(); robot.disconnect(); print("done")
