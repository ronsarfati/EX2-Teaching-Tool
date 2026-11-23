# Results (To Do 12) - draft

Status: written from the code and tests as of 2026-11-23. Figures from the live class are placeholders and are
filled in only after the demo; nothing below is estimated.

## 1. Setup

- App: Python 3.13, Flask, SQLite, OpenCV YuNet (face count), Anthropic Claude (review); see the README.
- Demo environment: laptop running the app; public HTTPS address from a Cloudflare quick tunnel (plan A) or LAN
  (plan B); students on their own phones. Campus allow-list: [to fill after the class demo].
- Demo data: fictional only (`scripts/seed_demo.py`); no personal data in the repository (D21).

## 2. What was built (state of the code)

| Feature | State |
|---|---|
| F1 Attendance: projector QR (10 s) + 3-digit code (5 s), campus allow-list, live table, photo head count with consistent/anomaly alert, CSV/XLSX export | Implemented, tested |
| F2 Comments (real-time and later) | Implemented, tested |
| F3 Polls (one vote per device, live results, close) | Implemented, tested |
| F5 Homework review with anonymised comparison (public GitHub URL, Claude) | Implemented, tested with fakes; live call needs an API key [to fill after the class demo] |
| F4 Video summary | Not implemented (T18 deferred, pending decision) |

## 3. Measured figures

Automated tests (real run on 2026-11-23, `pytest --cov=app`, offline, no API key):

- 909 passed, 2 skipped (the 2 skipped tests need the YuNet model file, which is absent in the test environment).
- Line coverage of `app/`: 99 % (1274 statements, 19 not covered: model loading in the head counter, the
  `__main__` start-up lines, 4 lines of the poll service).

Scripted local trial (2026-11-23, app on 127.0.0.1, fictional data, Flask server driven with curl): check-in with QR
and code, repeated check-in refused (409), wrong code refused (400), expired or forged QR refused (400), forged
`CF-Connecting-IP` from outside the allow-list refused (403), live table API, poll (create, vote, double vote
refused, close), comments (empty and 501-character comments refused), CSV and XLSX exports (sheets "Check-ins" and
"Summary"), photo upload without the model answers 503 "Head count is not available right now.", review without a key
answers 503 "The review service is unavailable right now. Please try again later." This trial is not a class result.

Photo head count accuracy (from the tools report, 4 provided class photos checked box by box, threshold 0.4): recall
94 %, precision 96 %, mean error 2.5 people, under 0.1 s per photo. These photos are not in the repository.

Live class demo:

| Measure | Value |
|---|---|
| Class date and place | [to fill after the class demo] |
| Students who checked in (N) | [to fill after the class demo] |
| Faces detected on the class photo (D) and alert status | [to fill after the class demo] |
| Duration of the whole-class check-in (open to last row) | [to fill after the class demo] |
| Refusals (off-campus, expired QR, expired window, wrong code) | [to fill after the class demo] |
| Poll: participants and time to results | [to fill after the class demo] |
| Comments received and delay before they appeared | [to fill after the class demo] |
| F5 review: repository, time to answer, quality of the comparison | [to fill after the class demo] |
| Plan B used? Incidents | [to fill after the class demo] |

## 4. Observations

- Design: all external services sit behind interfaces (`HeadCounter`, `LLMClient`, `RepoFetcher`, `Clock`), so the
  whole suite runs offline and F1-F3 work without any key.
- Local trial: [to fill after the class demo] for observations from the real class.
- F4 versus the Zoom example summary: [to fill after the class demo] / not applicable if F4 stays deferred (pending).

## 5. Limits

- Presence is a device on the campus network typing a code shown in the room; relaying the QR and code to someone
  on campus Wi-Fi is not prevented, only made harder and flagged by the head count alert.
- Nicknames and device tokens are not verified; clearing cookies gives a new device.
- The head count is an estimate with a tolerance, not an exact count; the photo is discarded and D cannot be edited.
- The homework review page has no PIN in the demo; peers are anonymised in the prompt and the output.
- Real time is polling (1-3 s); there is no offline-first mode.
- With the quick tunnel, the address changes at each start.
- F4 is not implemented (pending).
