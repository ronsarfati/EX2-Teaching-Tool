# Statement of Work (To Do 4)

Covers R26. Requirements are cited as R1-R37 ([requirements.md](requirements.md)), validated decisions as D1-D34
([decisions.md](decisions.md); D5 and D26 are superseded by D30).

## 1. Purpose and background

Current online teaching tools are heavy and not "LLM-ready" (R11). This project designs, end to end, a KISS web
application for teaching in one real class, used by students from their smartphone browser with no installation
(R12-R14), and demonstrates it live in class (R13, R19, R34). The assignment is a **design challenge**: the
implementation is secondary and composes existing tools rather than coding from scratch (R17, R18, R33).

## 2. Objectives

| # | Objective | R / D |
|---|---|---|
| O1 | Attendance (main feature): check-in from the phone (projector QR + 4-digit code), automatic photo head count with a consistency alert, online table + offline CSV/XLSX | R1-R4, D6-D8, D30 |
| O2 | Comments and suggestions, real time and asynchronous | R5, D4, D8 |
| O3 | On-the-spot KISS polls | R6, D9 |
| O4 | ML summary of a recorded class video, better than the Zoom automatic summary | R7, R8, D34 (closes D10): upload of a recording of any length, local transcription in a background job, structured summary |
| O5 | LLM homework review with anonymised comparison to other submissions | R9, R10, D11 |
| O6 | Complete design documentation (tools report, SoW, SRS, use cases, components, class and sequence diagrams, test strategy) | R24-R32, D14 |
| O7 | A 10-minute live demo in class and a short results description | R19, R34, R35, D17 |

## 3. Scope

**In scope** (D1): all five features designed; F1, F2, F3 and F5 implemented in one Flask app (D2) with SQLite storage (D3); F1
first and most robust. Attendance follows D30: the lecturer opens a session and the projector shows a QR
regenerated every 10 s and a 4-digit code regenerated every 5 s; students scan the QR with the phone's native
camera; the QR is accepted if at most 15 s old on arrival, then the student has a 1-minute window to type the code
(current or previous one, at most 5 attempts); no IP address is read and there is no network filter (D33); one check-in per device per session; a student who cannot scan is added by the lecturer
after class in the exported spreadsheet. A chain-of-trust design and a local Wi-Fi bubble were studied and
rejected (D30); a campus-IP filter was tested and abandoned (D33). Identity is a nickname plus a random device token (D6); lecturer pages are protected by a single
PIN (D22). F4 was planned last and deferred (D10); it is implemented since D34 (23/11): recordings of any length,
background job with a status page, one job at a time, recording and transcript never kept (R16).

**Out of scope:** Moodle, Zoom, Meet or Google Classroom integration (R15); personal data of any kind, including
real names, IDs, e-mails, face recognition and location (R16, D6, D21); user accounts (D6, D22); native mobile app
(R14); late-arrival handling (D5); network-offline mode (PWA) and Google Sheets sync (D8); pre-computed ML/LLM
outputs (D1, D10, D11); in-app check-in fallback for a phone that cannot scan (D30); manual correction of the
head count (D7).

## 4. Deliverables

| To Do | Deliverable | Location (D14) | R |
|---|---|---|---|
| 1 | Repository; problem and scope in the README | `README.md` | R20-R22 |
| 2 | Repository link submitted via the course form (by the student only) | — | R23, D18 |
| 3 | Tools report, every suggested tool tested for real | `docs/tools_report.md` | R24, R25, D15 |
| 4 | Statement of Work | `docs/sow.md` (this file) | R26 |
| 5 | Software Requirements Specification | `docs/srs.md` | R27 |
| 6 | Use cases (client stories) | `docs/use_cases.md` | R28 |
| 7 | Main software components | `docs/design.md` | R29 |
| 8 | Class and sequence diagrams (Mermaid) | `docs/design.md` | R30, R31 |
| 9 | Test strategy per class/component | `docs/test_strategy.md` | R32, D25 |
| 10 | Demo KISS web application with tests | `app/`, `tests/`, `demo_data/`, `requirements.txt`, `.env.example` | R33 |
| 11 | Live 10-minute demo in class, with plan B | demo script | R19, R34, D13 |
| 12 | Short description of the results | `docs/results.md` | R35, D17 |

## 5. Approach

- **Design first:** requirements (R1-R37) and validated decisions (D1-D34) precede SRS, use cases and design; code
  only implements what is designed (R17).
- **Compose existing tools:** Flask, `qrcode`, OpenCV YuNet, `ffmpeg`, faster-whisper, Anthropic SDK, `openpyxl`,
  `cloudflared`, each tested for real in the tools report before adoption (R18, R25, D15).
- **AI-assisted, student-validated:** AI agents (Claude Code) draft documents, code and tests; the student defines
  the key design choices (e.g. D30) and validates every decision and deliverable. AI use is disclosed in the README.
- **Incremental delivery:** feature order F1 > F3 > F2 > F5 > F4 (D1); each task is coded, then tested with pytest
  and the Flask test client (D25); frequent small commits (D24).

## 6. Schedule (22/11 - 30/11/2026, D16, D17)

