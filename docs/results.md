# Results (To Do 12) - draft

Status: written from the code and tests as of 2026-11-23. Figures from the live class are placeholders and are
filled in only after the demo; nothing below is estimated.

## 1. Setup

- App: Python 3.13, Flask, SQLite, OpenCV YuNet (face count), Anthropic Claude (review); see the README.
- Demo environment: laptop running the app; public HTTPS address from a Cloudflare quick tunnel (plan A) or phone hotspot
  (plan B); students on their own phones.
- Demo data: fictional only (`scripts/seed_demo.py`); no personal data in the repository (D21).

## 2. What was built (state of the code)

| Feature | State |
|---|---|
| F1 Attendance: projector QR (10 s) + 4-digit code (5 s), live table, photo head count with consistent/anomaly alert, CSV/XLSX export | Implemented, tested |
| F2 Comments (real-time and later) | Implemented, tested |
| F3 Polls (one vote per device, live results, close) | Implemented, tested |
| F5 Homework review with anonymised comparison (public GitHub URL, Claude) | Implemented, tested with fakes; live call needs an API key [to fill after the class demo] |
| F4 Video summary | Not implemented (T18 deferred, pending decision) |

## 3. Measured figures

Automated tests (23/11, after D33): 913 passed, 2 skipped (the 2 skipped tests need the YuNet model file); statement
coverage of `app/` 98 % (1,228 statements).

Scripted local trial (23/11, after D33, real server on the laptop, QR decoded from the projector image): wrong code refused (400), right 4-digit code accepted, second check-in from the same phone refused (409), 3-digit input refused, second phone accepted, removed allow-list page answers 404, no client address in the server log. Earlier trial scope (before D33): (check-in with QR and code, repeated check-in refused, wrong code
refused, expired or forged QR refused, live table API, poll, comments, CSV and XLSX exports, photo upload without the
model answering 503, review without a key answering 503). This trial is not a class result.

Photo head count accuracy (from the tools report, 4 provided class photos checked box by box, threshold 0.4): recall
94 %, precision 96 %, mean error 2.5 people, under 0.1 s per photo. These photos are not in the repository.

Live class demo:

| Measure | Value |
|---|---|
| Class date and place | [to fill after the class demo] |
| Students who checked in (N) | [to fill after the class demo] |
| Faces detected on the class photo (D) and alert status | [to fill after the class demo] |
| Duration of the whole-class check-in (open to last row) | [to fill after the class demo] |
| Refusals (expired QR, expired window, wrong code) | [to fill after the class demo] |
| Poll: participants and time to results | [to fill after the class demo] |
| Comments received and delay before they appeared | [to fill after the class demo] |
| F5 review: repository, time to answer, quality of the comparison | [to fill after the class demo] |
| Plan B used? Incidents | [to fill after the class demo] |

## 4. Observations

- Design: all external services sit behind interfaces (`HeadCounter`, `LLMClient`, `RepoFetcher`, `Clock`), so the
  whole suite runs offline and F1-F3 work without any key.
- Field findings before the demo (23/11): a campus-IP filter and Apple's Private Relay list were tested on site and
  abandoned (D33, tools report 2.12); the check-in relies on the rotating QR and the 4-digit code instead.
- Local trial: [to fill after the class demo] for observations from the real class.
- F4 versus the Zoom example summary: [to fill after the class demo] / not applicable if F4 stays deferred (pending).

## 5. Limits

- Presence is a device that scanned the projector QR and typed the code shown in the room; nothing proves the device
  is in the room (D33). A remote student with a live accomplice can check in; only the head count alert reveals a
  gap globally. Guessing the 4-digit code by rescanning needs about 5,000 tries on average.
- Nicknames and device tokens are not verified; clearing cookies gives a new device.
- The head count is an estimate with a tolerance, not an exact count; the photo is discarded and D cannot be edited.
- The homework review page has no PIN in the demo; peers are anonymised in the prompt and the output.
- Real time is polling (1-3 s); there is no offline-first mode.
- With the quick tunnel, the address changes at each start.
- F4 is not implemented (pending).
