"""Simulate a phone camera view of a QR (downscale, blur, rotation, low contrast) and decode with OpenCV.

Run:  python tools_tests/qr_degrade.py <qr_png> <scratch_output_dir>
Writes degraded PNGs to the given (non-repo) directory for the jsQR check.
"""
import pathlib
import sys

import cv2
import numpy as np


def main(src, out_dir):
    out = pathlib.Path(out_dir)
    img = cv2.imread(src, cv2.IMREAD_GRAYSCALE)
    canvas = np.full((600, 600), 255, np.uint8)
    q = cv2.resize(img, (260, 260), interpolation=cv2.INTER_AREA)
    canvas[170:430, 170:430] = q
    variants = {
        "small_150px": cv2.resize(img, (150, 150), interpolation=cv2.INTER_AREA),
        "blur_k5": cv2.GaussianBlur(canvas, (5, 5), 0),
        "rot_15deg": cv2.warpAffine(canvas, cv2.getRotationMatrix2D((300, 300), 15, 1.0), (600, 600), borderValue=255),
        "low_contrast": (canvas.astype(np.float32) * 0.35 + 120).astype(np.uint8),
        "perspective": cv2.warpPerspective(canvas, cv2.getPerspectiveTransform(
            np.float32([[0, 0], [600, 0], [600, 600], [0, 600]]),
            np.float32([[60, 30], [560, 0], [600, 600], [20, 560]])), (600, 600), borderValue=255),
    }
    det = cv2.QRCodeDetector()
    for name, v in variants.items():
        f = out / f"deg_{name}.png"
        cv2.imwrite(str(f), cv2.cvtColor(v, cv2.COLOR_GRAY2BGR))
        text, _, _ = det.detectAndDecode(cv2.imread(str(f)))
        print(f"{f.name}: opencv_decoded={bool(text)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
