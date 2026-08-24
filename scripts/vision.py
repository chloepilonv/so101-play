"""Shared red-X detection (HSV threshold + largest contour) used by aim/track/teach/touch."""
import cv2, numpy as np

# Red wraps around hue 0, so two ranges. S/V floors relaxed so pale/washed-out red still passes.
LO1, HI1 = (0, 70, 50), (12, 255, 255)
LO2, HI2 = (168, 70, 50), (180, 255, 255)


def centroid(contour):
    M = cv2.moments(contour)
    return M['m10'] / M['m00'], M['m01'] / M['m00']


def find_red(frame, min_area=8000, prev=None):
    """Find the red X. Returns (cx, cy, area, contour) or None.

    prev=(x,y): when several red blobs exist, pick the one nearest prev (anti flip-flop).
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LO1, HI1) | cv2.inRange(hsv, LO2, HI2)
    k = np.ones((9, 9), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = [c for c in cnts if cv2.contourArea(c) >= min_area]
    if not blobs:
        return None
    if prev is not None:
        c = min(blobs, key=lambda c: (centroid(c)[0] - prev[0]) ** 2 + (centroid(c)[1] - prev[1]) ** 2)
    else:
        c = max(blobs, key=cv2.contourArea)
    cx, cy = centroid(c)
    return cx, cy, cv2.contourArea(c), c


def annotate(frame, det, target=None):
    """Draw the detection (green box + magenta centroid) and optional target pixel, for preview."""
    if det is None:
        return frame
    cx, cy, area, c = det
    x, y, w, h = cv2.boundingRect(c)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.circle(frame, (int(cx), int(cy)), 8, (255, 0, 255), -1)
    if target is not None:
        tx, ty = int(target[0]), int(target[1])
        cv2.drawMarker(frame, (tx, ty), (0, 255, 255), cv2.MARKER_CROSS, 30, 2)
        cv2.line(frame, (tx, ty), (int(cx), int(cy)), (0, 255, 255), 2)
    return frame
