#!/usr/bin/env python3
"""
homography_calib.py
Pixel <-> table calibration for the SO-101 vision-pick pipeline.

You click >=4 points in the camera image and type the real table (X, Y) in mm
for each. It computes the homography H and saves it. Every later step loads H
and calls pixel_to_table(u, v) -> (X_mm, Y_mm).

HOW TO GET THE mm VALUES for each point (pick ONE method, be consistent):
  A) Ruler: choose an origin corner on the table = (0, 0). Lay a tape measure
     along two edges = your +X and +Y axes. Read off X,Y for each clicked spot.
  B) Gripper: jog the arm so the tool tip touches the spot, read the commanded
     X,Y you sent it. (Best, because it ties the map to the arm's own frame.)

CONTROLS (in the window):
  SPACE = freeze the live feed so you can click accurately
  click = mark a point (you'll be asked for its mm coords in the terminal)
  u     = undo last point
  c     = compute + save H (needs >=4 points)
  v     = verify mode (click anywhere, see the mapped table coords)
  q/ESC = quit

USAGE:
  python homography_calib.py                 # default camera 0
  python homography_calib.py --camera 1      # try 1 for the external USB cam
  python homography_calib.py --out myH.npz

NOTE (macOS): first run will prompt for Camera permission for your terminal/IDE.
Put a few points spread across the whole table (corners + middle), not clustered.
"""

import argparse
import cv2
import numpy as np


def reprojection_error(H, img_pts, world_pts):
    """Map the clicked pixels through H and compare to the mm you typed."""
    proj = cv2.perspectiveTransform(img_pts.reshape(-1, 1, 2), H).reshape(-1, 2)
    err = np.linalg.norm(proj - world_pts, axis=1)
    return proj, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0, help="camera index (try 1 for USB cam)")
    ap.add_argument("--out", default="homography.npz", help="output file for H")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {args.camera}. Try a different --camera index.")

    win = "homography calibration"
    cv2.namedWindow(win)

    state = {"pending": None}  # last unclaimed click

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["pending"] = (x, y)

    cv2.setMouseCallback(win, on_mouse)

    img_pts = []    # [(u, v), ...]
    world_pts = []  # [(X_mm, Y_mm), ...]
    frozen = None   # a frozen frame, or None for live

    print(__doc__)
    print("Press SPACE to freeze the frame, then click your calibration points.\n")

    while True:
        if frozen is None:
            ok, frame = cap.read()
            if not ok:
                print("Frame grab failed; retrying...")
                continue
            view = frame.copy()
        else:
            view = frozen.copy()

        # draw existing points
        for i, (u, v) in enumerate(img_pts):
            cv2.circle(view, (u, v), 5, (0, 255, 0), -1)
            label = f"{i}:({world_pts[i][0]:.0f},{world_pts[i][1]:.0f})"
            cv2.putText(view, label, (u + 8, v - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

        status = "FROZEN - click points" if frozen is not None else "LIVE - press SPACE to freeze"
        cv2.putText(view, f"{status} | points: {len(img_pts)}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2, cv2.LINE_AA)

        cv2.imshow(win, view)
        key = cv2.waitKey(20) & 0xFF

        # handle a fresh click
        if state["pending"] is not None:
            if frozen is None:
                print("Freeze the frame first (press SPACE), then click.")
            else:
                u, v = state["pending"]
                # show the dot immediately
                cv2.circle(view, (u, v), 5, (0, 0, 255), -1)
                cv2.imshow(win, view)
                cv2.waitKey(1)
                try:
                    raw = input(f"  table coords for pixel ({u},{v}) as 'X Y' in mm: ")
                    X, Y = (float(t) for t in raw.replace(",", " ").split())
                    img_pts.append((u, v))
                    world_pts.append((X, Y))
                    print(f"  -> stored point {len(img_pts)-1}: pixel({u},{v}) = table({X},{Y}) mm")
                except (ValueError, KeyboardInterrupt):
                    print("  skipped (bad input)")
            state["pending"] = None

        if key == ord(" "):
            if frozen is None:
                ok, frame = cap.read()
                frozen = frame.copy() if ok else None
                print("Frame frozen. Click your points.")
            else:
                frozen = None
                print("Back to live feed.")

        elif key == ord("u"):
            if img_pts:
                p = img_pts.pop(); w = world_pts.pop()
                print(f"Undid point pixel{p} = table{w}")

        elif key == ord("c"):
            if len(img_pts) < 4:
                print(f"Need at least 4 points, have {len(img_pts)}.")
                continue
            ip = np.array(img_pts, dtype=np.float32)
            wp = np.array(world_pts, dtype=np.float32)
            H, mask = cv2.findHomography(ip, wp)  # least-squares over all points
            if H is None:
                print("findHomography failed (points too collinear?). Add more spread.")
                continue
            proj, err = reprojection_error(H, ip, wp)
            print("\n=== calibration result ===")
            for i in range(len(ip)):
                print(f"  pt {i}: typed {wp[i]} mm, mapped {proj[i].round(1)} mm, "
                      f"error {err[i]:.1f} mm")
            print(f"  mean error: {err.mean():.1f} mm | max: {err.max():.1f} mm")
            if err.max() > 10:
                print("  ** high error - re-check your mm values or click more/spread points **")
            np.savez(args.out, H=H, img_pts=ip, world_pts=wp)
            print(f"  saved H to {args.out}\n")

        elif key == ord("v"):
            if len(img_pts) < 4:
                print("Compute H first (press c).")
                continue
            ip = np.array(img_pts, dtype=np.float32)
            wp = np.array(world_pts, dtype=np.float32)
            H, _ = cv2.findHomography(ip, wp)
            print("VERIFY: click anywhere to see mapped table coords. Press q in window to stop.")
            while True:
                ok, frame = cap.read()
                if not ok:
                    continue
                cv2.putText(frame, "VERIFY - click to map | q to exit", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2, cv2.LINE_AA)
                cv2.imshow(win, frame)
                if state["pending"] is not None:
                    u, v = state["pending"]; state["pending"] = None
                    pt = cv2.perspectiveTransform(
                        np.array([[[u, v]]], dtype=np.float32), H).reshape(2)
                    print(f"  pixel({u},{v}) -> table ({pt[0]:.1f}, {pt[1]:.1f}) mm")
                if (cv2.waitKey(20) & 0xFF) == ord("q"):
                    break

        elif key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()


# convenience function the rest of your pipeline imports
def pixel_to_table(u, v, npz_path="homography.npz"):
    """Load saved H and map one pixel -> (X_mm, Y_mm) on the table plane."""
    data = np.load(npz_path)
    H = data["H"]
    pt = cv2.perspectiveTransform(np.array([[[u, v]]], dtype=np.float32), H).reshape(2)
    return float(pt[0]), float(pt[1])


if __name__ == "__main__":
    main()
