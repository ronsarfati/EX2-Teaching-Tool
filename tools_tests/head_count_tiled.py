"""Tiled YuNet head count: run the face detector on overlapping (optionally upscaled) tiles and merge.

Run:  python tools_tests/head_count_tiled.py <yunet.onnx> <photo1.jpeg> [photo2.jpeg ...]
Prints one CSV line per photo and per configuration: counts and runtime only.
Privacy: images are only read in memory; nothing derived from them is written.

The functions `detect_tiled` and `merge` are reusable by the app (count only, photo discarded).
"""
import pathlib
import sys
import time

import cv2
import numpy as np


def _detect(det, img, thr):
    h, w = img.shape[:2]
    det.setInputSize((w, h))
    det.setScoreThreshold(thr)
    _, faces = det.detect(img)
    if faces is None:
        return np.zeros((0, 5), np.float32)
    return faces[:, [0, 1, 2, 3, 14]].astype(np.float32)  # x, y, w, h, score


def merge(boxes, iou_thr=0.3, contain_thr=0.6):
    """Greedy NMS on score; also drops a box mostly contained in a kept one (face cut by a tile border)."""
    if len(boxes) == 0:
        return boxes
    order = np.argsort(-boxes[:, 4])
    keep = []
    for i in order:
        x, y, w, h, _ = boxes[i]
        ok = True
        for j in keep:
            X, Y, W, H, _ = boxes[j]
            iw = max(0.0, min(x + w, X + W) - max(x, X))
            ih = max(0.0, min(y + h, Y + H) - max(y, Y))
            inter = iw * ih
            if inter == 0:
                continue
            union = w * h + W * H - inter
            if inter / union > iou_thr or inter / min(w * h, W * H) > contain_thr:
                ok = False
                break
        if ok:
            keep.append(i)
    return boxes[keep]


def detect_tiled(det, img, rows=1, cols=1, overlap=0.2, upscale=1.0, thr=0.6):
    """Detect faces on a rows x cols grid of overlapping tiles, each upscaled, and merge the results."""
    H, W = img.shape[:2]
    th, tw = H / (rows - overlap * (rows - 1)), W / (cols - overlap * (cols - 1))
    all_boxes = []
    for r in range(rows):
        for c in range(cols):
            y0 = int(round(r * th * (1 - overlap)))
            x0 = int(round(c * tw * (1 - overlap)))
            y1, x1 = min(H, int(round(y0 + th))), min(W, int(round(x0 + tw)))
            tile = img[y0:y1, x0:x1]
            if upscale != 1.0:
                tile = cv2.resize(tile, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
            b = _detect(det, tile, thr)
            if len(b):
                b[:, :4] /= upscale
                b[:, 0] += x0
                b[:, 1] += y0
                all_boxes.append(b)
    boxes = np.concatenate(all_boxes) if all_boxes else np.zeros((0, 5), np.float32)
    return merge(boxes) if (rows * cols > 1) else boxes


def detect_two_bands(det, img, split_frac=0.6, upscale_back=2.0, thr=0.4):
    """SIMULATION of a 'front photo + back photo' protocol from ONE photo.

    The back band (top of the image, y < split) is processed as if it were a second, zoomed photo
    (upscaled), the front band at normal size. Each face is counted in exactly one band, decided by
    the y coordinate of its centre, so nobody is counted twice. A small margin lets faces cut by the
    split line be detected whole in either band.
    """
    H = img.shape[0]
    split = int(H * split_frac)
    margin = int(0.05 * H)
    back = img[: split + margin]
    front = img[split - margin:]
    b = _detect(det, cv2.resize(back, None, fx=upscale_back, fy=upscale_back, interpolation=cv2.INTER_CUBIC), thr)
    b[:, :4] /= upscale_back
    f = _detect(det, front, thr)
    f[:, 1] += split - margin
    keep_b = b[(b[:, 1] + b[:, 3] / 2) < split]
    keep_f = f[(f[:, 1] + f[:, 3] / 2) >= split]
    return np.concatenate([keep_b, keep_f])


CONFIGS = [  # name, rows, cols, upscale, threshold
    ("full_t0.6", 1, 1, 1.0, 0.6),
    ("full_t0.4", 1, 1, 1.0, 0.4),
    ("full_t0.5", 1, 1, 1.0, 0.5),
    ("full_t0.3", 1, 1, 1.0, 0.3),
    ("2x2_u2_t0.6", 2, 2, 2.0, 0.6),
    ("2x2_u2_t0.4", 2, 2, 2.0, 0.4),
    ("3x3_u2_t0.6", 3, 3, 2.0, 0.6),
    ("3x3_u2_t0.4", 3, 3, 2.0, 0.4),
    ("3x3_u3_t0.5", 3, 3, 3.0, 0.5),
    ("4x4_u3_t0.5", 4, 4, 3.0, 0.5),
]


def main(model, photos):
    det = cv2.FaceDetectorYN.create(model, "", (320, 320), 0.6, 0.3, 5000)
    names = [n for n, *_ in CONFIGS] + ["2bands_u2_t0.4", "2bands_u3_t0.5"]
    print("photo," + ",".join(f"{n},{n}_ms" for n in names))
    for p in photos:
        img = cv2.imread(p)
        cells = []
        runs = [lambda r=r, c=c, u=u, t=t: detect_tiled(det, img, r, c, 0.2, u, t) for _, r, c, u, t in CONFIGS]
        runs += [lambda: detect_two_bands(det, img, 0.6, 2.0, 0.4), lambda: detect_two_bands(det, img, 0.6, 3.0, 0.5)]
        for run in runs:
            t0 = time.perf_counter()
            n = len(run())
            cells += [str(n), f"{(time.perf_counter() - t0) * 1000:.0f}"]
        print(pathlib.Path(p).name + "," + ",".join(cells))
        del img


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
