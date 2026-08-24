import cv2, os
# Probe camera indices and save one frame from each, so you can tell them apart.
# XWF-1080P (arm cam) was index 0; MacBook Air built-in was index 1.
out = os.path.dirname(os.path.abspath(__file__))
for idx in range(4):
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        print(f"index {idx}: not opened"); cap.release(); continue
    frame = None
    for _ in range(10):              # warm up; first frames are often black
        ok, f = cap.read()
        if ok and f is not None: frame = f
    if frame is None:
        print(f"index {idx}: opened but no frame"); cap.release(); continue
    h, w = frame.shape[:2]
    path = os.path.join(out, f"cam{idx}.png")
    cv2.imwrite(path, frame)
    print(f"index {idx}: OK  {w}x{h}  mean_brightness={frame.mean():.1f}  -> {path}")
    cap.release()
