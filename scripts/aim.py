import time, argparse, cv2, numpy as np
from datetime import datetime
from lerobot.robots.so_follower import SOFollower
from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig

# ---- CONFIG (tune here) ----
ap = argparse.ArgumentParser()
ap.add_argument('--live', action='store_true', help='actually move the arm (default: dry-run)')
ap.add_argument('--target-area', type=int, default=80000, help='blob px to stop at; bigger = gets closer')
ap.add_argument('--no-approach', action='store_true', help='only aim/center, do not creep forward')
ap.add_argument('--sign-pan',   type=int, default=1, choices=[-1,1], help='flip if base runs AWAY from X')
ap.add_argument('--sign-wrist', type=int, default=1, choices=[-1,1], help='flip if wrist runs AWAY from X')
ap.add_argument('--sign-lift',  type=int, default=1, choices=[-1,1], help='flip if forward backs away from X')
ap.add_argument('--sign-elbow', type=int, default=1, choices=[-1,1], help='flip if elbow reaches the wrong way')
ap.add_argument('--min-area', type=int, default=8000, help='ignore red blobs smaller than this (px) = anti-speck')
ap.add_argument('--limit', type=int, default=60, help='max degrees a joint may travel from its start pose')
ap.add_argument('--deadband', type=float, default=0.05, help='|error| under this (frac of frame) counts as centered')
args = ap.parse_args()
DRY_RUN = not args.live              # default dry-run; pass --live to move
PORT      = '/dev/tty.usbmodem5B3D0433471'
CAM       = 0
KP_PAN    = 4.0      # how hard to swivel base per unit horizontal error
KP_WRIST  = 4.0      # how hard to tilt wrist per unit vertical error
SIGN_PAN  = args.sign_pan     # --sign-pan -1  if it runs AWAY from the X horizontally
SIGN_WRIST= args.sign_wrist   # --sign-wrist -1  if it runs AWAY vertically
MAX_STEP  = 2.0      # max degrees moved per loop (safety cap)
LIMIT     = args.limit   # --limit N  : max degrees away from start a joint may go
DEADBAND  = args.deadband   # --deadband N  : |error| under this (frac of frame) = "centered"
APPROACH      = not args.no_approach   # --no-approach = only aim, don't creep forward
TARGET_AREA   = args.target_area       # --target-area N  (bigger = gets closer)
SIGN_LIFT     = args.sign_lift         # --sign-lift -1  if forward backs away
SIGN_ELBOW    = args.sign_elbow        # --sign-elbow -1  if elbow reaches the wrong way
MIN_AREA      = args.min_area          # --min-area N  : ignore red blobs smaller than this
SUCCESS_FRAMES= 5       # consecutive on-target frames before declaring success
# red HSV (relaxed for pale red): S>=70, V>=50
LO1,HI1 = (0,70,50),(12,255,255)
LO2,HI2 = (168,70,50),(180,255,255)

def centroid(c):
    M = cv2.moments(c); return M['m10']/M['m00'], M['m01']/M['m00']

