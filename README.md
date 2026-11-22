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

All five features are designed **and** implemented in the demo app; F1 is built first and is the most robust
part (D1).

- **F1 Attendance (main)**
  - *Chain-of-trust check-in at the end of class* (D5): the lecturer opens a session and shows a QR code to one or a
    few students; each checked-in student's phone then shows its own QR code and can sponsor up to 3 nearby
    classmates, and so on. All QR codes rotate **every 10 s** and expired codes are rejected server-side, so a
    forwarded screenshot is useless. The app stores who validated whom (**sponsor tree**). The lecturer can validate
    any number of students directly, then closes the session.
  - *Photo head count as a global check* (D7): the lecturer uploads a class photo; the app counts heads only (no
    identification), shows "checked in N / counted M / difference", and **discards the photo** (processed in memory).
  - *Spreadsheet* (D8): live table on the lecturer page (online) and CSV/XLSX download (offline). Columns: session
    date, nickname, check-in time, sponsor (D6).
- **F2 Comments** (D8): real time (visible on the lecturer page within a few seconds, D4) and asynchronous (posted
  outside class, read later).
- **F3 Polls** (D9): one question, 2-4 options, one vote per device, live results, closed by the lecturer.
- **F4 Video summary** (D10): uploaded video, local transcription, structured LLM summary (topics, key points,
  action items, questions), aiming to beat the Zoom automatic summary (R8).
- **F5 Homework review** (D11): public repository URL, capped text extract, LLM review against a short rubric,
  comparison with 1-2 other submissions shown **anonymised** ("Submission B, C").
- Student identity = self-chosen **nickname** entered once, remembered by a random device token (D6). Lecturer pages
  protected by a single PIN (D22).

### Out of scope

- Integration with Moodle, Zoom, Meet or Google Classroom; the video is an uploaded file (R15).
- Personal data: no real names, student IDs, e-mails, face recognition or location; nicknames only (R16, D6, D21).
- User accounts and sign-up (D6, D22).
- Native mobile app (R14).
- Late-arrival handling: check-in happens at the end of class (D5).
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
- **Real time** (D4): short polling every 2-3 s (also refreshes the rotating QR codes); no WebSockets.
- **ML / LLM** (D7, D10, D12): local head detector (OpenCV YuNet or Ultralytics YOLO, chosen by measurement in the
  tools report), local transcription with `faster-whisper`, Anthropic Claude for summaries and reviews (model and
  API key from environment variables, never committed).
- **Demo hosting** (D13): app on a laptop exposed with a Cloudflare quick tunnel (public HTTPS URL); plan B phone
  hotspot / LAN; plan C recorded rehearsal.

### How to run

Coming with the demo app (To Do 10).

## 4. Deliverables

| To Do | Deliverable | Location | Status |
|---|---|---|---|
| — | Requirements R1-R37 | [docs/requirements.md](docs/requirements.md) | Done |
| — | Validated decisions D1-D25 | [docs/decisions.md](docs/decisions.md) | Done |
| 1 | Repository, problem and scope | this README | Done |
| 2 | Repository link submitted via the course form | (by the student) | Planned |
| 3 | Tools report, every tool tested for real | [docs/tools_report.md](docs/tools_report.md) | Done |
| 4 | Statement of Work | [docs/sow.md](docs/sow.md) | Planned |
| 5 | Software Requirements Specification | [docs/srs.md](docs/srs.md) | Planned |
| 6 | Use cases (client stories) | [docs/use_cases.md](docs/use_cases.md) | Planned |
| 7 | Main software components | [docs/design.md](docs/design.md) | Planned |
| 8 | Class and sequence diagrams | [docs/design.md](docs/design.md) | Planned |
| 9 | Test strategy (per class) | [docs/test_strategy.md](docs/test_strategy.md) | Planned |
| 10 | Demo KISS web application | [app/](app/), [tests/](tests/) | Planned |
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
key design choices (e.g. the chain-of-trust check-in, D5) and reviewed and validated every decision before it was
applied. Third-party libraries and services used by the app are listed in the tools report.