| Date | Milestone |
|---|---|
| 22/11 | Requirements, decisions, README (To Do 1), tools report (To Do 3) — done |
| 23/11 | SoW, SRS, use cases (To Do 4-6) |
| 24/11 | Components, class and sequence diagrams, test strategy (To Do 7-9) |
| 25-26/11 | F1 attendance: check-in (QR + code), head count and consistency alert, spreadsheet (To Do 10) |
| 26/11 | F2 comments, F3 polls |
| 27/11 | F5 homework review, then F4 video summary (D34, T18a-T18f; done 23/11, real trial T18f) |
| 28/11 | Quality review, fixes, tests on real phones through the tunnel |
| 29/11 | Demo data and script with plan B, full rehearsal, results description, final verification (To Do 11-12) |
| 30/11 | Margin; the student submits the repository link (To Do 2) |

## 7. Roles

| Role | Responsibility |
|---|---|
| Student (owner) | Decision maker: validates every decision and deliverable, runs the manual phone tests, publishes the repository, submits the form, performs the demo (D18, D20, D24) |
| AI agents | Draft documents, code and tests under the student's direction; never push or submit (D24) |
| Lecturer (client, evaluator) | Defines the needs (assignment statement), gives feedback (e.g. on D5, later replaced by D30), evaluates the deliverables and the demo |

## 8. Assumptions and constraints

- No personal data in the repository, its history or the demo; provided course files are used locally only and
  only aggregate numbers are reported (R16, D21).
- KISS smartphone web app, few taps, no installation (R14); only implementable designs (R17).
- Demo hosted on the student's laptop, exposed by a Cloudflare quick tunnel (D13).
- Students may be on the university Wi-Fi or on mobile data; the check-in does not depend on the network (D33).
- An Anthropic API key is available for F4/F5; without it F1-F3 still run and F4/F5 show a plain error (D12, D23). F4 also needs `ffmpeg` and a one-time download of the Whisper `small` model (about 460 MB, D34).
- Individual work (D20); deadline 30/11/2026 (D16); the class demo date is still to be confirmed (D17).

## 9. Risks and mitigations

| Risk | Mitigation | D |
|---|---|---|
| A phone cannot scan the QR (camera, old OS) | Native camera only, no in-page scanner or permission prompt; tested on real phones before the demo; otherwise the lecturer adds the student manually after class in the exported spreadsheet | D30 |
| Classroom network or tunnel fails | Plan B: phone hotspot over HTTP (no in-page camera needed); plan C: recorded rehearsal; QR codes encode the configured base URL | D13 |
| Check-in takes too long or distracts the class (lecturer's concern) | One click for the lecturer; every student scans the same projector QR in parallel; 1-minute window to type the code; whole-class duration measured live and reported | D17, D30 |
| A remote student checks in with a live accomplice who relays the QR and the code | Residual risk accepted (D33): code changes every 5 s, 1-minute window, 5 attempts, one check-in per device; the photo consistency alert flags the gap (D7 limit applies). Guessing the code by rescanning needs about 5,000 tries on average | D7, D30, D33 |
| Head count misses hidden faces | Measured recall ~94 %, precision ~96 % on 4 provided photos (tools report 2.5); asymmetric consistency alert; advice to shoot when students look up; limit stated (fraud under ~7 absent check-ins for N ≈ 45 stays in the noise) | D7 |
| LLM API unavailable, slow or costly | Short capped inputs; one call per request; plain error message, no canned output; model configurable by env var | D11, D12, D23 |
| F4 too slow live | Background job, one at a time; no time promised (NFR-13); measured 70 s for a 244 s clip with `small` (T18f), roughly 15-20 min for 90 min; the demo starts a short clip during the polls and keeps a pre-made summary as plan B; upload on localhost (the free tunnel limits a request to about 100 MB) | D34 |

## 10. Acceptance criteria

| # | Criterion | R |
|---|---|---|
| A1 | A student checks in from a phone browser (native camera, 4-digit code, no install) and appears in the lecturer's live list | R1, R14, D30, D33 |
| A2 | A class photo returns a head count and a consistent/anomaly status next to the number of check-ins; the photo is not stored | R2, R16, D7 |
| A3 | The lecturer sees the attendance table online and downloads it as CSV/XLSX | R3, D8 |
| A4 | A comment posted from a phone appears on the lecturer page within 5 s; a comment posted outside a session is visible later | R5, D4, D8 |
| A5 | The lecturer creates a poll, students vote from phones, live results are shown | R6, D9 |
| A6 | A video file produces a structured summary, compared with the Zoom example in the results | R7, R8, D34 (summary in four sections, shown and downloadable; comparison with the Zoom example in `docs/results.md`) |
| A7 | A public repository URL produces an LLM review with an anonymised comparison to at least one other submission when one is available (otherwise the review says so, D31) | R9, R10, D11, D31 |
| A8 | Every document of To Do 3-9 and 12 exists in `docs/` and is linked from the README | R24-R32, R35, D14 |
| A9 | The app runs from a fresh clone following the README; the pytest suite passes | R33, R37, D25 |
| A10 | The live demo shows F1 first and fits in 10 minutes, with a plan B | R4, R19, R34, D13 |
| A11 | No personal data or secret in the repository or its history | R16, D21, D24 |
| A12 | Everything committed and the link submitted by 30/11/2026 | R23, R36, R37, D16 |
