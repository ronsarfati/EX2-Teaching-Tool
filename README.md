# Web-based Teaching Tool

A KISS smartphone web app for teaching in class: attendance first, plus live comments, quick polls, ML video
summaries and LLM homework reviews.

Course assignment: *Introduction to Software Engineering (OOP/OOD)*, Ex2 "Vibe Coding & Deep Designing:
Web-based Teaching Tool". The assignment is a **design challenge**; the implementation is secondary and reuses
existing code where possible (R12, R17, R18).

## 1. Problem

Current online teaching tools are too heavy for what happens in a classroom and are not built to use LLMs (R11).
Lecturers need a simple way to know who attended, and students need a simple way to react during and after class.
This project designs, end to end, a set of teaching tools for one real class (R12, R13), all available from
any smartphone browser with no installation (R14):

| # | Feature | Requirements |
|---|---|---|
| F1 | **Attendance (main feature):** students mark their attendance as simply as possible; the lecturer checks it with an automatic head count on a class photo and gets an online/offline spreadsheet | R1-R4 |
| F2 | Students post comments and suggestions in real time or offline | R5 |
| F3 | Lecturers create on-the-spot (KISS) polls on the current material | R6 |
| F4 | Lecturers get an ML summary of a recorded class video | R7, R8 |
| F5 | Students and lecturers get a deep LLM review of a homework, compared with other students' work | R9, R10 |

## 2. Scope

### In scope

All five features are designed. F1, F2, F3 and F5 are implemented in the demo app; F1 is built first and is the
most robust part (D1). F4 (video summary) is designed but its implementation is deferred (D10, decision pending).

- **F1 Attendance (main)**
  - *Projector check-in* (D30): the lecturer opens a session (one click, PIN) and the projector shows a **QR**
    regenerated **every 10 s** and, under it, a **4-digit code** (0000-9999) regenerated **every 5 s**. Students scan
    the QR with the phone's **native camera**, which opens the check-in URL in the browser (no app, no in-page
    scanner). The QR is accepted only if it is **<= 15 s old when the request reaches the server**; the student then
    has a **1-minute window** to type, the first time only, a nickname (D6), then the 4-digit code (the current or the
    previous one, at most 5 attempts), and tap "Confirm". One check-in per device per session. No IP address is read
    or stored and there is no network filter (D33). A student whose camera cannot scan is added manually by the
    lecturer after class in the exported spreadsheet. A chain-of-trust design (students validating each other), a
    local Wi-Fi bubble and a campus-IP filter were studied and rejected (D30, D33).
    Residual risk (D33): a remote student helped by an accomplice in the room can still check in; the photo
    consistency alert below is the room-level check. Guessing the code by rescanning needs about 5,000 tries on average.
  - *Photo head count as a global check* (D7): the lecturer uploads a class photo; OpenCV **YuNet** counts faces only
    (no identification) and the app shows "checked in N / detected D" with an automatic **consistent / anomaly**
    alert. The photo is processed in memory and **discarded**.
  - *Spreadsheet* (D8): live table on the lecturer page (online) and CSV/XLSX download (offline). Columns: session
    date, nickname, check-in time (D6). No client IP address is read or stored (D21, D33).
- **F2 Comments** (D8): real time (visible on the lecturer page within a few seconds, D4) and asynchronous (posted
  outside class, read later).
- **F3 Polls** (D9): one question, 2-4 options, one vote per device, live results, closed by the lecturer.
- **F4 Video summary** (D10, deferred): uploaded video, local transcription, structured LLM summary (topics, key
  points, action items, questions), aiming to beat the Zoom automatic summary (R8); no pre-computed output (D1).
- **F5 Homework review** (D11): public repository URL, capped text extract, LLM review against a short rubric,
  comparison with 1-2 other submissions shown **anonymised** ("Submission B, C"); runs live, no pre-computed output.
- Student identity = self-chosen **nickname** entered once, remembered by a random device token (D6). Lecturer pages
  protected by a single PIN (D22).

### Out of scope

- Integration with Moodle, Zoom, Meet or Google Classroom; the video is an uploaded file (R15).
- Personal data: no real names, student IDs, e-mails, face recognition or location; nicknames only (R16, D6, D21).
- User accounts and sign-up (D6, D22).
- Native mobile app (R14).
- Late-arrival handling: check-in happens at the end of class (D5; timing unchanged by D30).
- In-app check-in fallback for a phone that cannot scan (the lecturer adds the student after class, D30) and
  manual correction of the head count (D7).
- Network-offline mode (PWA / local queue): "offline" means downloadable spreadsheet and asynchronous comments (D8).
- Google Sheets synchronisation (listed as a possible extension, D8).

### Constraints

- KISS: a simple smartphone web app, few taps, no installation (R14).
- Must work in this class, in a **live 10-minute demo** (R13, R19).
- Only design what can be implemented (R17).
- Compose existing tools and libraries rather than code from scratch (R18, R33).

## 3. Approach and tech stack

