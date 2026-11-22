"""Generate QR codes with `qrcode` and decode them back with OpenCV QRCodeDetector.

Run:  python tools_tests/qr_roundtrip.py <scratch_output_dir>
Writes qr_*.png into the given (non-repo) directory so jsQR can also read them.
"""
import pathlib
import sys
import time

import cv2
import qrcode

PAYLOADS = [
    "https://example.trycloudflare.com/a/sess42?t=" + "A" * 60,          # lecturer QR (URL + token)
    "https://example.trycloudflare.com/s/sess42/p7?t=" + "B" * 60,       # student sponsor QR
    "short-token-123",
]


def main(out_dir: str) -> None:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    det = cv2.QRCodeDetector()
    ok = 0
    for i, p in enumerate(PAYLOADS):
        t0 = time.perf_counter()
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
        qr.add_data(p)
        qr.make(fit=True)
        img = qr.make_image()
        f = out / f"qr_{i}.png"
        img.save(f)
        gen_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        text, pts, _ = det.detectAndDecode(cv2.imread(str(f)))
        dec_ms = (time.perf_counter() - t1) * 1000
        match = text == p
        ok += match
        print(f"{f.name}: len={len(p)} chars, version={qr.version}, "
              f"size={img.size[0]}px, gen={gen_ms:.1f} ms, decode={dec_ms:.1f} ms, match={match}")
    print(f"round-trip OK: {ok}/{len(PAYLOADS)}")


if __name__ == "__main__":
    main(sys.argv[1])