def find_red(frame, prev=None):
    H,W = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,LO1,HI1) | cv2.inRange(hsv,LO2,HI2)
    k = np.ones((9,9),np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    cnts,_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = [c for c in cnts if cv2.contourArea(c) >= MIN_AREA]
    if not blobs: return None
    if prev is not None:   # lock onto the blob nearest last frame (anti flip-flop)
        c = min(blobs, key=lambda c: (centroid(c)[0]-prev[0])**2 + (centroid(c)[1]-prev[1])**2)
    else:
        c = max(blobs, key=cv2.contourArea)
    cx,cy = centroid(c)
    ex = (cx - W/2)/(W/2)     # -1..+1, + = X is right of center
    ey = (cy - H/2)/(H/2)     # -1..+1, + = X is below center
    return cx,cy,ex,ey,c

cap = cv2.VideoCapture(CAM)
robot = SOFollower(SO101FollowerConfig(port=PORT, id='follower'))
robot.connect()
home = {k:v for k,v in robot.get_observation().items() if k.endswith('.pos')}
pan, wrist = home['shoulder_pan.pos'], home['wrist_flex.pos']
lift = home['shoulder_lift.pos']
elbow = home['elbow_flex.pos']
hits = 0
def ts(): return datetime.now().strftime('%H:%M:%S')
print(f"=== track.py run {datetime.now():%Y-%m-%d %H:%M:%S} | "
      f"{'DRY-RUN (no motion)' if DRY_RUN else 'LIVE'} | Ctrl-C to stop ===")

def clamp(v, c): return max(c-LIMIT, min(c+LIMIT, v))
def ease(cur, target, step=1.0):   # move cur toward target by up to `step` deg
    d = target - cur
    return cur + max(-step, min(step, d))
prev = None
try:
    while True:
        ok, frame = cap.read()
        if not ok: continue
        r = find_red(frame, prev)
        if r is None:
            prev = None
            pan   = ease(pan,   home['shoulder_pan.pos'])   # back off so gripper un-blocks
            wrist = ease(wrist, home['wrist_flex.pos'])
            lift  = ease(lift,  home['shoulder_lift.pos'])
            elbow = ease(elbow, home['elbow_flex.pos'])
            hits  = 0
            print(f"[{ts()}] no red X -> easing back toward home to re-find it")
            if not DRY_RUN:
                a = dict(home); a['shoulder_pan.pos']=pan; a['wrist_flex.pos']=wrist
                a['shoulder_lift.pos']=lift; a['elbow_flex.pos']=elbow
                robot.send_action(a)
            time.sleep(0.05); continue
        cx,cy,ex,ey,c = r
        prev = (cx,cy)
        area = cv2.contourArea(c)
        centered = abs(ex)<DEADBAND and abs(ey)<DEADBAND
        close    = area >= TARGET_AREA
        # AIM: always steer toward center
        dpan   = SIGN_PAN  *np.clip(KP_PAN  *ex, -MAX_STEP, MAX_STEP)
        dwrist = SIGN_WRIST*np.clip(KP_WRIST*ey, -MAX_STEP, MAX_STEP)
        pan    = clamp(pan   + dpan,   home['shoulder_pan.pos'])
        wrist  = clamp(wrist + dwrist, home['wrist_flex.pos'])
        # APPROACH: once centered, reach forward (shoulder_lift + elbow together) until big enough
        dlift = delbow = 0.0
        if APPROACH and centered and not close:
            dlift  = SIGN_LIFT *MAX_STEP
            delbow = SIGN_ELBOW*MAX_STEP
            lift   = clamp(lift  + dlift,  home['shoulder_lift.pos'])
            elbow  = clamp(elbow + delbow, home['elbow_flex.pos'])
        if centered and close:
            hits += 1
            print(f"[{ts()}] ON TARGET ({hits}/{SUCCESS_FRAMES})  area={area:.0f}")
            if hits >= SUCCESS_FRAMES:
                print(f"[{ts()}] *** SUCCESS - reached the X ***"); break
        else:
            hits = 0
            opan=pan-home['shoulder_pan.pos']; owr=wrist-home['wrist_flex.pos']
            oli=lift-home['shoulder_lift.pos']; oel=elbow-home['elbow_flex.pos']
            mx=lambda o: '!MAX' if abs(o)>=LIMIT-0.5 else ''   # joint pinned at its travel limit
            print(f"[{ts()}] err=({ex:+.2f},{ey:+.2f}) area={area:.0f} | from start: "
                  f"pan{opan:+.0f}{mx(opan)} wrist{owr:+.0f}{mx(owr)} "
                  f"lift{oli:+.0f}{mx(oli)} elbow{oel:+.0f}{mx(oel)}{'  [DRY]' if DRY_RUN else ''}")
        if not DRY_RUN:
            a = dict(home); a['shoulder_pan.pos']=pan; a['wrist_flex.pos']=wrist
            a['shoulder_lift.pos']=lift; a['elbow_flex.pos']=elbow
            robot.send_action(a)
        # preview (opencv is headless -> write to file, open it to watch)
        x,y,w,h = cv2.boundingRect(c)
        cv2.rectangle(frame,(x,y),(x+w,y+h),(0,255,0),2)
        cv2.circle(frame,(int(cx),int(cy)),8,(255,0,255),-1)
        cv2.imwrite('track_view.png', frame)
        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    cap.release(); robot.disconnect(); print("done")
