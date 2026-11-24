# Results (To Do 12) - draft

Status: written from the code and tests as of 2026-11-23. Figures from the live class are placeholders and are
filled in only after the demo; nothing below is estimated.

## 1. Setup

- App: Python 3.13, Flask, SQLite, OpenCV YuNet (face count), `ffmpeg` and faster-whisper (`small` model) for the F4 video summary, Anthropic Claude (review and summary); see the README.
- Demo environment: laptop running the app; public HTTPS address from a Cloudflare quick tunnel (plan A) or phone hotspot
  (plan B); students on their own phones.
- Demo data: fictional only (`scripts/seed_demo.py`); no personal data in the repository (D21).

## 2. What was built (state of the code)

| Feature | State |
|---|---|
| F1 Attendance: projector QR (10 s) + 4-digit code (5 s), live table, photo head count with consistent/anomaly alert, CSV/XLSX export | Implemented, tested |
| F2 Comments (real-time and later) | Implemented, tested |
| F3 Polls (one vote per device, signed device token mirrored on the phone, D37, live results, close) | Implemented, tested |
| F5 Homework review with anonymised comparison (public GitHub URL, Claude) | Implemented, tested with fakes; live call needs an API key [to fill after the class demo] |
| F4 Video summary (upload, ffmpeg, Whisper `small`, Claude, background job, status page, `.md`/`.txt` download; D34; 4 h cap, Cancel button, LLM retries, D36) | Implemented, tested with fakes; one real end-to-end trial (section 3) |
| UI redesign (HereOrNot, D38: identity, dashboard, student, projector and lecturer pages, theme toggle) and one-click launcher (D39) | Implemented, tested (`tests/test_t22_*.py`, `tests/test_launcher.py`); check on real phones (M13) still to be recorded |

## 3. Measured figures

Automated tests (24/11, after D39, `python -m pytest -q --cov=app`): 1364 passed, 1 skipped (the opt-in F4 integration test,
`RUN_F4_INTEGRATION=1`); statement coverage of `app/` 99 %.

Scripted local trial (23/11, after D33, real server on the laptop, QR decoded from the projector image): wrong code refused (400), right 4-digit code accepted, second check-in from the same phone refused (409), 3-digit input refused, second phone accepted, removed allow-list page answers 404, no client address in the server log. Earlier trial scope (before D33): (check-in with QR and code, repeated check-in refused, wrong code
refused, expired or forged QR refused, live table API, poll, comments, CSV and XLSX exports, photo upload without the
model answering 503, review without a key answering 503). This trial is not a class result.

Photo head count accuracy (from the tools report, 4 provided class photos checked box by box, threshold 0.4): recall
94 %, precision 96 %, mean error 2.5 people, under 0.1 s per photo. These photos are not in the repository.

F4 real trial (T18f, 23/11/2026, MacBook M3, full HTTP stack, upload on localhost): a 244 s Hebrew lecture clip (a public
university lecture, kept local only, not in the repository) was summarised in about 70 s: audio extraction 2 s,
transcription with Whisper `small` about 54 s, Claude summary 14 s. The summary was faithful to the lecture, in four
sections with headings in the lecture language (Hebrew); the `.md` and `.txt` downloads worked; the work directory was
empty afterwards and the database kept only the summary text (FR-4.5). D36 check (24/11): `ffprobe` measured 244.4 s for this clip, well under the 4 h cap; a fake `.mp4` gives no duration. Earlier measure (tools report 2.6): real-time
factor of `small` about 0.17-0.22, so a 90-minute lecture takes roughly 15-20 minutes (NFR-13); this 90-minute
figure is an extrapolation, not a measured run.

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
| F4 summary: clip length, processing time, plan B used? | [to fill after the class demo] |
| Plan B used? Incidents | [to fill after the class demo] |

## 4. Observations

- Design: all external services sit behind interfaces (`HeadCounter`, `LLMClient`, `RepoFetcher`, `Clock`, `Transcriber`, `AudioExtractor`, `JobRunner`), so the
  whole suite runs offline and F1-F3 work without any key.
- Field findings before the demo (23/11): a campus-IP filter and Apple's Private Relay list were tested on site and
  abandoned (D33, tools report 2.12); the check-in relies on the rotating QR and the 4-digit code instead.
- Local trial: [to fill after the class demo] for observations from the real class.
- F4 versus the Zoom example summary (R8, qualitative; the Zoom example is local only and its content is not reproduced):
  the Zoom example is a quick recap plus next steps; ours gives four study sections (topics covered, key notions,
  definitions and examples, what to review) in the lecture language. Ours works on any recording, offline from Zoom
  (no Zoom integration, R15), and the audio stays on the laptop (R16). No quantitative comparison was made, and the
  quality judgement comes from one trial on one clip.

## 5. Limits

- Presence is a device that scanned the projector QR and typed the code shown in the room; nothing proves the device
  is in the room (D33). A remote student with a live accomplice can check in; only the head count alert reveals a
  gap globally. Guessing the 4-digit code by rescanning needs about 5,000 tries on average.
- Nicknames are not verified. The device token is signed and mirrored in cookie, localStorage and IndexedDB (D37): clearing the cookies alone does not give a second check-in; clearing all site data, private browsing, a second browser or disabling JavaScript still does.
- The head count is an estimate with a tolerance, not an exact count; the photo is discarded and D cannot be edited.
- The homework review page has no PIN in the demo; peers are anonymised in the prompt and the output.
- Real time is polling (1-3 s); there is no offline-first mode.
- With the quick tunnel, the address changes at each start.
- F4: a 90-minute lecture takes about 15-20 minutes (extrapolated, NFR-13); one job at a time; the summary is a model output checked on one clip only; the first use downloads the `small` model (about 460 MB); uploads above about 100 MB must go through localhost, not the free tunnel.
