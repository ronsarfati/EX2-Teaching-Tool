# HereOrNot - a web-based teaching tool

**HereOrNot** ("here or not") is a KISS smartphone web app for teaching in class: attendance first, plus live comments, quick polls, ML video
summaries and LLM homework reviews.

Course assignment: *Introduction to Software Engineering (OOP/OOD)*, Ex2 "Vibe Coding & Deep Designing:
Web-based Teaching Tool".

Look and feel (D38): phone-first student pages, a lecturer dashboard split into "In class now" and "After class", a projector page with QR, code and three steps, light and dark themes (lecturer toggle), Hebrew and English text, system fonts and no external resource. The assignment is a **design challenge**; the implementation is secondary and reuses
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

All five features are designed and implemented in the demo app; F1 is built first and is the most robust part (D1).
F4 (video summary) was first deferred (D10) and is implemented since D34 (23/11).

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
- **F4 Video summary** (D34, closes D10): on the PIN-protected page "Video summary" the lecturer uploads a recording
  (video or audio, up to 2 GB, this page only). `ffmpeg` extracts the audio, `faster-whisper` (`small`) transcribes it
  on the laptop in **one background job at a time**, and Claude writes a structured summary in four sections (topics
  covered, key notions, definitions and examples, what to review) in the language of the lecture. A status page
  shows the step; the result is shown and downloadable as `.md` and `.txt` (R7, R8). The recording and its audio
  are deleted right after transcription, the transcript is never stored, only the summary text is kept (R16, D21).
  No pre-computed output (D1). Limits and controls of D36: recordings above 4 hours are refused, a Cancel button stops an
  active job, LLM calls are retried up to 3 times.
- **F5 Homework review** (D11): public repository URL, capped text extract, LLM review against a short rubric,
  comparison with 1-2 other submissions shown **anonymised** ("Submission B, C"); runs live, no pre-computed output.
- Student identity = self-chosen **nickname** entered once, remembered by a random device token (D6), signed by the server and mirrored on the phone (cookie, localStorage, IndexedDB) so that clearing cookies does not give a second check-in (D37). Still possible: clearing all site data, private browsing, a second browser; the head-count alert is the safety net. Lecturer pages
  protected by a single PIN (D22).

### Out of scope

- Integration with Moodle, Zoom, Meet or Google Classroom; the recording is an uploaded file (R15).
- Personal data: no real names, student IDs, e-mails, face recognition or location; nicknames only (R16, D6, D21).
- User accounts and sign-up (D6, D22).
- Native mobile app (R14).
- Late-arrival handling: check-in happens at the end of class (D5; timing unchanged by D30).
- In-app check-in fallback for a phone that cannot scan (the lecturer adds the student after class, D30) and
  manual correction of the head count (D7).
- A 100 % guarantee of one check-in per person: it would need identifying the student (D5, D37).
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
- **ML / LLM** (D7, D12, D34): local face detector OpenCV YuNet, threshold 0.4 (Ultralytics YOLO tested and
  rejected in the tools report), local audio extraction with `ffmpeg` and transcription with `faster-whisper` (`small`, one background thread), Anthropic Claude for summaries and
  reviews (model and API key from environment variables, never committed).
- **Demo hosting** (D13, D39): app on a laptop exposed with a Cloudflare quick tunnel (public HTTPS URL), started by a one-click launcher; plan B phone
  hotspot; plan C recorded rehearsal.
- **Interface** (D38): server-rendered templates on the vendored Pico CSS plus `app/static/app.css` (design tokens, light and dark), system fonts, Lucide icons; no framework, no build step.

### How to run

**One click (D39, macOS).** Once the setup below is done (virtual environment, `.env`, `cloudflared`, `ffmpeg`), create a Desktop alias and double-click it:

```bash
ln -s "$PWD/scripts/HereOrNot.command" ~/Desktop/HereOrNot.command
```

First launch: right-click the file, then **Open** (macOS asks once to confirm). The launcher starts the Cloudflare quick tunnel, reads its URL, starts the app with that `BASE_URL` (and `PORT`, default 5050) without editing `.env`, waits for `/ping`, opens Safari on the lecturer login and stops everything when its window is closed. If HereOrNot is already running it just opens Safari. `scripts/HereOrNot.command --check` only verifies the prerequisites. The Mac must stay on during class.

**Manual commands (fallback).**

