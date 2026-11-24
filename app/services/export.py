"""Offline spreadsheet of all sessions (FR-1.18, D8, D31/OI-6): CSV (two files) and XLSX (two sheets).

Columns carry no IP and no device token (NFR-7). Dates and times are shown in Israel local time (D35)
and the headers say so; the stored values stay UTC.
"""
from __future__ import annotations

import csv
import io

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from app.repositories.checkins import CheckInRepository
from app.repositories.sessions import SessionRepository
from app.services.consistency import ConsistencyResult
from app.timezone import ZONE_LABEL, format_local

CHECKINS_HEADER = [f"Session date ({ZONE_LABEL})", "Nickname", f"Checked in at ({ZONE_LABEL})"]
SUMMARY_HEADER = [f"Session date ({ZONE_LABEL})", "check-ins (N)", "faces detected (D)", "consistency status"]
FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")  # characters that make Excel / Calc read a cell as a formula


def _safe(text: str) -> str:
    """Neutralise formula injection (`=HYPERLINK(...)` must stay text) and drop characters XLSX cannot hold.

    Rows saved before nicknames were cleaned may still contain them; one such row must not break the export.
    """
    text = ILLEGAL_CHARACTERS_RE.sub("", text)  # newline and tab are legal and kept
    return "'" + text if text.startswith(FORMULA_TRIGGERS) else text


def _date(timestamp: float) -> str:
    """Session date; includes the time of day so two sessions on the same day stay distinguishable."""
    return format_local(timestamp, "%Y-%m-%d %H:%M")


class AttendanceExporter:
    def __init__(self, sessions: SessionRepository, check_ins: CheckInRepository) -> None:
        self._sessions = sessions
        self._check_ins = check_ins

    def _checkin_rows(self) -> list[list[str]]:
        rows = []
        for session in self._sessions.list_all():
            for check_in in self._check_ins.list_for_session(session.id):
                rows.append([_date(session.opened_at), _safe(check_in.nickname),
                             format_local(check_in.checked_in_at, "%Y-%m-%d %H:%M:%S")])
        return rows

    def _summary_rows(self) -> list[list[str | int]]:
        rows: list[list[str | int]] = []
        for session in self._sessions.list_all():
            check_ins = self._check_ins.list_for_session(session.id)
            n = len(check_ins)
            d = session.head_count
            # Same rule and wording as the lecturer page; empty cells until a photo is counted (FR-1.16).
            status = "" if d is None else ConsistencyResult.evaluate(n, d).label()
            rows.append([_date(session.opened_at), n, "" if d is None else d, status])
        return rows

    @staticmethod
    def _csv(header: list[str], rows: list[list]) -> bytes:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(header)
        writer.writerows(rows)
        return buffer.getvalue().encode("utf-8-sig")  # BOM: Excel would otherwise misread non-ASCII nicknames

    def checkins_csv(self) -> bytes:
        return self._csv(CHECKINS_HEADER, self._checkin_rows())

    def summary_csv(self) -> bytes:
        return self._csv(SUMMARY_HEADER, self._summary_rows())

    def xlsx(self) -> bytes:
        workbook = Workbook()
        first = True
        for title, header, rows in (("Check-ins", CHECKINS_HEADER, self._checkin_rows()),
                                    ("Summary", SUMMARY_HEADER, self._summary_rows())):
            sheet = workbook.active if first else workbook.create_sheet()
            first = False
            sheet.title = title
            sheet.append(header)
            for row in rows:
                sheet.append(row)
            sheet.freeze_panes = "A2"  # header stays visible while scrolling
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