- **Back end and UI** (D2): Python 3.11+, Flask, server-rendered mobile-first HTML, small vanilla JavaScript.
- **Storage** (D3): SQLite (standard library `sqlite3`), one local file, git-ignored.
- **Real time** (D4): short polling every 2-3 s on student and lecturer pages, every 1 s on the projector page (QR and code, D31); no WebSockets.
- **Attendance** (D30): rotating signed QR tokens (stdlib `hmac`), QR images generated server-side with `qrcode`;
  no QR-decoding library in the app (the phone's native camera scans); projected 4-digit code (D33); no IP-based
  check.
- **ML / LLM** (D7, D10, D12): local face detector OpenCV YuNet, threshold 0.4 (Ultralytics YOLO tested and
  rejected in the tools report), local transcription with `faster-whisper`, Anthropic Claude for summaries and
  reviews (model and API key from environment variables, never committed).
- **Demo hosting** (D13): app on a laptop exposed with a Cloudflare quick tunnel (public HTTPS URL); plan B phone
  hotspot; plan C recorded rehearsal.

### How to run

Prerequisites: Python 3.11+ (tested with 3.13) and, optionally, `cloudflared` (to expose the app to phones).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env (git-ignored)
python -m app               # serves on 0.0.0.0, port $PORT (default 5000; on macOS use PORT=5050, AirPlay takes 5000)
```

In `.env` set:

- `SECRET_KEY`: a long random string.
- `LECTURER_PIN`: the lecturer PIN; use a long one (D22).
- `BASE_URL`: the public URL phones will use (`http://localhost:5000` locally, the tunnel URL for the demo).
- `PORT` (optional): on a Mac set `PORT=5050` and use the same port in `BASE_URL` (macOS AirPlay listens on 5000).
- `ANTHROPIC_API_KEY` (optional): enables the F5 homework review; without it the page shows an "unavailable" message.

`python -m app` loads `.env` with a small standard-library loader; variables already set in the environment win.

Optional face model: for the photo head count, download the YuNet model `face_detection_yunet_2023mar.onnx` from
the official OpenCV `opencv_zoo` repository and place it in `models/` (or set `YUNET_MODEL_PATH`). The model file
is not bundled with this repository.

First step for the lecturer: open the app and sign in with the PIN at `/lecturer/login`.

Phones must reach the laptop. Either use a Cloudflare quick tunnel
(`cloudflared tunnel --url http://localhost:5000`, then put the printed URL in `BASE_URL` and restart the app), or
a phone hotspot. See
[docs/demo_script.md](docs/demo_script.md).

Tests: `python -m pytest -q`.

Optional demo data (fictional nicknames only, no network, no API key; existing files are not overwritten without
`--force`): `python scripts/seed_demo.py [DB_PATH] [--force]`.

## 4. Deliverables

| To Do | Deliverable | Location | Status |
|---|---|---|---|
| — | Requirements R1-R37 | [docs/requirements.md](docs/requirements.md) | Done |
| — | Validated decisions D1-D33 | [docs/decisions.md](docs/decisions.md) | Done |
| 1 | Repository, problem and scope | this README | Done |
| 2 | Repository link submitted via the course form | (by the student) | Planned |
| 3 | Tools report, every tool tested for real | [docs/tools_report.md](docs/tools_report.md) | Done |
| 4 | Statement of Work | [docs/sow.md](docs/sow.md) | Done |
| 5 | Software Requirements Specification | [docs/srs.md](docs/srs.md) | Done |
| 6 | Use cases (client stories) | [docs/use_cases.md](docs/use_cases.md) | Done |
| 7 | Main software components | [docs/design.md](docs/design.md) (sections 1-2) | Done |
| 8 | Class and sequence diagrams | [docs/design.md](docs/design.md) (sections 3-5) | Done |
| 9 | Test strategy (per class) | [docs/test_strategy.md](docs/test_strategy.md) | Done |
| 10 | Demo KISS web application | [app/](app/), [tests/](tests/) | In progress |
| 11 | Live demo in class | demo script (with plan B) | Planned |
| 12 | Short description of the results | [docs/results.md](docs/results.md) | Planned |

## 5. Privacy

- No personal data in this repository, in its history, or in the demo: fictitious nicknames and non-personal test
  images only (R16, D21).
- The files provided for the course (participant list, class photos, class video, list of homework repositories)
  are used **locally only**; only aggregate numbers (e.g. head-count accuracy) are reported.
- Class photos taken during the demo are processed in memory and discarded; only the count is kept (D7).
- Secrets (API keys, lecturer PIN) live in a git-ignored `.env`; a `.env.example` with placeholders is provided (D12, D22).

## 6. Tools used

This project was designed and built with the help of **Claude Code** (Anthropic) AI agents, working under the
student's direction. The agents drafted the requirements, decisions, documents and code; the student defined the
key design choices (e.g. the projector QR + 4-digit code check-in, D30, D33) and reviewed and validated every decision before it was
applied. Third-party libraries and services used by the app are listed in the tools report.