Prerequisites: Python 3.11+ (tested with 3.13) and, optionally, `cloudflared` (to expose the app to phones) and `ffmpeg` (F4 only, for example `brew install ffmpeg`).

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
- `WHISPER_MODEL` (default `small`), `WHISPER_LANGUAGE` (empty = detect the language), `VIDEO_MAX_BYTES` (default 2 GB,
  F4 upload page only) and `VIDEO_WORK_DIR` (temporary files, outside the repository; empty = system temp folder), D34.
- `PORT` (optional): on a Mac set `PORT=5050` and use the same port in `BASE_URL` (macOS AirPlay listens on 5000).
- `ANTHROPIC_API_KEY` (optional): enables the F5 homework review and the F4 summary; without it the page shows an "unavailable" message.

`python -m app` loads `.env` with a small standard-library loader; variables already set in the environment win.

Times (D35, D36-c; the export shows the check-in as date and time `YYYY-MM-DD HH:MM:SS`): every shown time (export, lecturer and projector pages, F4 "Generated on" line) is Israel time (`Asia/Jerusalem`, daylight saving applied); the database and the JSON API stay UTC. This is a constant in `app/timezone.py`, not a setting; `tzdata` is in `requirements.txt`.

Optional face model: for the photo head count, download the YuNet model `face_detection_yunet_2023mar.onnx` from
the official OpenCV `opencv_zoo` repository and place it in `models/` (or set `YUNET_MODEL_PATH`). The model file
is not bundled with this repository.

F4 video summary (D34): install `ffmpeg`. The Whisper `small` model (about 460 MB) is downloaded **once, at the first
summary**, into the Hugging Face cache of the user's home (not in the repository), so the first job is slower and needs
internet. Upload large recordings on `http://localhost:<port>/lecturer/video`, **not through the tunnel**: the free
Cloudflare plan limits a request body to about 100 MB (per its documentation). Measured on a MacBook M3 (T18f,
23/11/2026): a 244 s Hebrew lecture clip took about 70 s (audio 2 s, Whisper `small` about 54 s, Claude 14 s); at the
measured real-time factor of 0.17-0.22 a 90-minute lecture takes roughly 15-20 minutes. Do not start a long
recording during a check-in (shared CPU). The upload needs about twice the file size in free disk space
(Werkzeug spools it before the copy). Recordings above 4 hours are refused (measured with `ffprobe`), a **Cancel** button stops an active job, each Claude call of the job is tried up to 3 times (waits of 2 s then 8 s) (D36). Only one `python -m app` can run at a time (lock file `instance/app.lock`). Optional integration test: `RUN_F4_INTEGRATION=1 python -m pytest -q
tests/test_t18b_integration.py` (needs `ffmpeg` and the cached model).

First step for the lecturer: open the app and sign in with the PIN at `/lecturer/login`.

Phones must reach the laptop. Either use the launcher above, or a Cloudflare quick tunnel
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
| — | Validated decisions D1-D39 | [docs/decisions.md](docs/decisions.md) | Done |
| 1 | Repository, problem and scope | this README | Done |
| 2 | Repository link submitted via the course form | (by the student) | Done |
| 3 | Tools report, every tool tested for real | [docs/tools_report.md](docs/tools_report.md) | Done |
| 4 | Statement of Work | [docs/sow.md](docs/sow.md) | Done |
| 5 | Software Requirements Specification | [docs/srs.md](docs/srs.md) | Done |
| 6 | Use cases (client stories) | [docs/use_cases.md](docs/use_cases.md) | Done |
| 7 | Main software components | [docs/design.md](docs/design.md) (sections 1-2) | Done |
| 8 | Class and sequence diagrams | [docs/design.md](docs/design.md) (sections 3-5) | Done |
| 9 | Test strategy (per class) | [docs/test_strategy.md](docs/test_strategy.md) | Done |
| 10 | Demo KISS web application | [app/](app/), [tests/](tests/) | Done (all five features implemented) |
| 11 | Live demo in class | [docs/demo_script.md](docs/demo_script.md) (with plan B) | Planned |
| 12 | Short description of the results | [docs/results.md](docs/results.md) | Draft (real class figures to be added after the demo) |

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
applied. The icons are copied from **Lucide** (ISC licence; the app loads nothing from the network). The F4 video-summary feature was tried on a public lecture clip that stays local and is not in the repository. Third-party libraries and services used by the app are listed in the tools report.
