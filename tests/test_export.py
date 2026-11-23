"""Export (T12): files equal the live data, no IP / token, injection neutralised, PIN required."""
import csv
import io

import pytest
from openpyxl import load_workbook

from app.services.export import AttendanceExporter

URLS = ["/lecturer/export/checkins.csv", "/lecturer/export/summary.csv", "/lecturer/export.xlsx"]


@pytest.fixture
def services(app):
    s = app.extensions["services"]
    return s


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def check_in(app, nickname):
    phone = app.test_client()
    state = app.extensions["services"]["session_service"].projector_state()
    phone.get(state.check_in_url.split("test.example")[1])
    phone.post("/checkin", data={"nickname": nickname, "code": state.code})


def run_session(app, services, nicknames, head_count=None):
    service = services["session_service"]
    session = service.open_session()
    for nickname in nicknames:
        check_in(app, nickname)
    if head_count is not None:
        services["sessions"].set_head_count(session.id, head_count, 0)
    service.close_session()
    return session


def read_csv(response):
    return list(csv.reader(io.StringIO(response.get_data().decode("utf-8-sig"))))


def test_checkins_csv_equals_live_table(app, services, lecturer):
    session = run_session(app, services, ["Fox", "Owl"])
    rows = read_csv(lecturer.get(URLS[0]))
    live = lecturer.get(f"/api/sessions/{session.id}/attendance").get_json()["check_ins"]
    assert rows[0] == ["Session date (Jerusalem time)", "Nickname", "Checked in at (Jerusalem time)"]
    assert [r[1] for r in rows[1:]] == [c["nickname"] for c in live]


def test_summary_equals_page(app, services, lecturer):
    first = run_session(app, services, ["Fox", "Owl"], head_count=2)
    run_session(app, services, ["Cat"])
    rows = read_csv(lecturer.get(URLS[1]))
    page = lecturer.get(f"/api/sessions/{first.id}/attendance").get_json()
    assert rows[0] == ["Session date (Jerusalem time)", "check-ins (N)", "faces detected (D)", "consistency status"]
    assert rows[1][1:] == [str(page["n"]), str(page["head_count"]), page["consistency"]]
    assert rows[2][1:] == ["1", "", ""]  # no photo counted: empty D and status


def test_anomaly_status_exported(app, services, lecturer):
    run_session(app, services, ["Fox"], head_count=40)
    assert read_csv(lecturer.get(URLS[1]))[1][3] == "anomaly"


def test_xlsx_has_two_sheets_equal_to_csv(app, services, lecturer):
    run_session(app, services, ["Fox", "Owl"], head_count=2)
    workbook = load_workbook(io.BytesIO(lecturer.get(URLS[2]).get_data()))
    assert workbook.sheetnames == ["Check-ins", "Summary"]
    checkins = [[str(c) for c in row] for row in workbook["Check-ins"].iter_rows(values_only=True)]
    assert checkins == read_csv(lecturer.get(URLS[0]))
    assert [c.value for c in workbook["Summary"][2]][1:] == [2, 2, "consistent"]


def test_no_ip_or_token_column_or_value(app, services, lecturer):
    run_session(app, services, ["Fox"])
    for url in URLS[:2]:
        text = lecturer.get(url).get_data(as_text=True).lower()
        assert "token" not in text and "ip" not in text.split("\n")[0].split(",")


@pytest.mark.parametrize("nickname", ["=1+1", "+cmd", "-2", "@SUM(A1)"])
def test_formula_injection_neutralised(app, services, lecturer, nickname):
    run_session(app, services, [nickname])
    assert read_csv(lecturer.get(URLS[0]))[1][1] == "'" + nickname
    sheet = load_workbook(io.BytesIO(lecturer.get(URLS[2]).get_data()))["Check-ins"]
    assert sheet["B2"].value == "'" + nickname and sheet["B2"].data_type == "s"


def test_unicode_nickname_round_trips(app, services, lecturer):
    run_session(app, services, ["שלום-ñ"])
    assert read_csv(lecturer.get(URLS[0]))[1][1] == "שלום-ñ"
    assert load_workbook(io.BytesIO(lecturer.get(URLS[2]).get_data()))["Check-ins"]["B2"].value == "שלום-ñ"


def test_empty_database_gives_headers_only(lecturer):
    assert len(read_csv(lecturer.get(URLS[0]))) == 1 and len(read_csv(lecturer.get(URLS[1]))) == 1


@pytest.mark.parametrize("url", URLS)
def test_routes_require_pin(client, url):
    response = client.get(url)
    assert response.status_code == 302 and "/lecturer/login" in response.headers["Location"]


@pytest.mark.parametrize("url,mimetype,filename", [
    (URLS[0], "text/csv", "checkins.csv"),
    (URLS[1], "text/csv", "summary.csv"),
    (URLS[2], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "attendance.xlsx"),
])
def test_content_type_and_filename(lecturer, url, mimetype, filename):
    response = lecturer.get(url)
    assert response.mimetype == mimetype
    assert f'filename="{filename}"' in response.headers["Content-Disposition"]


def test_dashboard_links(lecturer):
    html = lecturer.get("/lecturer").get_data(as_text=True)
    assert all(url in html for url in URLS)


def test_exporter_is_wired(app):
    assert isinstance(app.extensions["services"]["exporter"], AttendanceExporter)
