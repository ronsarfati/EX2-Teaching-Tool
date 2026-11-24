"""D35: stored UTC times are displayed in Israel local time (DST handled)."""
import dataclasses
import io
from datetime import datetime, timezone

from openpyxl import load_workbook

from app.repositories.summaries import JobStatus, SummaryJob
from app.services.video import _generated_line
from app.timezone import format_local, to_local
from tests.test_export import run_session


def utc(*args) -> float:
    return datetime(*args, tzinfo=timezone.utc).timestamp()


def test_winter_is_utc_plus_2():
    assert format_local(utc(2026, 11, 23, 19, 29), "%H:%M") == "21:29"
    assert to_local(utc(2026, 1, 15, 10, 0)).utcoffset().total_seconds() == 2 * 3600


def test_summer_is_utc_plus_3():
    assert format_local(utc(2026, 7, 10, 10, 0), "%H:%M") == "13:00"
    assert to_local(utc(2026, 7, 10, 10, 0)).utcoffset().total_seconds() == 3 * 3600


def test_date_rolls_over_midnight():
    assert format_local(utc(2026, 11, 23, 22, 30), "%Y-%m-%d %H:%M") == "2026-11-24 00:30"


def test_export_header_and_cell_are_local(app, client, clock):
    client.post("/lecturer/login", data={"pin": "1234"})
    clock.set(utc(2026, 11, 23, 19, 29))
    run_session(app, app.extensions["services"], ["Fox"])
    sheet = load_workbook(io.BytesIO(client.get("/lecturer/export.xlsx").get_data()))["Check-ins"]
    header = [c.value for c in sheet[1]]
    assert header[2] == "Checked in at (Jerusalem time)" and "Jerusalem time" in header[0]
    assert sheet[2][0].value == "2026-11-23 21:29" and sheet[2][2].value == "2026-11-23 21:29:00"


def test_summary_generated_line_uses_local_time():
    job = SummaryJob(1, JobStatus.DONE, 1.0, None, None, None, "x", None,
                     utc(2026, 11, 23, 19, 29), utc(2026, 11, 23, 19, 29), utc(2026, 11, 23, 22, 45))
    assert _generated_line(job) == "Generated on 2026-11-24 00:45"
    assert _generated_line(dataclasses.replace(job, finished_at=None)) == "Generated on 2026-11-23 21:29"
