"""Write and re-read an attendance XLSX (fictitious data) with openpyxl, plus a CSV with stdlib.

Run:  python tools_tests/xlsx_roundtrip.py <scratch_output_dir>
"""
import csv
import pathlib
import sys

from openpyxl import Workbook, load_workbook

ROWS = [
    ("nickname", "marked_at", "sponsor", "method"),
    ("BlueFox", "2026-11-22 10:58:01", "lecturer", "qr"),
    ("Pixel42", "2026-11-22 10:58:20", "BlueFox", "qr"),
    ("Kiwi", "2026-11-22 10:58:31", "BlueFox", "qr"),
]


def main(out_dir: str) -> None:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "attendance"
    for r in ROWS:
        ws.append(r)
    ws.freeze_panes = "A2"
    x = out / "attendance_demo.xlsx"
    wb.save(x)
    back = [tuple(r) for r in load_workbook(x).active.iter_rows(values_only=True)]
    print("xlsx bytes:", x.stat().st_size, "| rows read back:", len(back), "| identical:", back == ROWS)
    c = out / "attendance_demo.csv"
    with c.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(ROWS)
    with c.open(newline="", encoding="utf-8") as fh:
        print("csv identical:", [tuple(r) for r in csv.reader(fh)] == ROWS)


if __name__ == "__main__":
    main(sys.argv[1])
