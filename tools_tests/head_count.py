"""Head count on class photos: OpenCV YuNet (faces) vs Ultralytics YOLO (persons).

Run:  python tools_tests/head_count.py <yunet.onnx> <yolo.pt|none> <photo1.jpeg> [photo2.jpeg ...]
Privacy: images are only read in memory; nothing derived from them is written. Output = counts only.
"""
import pathlib
import sys
import time

import cv2


def yunet_count(det, img, score=0.6, max_side=2000):
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    if s < 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s)))
        h, w = img.shape[:2]
    det.setInputSize((w, h))
    det.setScoreThreshold(score)
    _, faces = det.detect(img)
    return 0 if faces is None else len(faces)


def main(yunet_path, yolo_path, photos):
    det = cv2.FaceDetectorYN.create(yunet_path, "", (320, 320), 0.6, 0.3, 5000)
    yolo = None
    if yolo_path != "none":
        from ultralytics import YOLO  # optional, heavy (torch)
        yolo = YOLO(yolo_path)
    print("photo,yunet,yunet_ms,yolo,yolo_ms,yolo_1280,yolo_1280_ms")
    for p in photos:
        img = cv2.imread(p)
        t0 = time.perf_counter()
        n_face = yunet_count(det, img)
        t1 = time.perf_counter()
        if yolo is None:
            print(f"{pathlib.Path(p).name},{n_face},{(t1-t0)*1000:.0f},-,-,-,-")
            continue
        r = yolo.predict(img, classes=[0], conf=0.25, imgsz=640, verbose=False)[0]
        t2 = time.perf_counter()
        r2 = yolo.predict(img, classes=[0], conf=0.25, imgsz=1280, verbose=False)[0]
        t3 = time.perf_counter()
        print(f"{pathlib.Path(p).name},{n_face},{(t1-t0)*1000:.0f},{len(r.boxes)},{(t2-t1)*1000:.0f},"
              f"{len(r2.boxes)},{(t3-t2)*1000:.0f}")
        del img


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
