# Decisions — Ex2 "Web-based Teaching Tool"

Resolutions of the open questions (OQ1-OQ14 in `docs/requirements.md`) and of the technical choices left open by
the statement. Proposed by the ambiguity analysis, **validated by the student on 2026-11-22**.
Requirements are cited as R<n>, statement locators as F/Req/G/TD/QA (see `docs/requirements.md`).

Guiding rule: the **simplest option that fully satisfies the requirements** (KISS, Req2), that can really be
implemented and shown live (G2, Req1), reusing existing code (Note, G3, TD10), with **no personal data** (G1, QA6),
within the days available (22/11 to 26/11/2026). No over-design (lesson from Ex1).

Legend: **[ASK]** = still worth confirming with the lecturer/TA.

## Summary

| D | Topic | Decision | Status |
|---|---|---|---|
| D1 | Demo scope (OQ1) | All 5 features fully implemented; F1 first and most robust; pre-computed F4/F5 output only as demo plan B | VALIDATED |
| D2 | Tech stack | Python 3.11+ / Flask, server-rendered mobile-first HTML + small vanilla JS | VALIDATED |
| D3 | Storage | SQLite (stdlib `sqlite3`), one local file, git-ignored | VALIDATED |
| D4 | Real time | Short polling (2-3 s); no websockets | VALIDATED |
| D5 | Attendance mechanism (OQ2) | Chain-of-trust check-in at end of class: rotating (10 s) phone-to-phone QR codes, max 3 sponsored per student, sponsor tree stored | VALIDATED — awaiting lecturer confirmation [ASK] |
| D6 | Student identity (OQ4) | Nickname entered once, remembered by a random device token (cookie/localStorage); automatic recognition afterwards | VALIDATED |
| D7 | Photo head count (OQ3) | Count only; photo processed in memory and discarded; YuNet vs YOLO chosen by tools-report measurements | VALIDATED |
| D8 | Spreadsheet online/offline; offline comments (OQ5) | Live in-app table + CSV/XLSX download; F2 offline = asynchronous | VALIDATED |
| D9 | Polls (F3) | One question, 2-4 options, one vote per token, live results | VALIDATED |
| D10 | Video summary F4 (OQ6) | Local transcription (faster-whisper) + Claude summary | VALIDATED |
| D11 | Homework review F5 (OQ6) | Public repo URL -> capped text extract -> Claude review + anonymised comparison with 1-2 other repos | VALIDATED |
| D12 | LLM provider and secrets | Anthropic (Claude), fast/cheap model configurable by env var; key in `.env` | VALIDATED |
| D13 | Demo hosting (OQ7) | Laptop + Cloudflare quick tunnel; plan B hotspot/LAN; plan C recorded run | VALIDATED |
| D14 | Documents format and layout (OQ11) | Markdown in `docs/`, one file per deliverable, Mermaid, README links all | VALIDATED |
| D15 | Tools report (OQ12) | Every tool we suggest, tested for real with command, input, result, date, version | VALIDATED |
| D16 | Deadline (OQ8) | 26/11/2026 (confirmed by the student) | VALIDATED |
| D17 | Demo date and results (OQ9) | Demo-ready by 25/11; results from rehearsal, updated after class demo if allowed | VALIDATED [ASK] |
| D18 | Submission channel (OQ10) | Google Form, filled by the student only; check Moodle for an extra upload | VALIDATED [ASK] |
| D19 | Live statement (OQ13) | Re-read the live Google Doc at Phase 2 and before submission | VALIDATED |
| D20 | Individual vs team (OQ14) | Individual work | VALIDATED |
| D21 | Personal data (R16) | Fictitious data in repo/demo; provided files local only, aggregate results only | VALIDATED |
| D22 | Lecturer access | Single lecturer PIN from an env var; no accounts | VALIDATED |
| D23 | Error messages | Plain user messages, no internal identifiers/stack traces; details in server log | VALIDATED |
| D24 | Git practice | Frequent small commits 22-26/11, conventional messages, no `Co-Authored-By` trailer, agents never push | VALIDATED |
| D25 | Test tooling | pytest + Flask test client; ML/LLM mocked; detector tested on non-personal images | VALIDATED |

"VALIDATED" = "VALIDATED by the student — 2026-11-22" unless stated otherwise.

---

## D1 — Demo scope (OQ1; R4, R5-R10, R12, R17, R19, R33)

**Question.** Must all five features be implemented in the demo app, or only designed?

**Options.** 1. *All five fully implemented.* 2. *F1 only, F2-F5 design only* (weak demo, Req1). 3. *F1 complete, F2-F3 simple, F4-F5 thin wrappers with pre-computed fallback* (initial proposal).

**DECISION: option 1 (changed by the student).**
- All five features are fully designed **and** fully implemented (real working paths, not thin wrappers).
- F1 (R1-R3: chain-of-trust check-in D5, photo head count D7, live table + CSV/XLSX D8, check-ins vs counted comparison) is built **first** and is the most robust part.
- F2 (D8), F3 (D9), F4 (D10), F5 (D11) are real implementations.
- Pre-computed F4/F5 results are kept **only as demo plan B** if the API or the network fails, clearly labelled "pre-computed".
- No extra features (no accounts, no analytics, no notifications, no PWA offline mode).

**Justification.** F1 "is the main (most important) feature"; Req1 "should work in this class"; G2 "only design what can be implemented"; reuse of existing libraries (Note) keeps the full scope feasible.

**Impact.** README scope (R22) and SoW schedule list all five; task order F1 > F3 > F2 > F4 > F5; test strategy weights F1; demo script (R19) has a plan B for F4/F5.

**Status:** VALIDATED by the student — 2026-11-22

## D2 — Tech stack (R14, R17, R18, R33)

**Options.** 1. *Python + Flask, Jinja templates, small vanilla JS, classless CSS (e.g. Pico.css).* 2. *Streamlit* (poor for many concurrent phones, weak OO design). 3. *Node.js/Express* (ML parts are Python-first). 4. *No-code Google Forms/Sheets* (accounts, no photo count, little to design).

**DECISION: option 1**, Python 3.11+.

**Justification.** Req2 "simple smartphone app (web-based application)"; all ML reuse (OpenCV, faster-whisper, Anthropic SDK) is Python.

**Impact.** Class diagrams are Python classes; `requirements.txt` pinned.

**Status:** VALIDATED by the student — 2026-11-22

## D3 — Storage (R3, R5, R6)

**DECISION:** SQLite via stdlib `sqlite3`, database file under `instance/` (git-ignored); repository classes isolate SQL; no ORM. Rejected: CSV/JSON files (concurrency), Google Sheets as DB (accounts, network dependence).

**Impact.** Spreadsheet export generated from SQLite (D8); demo DB seeded with fictitious data (D21).

**Status:** VALIDATED by the student — 2026-11-22

## D4 — Real-time mechanism (R5, R6)

**DECISION:** short polling every 2-3 s (fetch JSON). Rejected: SSE (flaky through tunnels), WebSockets (extra dependency, more failure modes live). "Real time" = visible within a few seconds. Also used to refresh the rotating QR codes of D5.

**Impact.** Sequence diagrams show a polling loop; SRS NFR "update visible within 5 s".

**Status:** VALIDATED by the student — 2026-11-22

## D5 — Attendance mechanism: chain-of-trust check-in (OQ2; R1, R13, R14, R16)

**Question.** How can a student mark attendance "automatically (or as simple as possible)" from a phone, without personal data, while making it hard to mark an absent friend?

**DECISION (student's own design): chain-of-trust check-in, done at the END of the class.**
1. The lecturer opens the check-in session; the lecturer's phone shows a QR code.
2. The lecturer shows it to a first student (or a few), who scans it -> attendance recorded.
3. That student's phone then shows **their own** QR code and can sponsor **up to 3** classmates sitting nearby; each of them can sponsor 3 more, and so on (tree propagation: the whole class in under 1 minute). Sponsoring is optional: the last students simply do nothing more. The lecturer can validate an **unlimited** number of students directly.
4. **All** QR codes (lecturer and students) regenerate **every 10 s**; the server rejects expired codes, so a forwarded photo or screenshot is useless.
5. Scans are phone-to-phone at a few centimetres -> physical presence is required.
6. The app stores **who validated whom** (sponsor tree) -> an accomplice is identifiable too (deterrence).
7. The lecturer sees the live list (and tree) and closes the session.

Identity of each node = the nickname and device token of D6 (no personal data). The 3-sponsor limit and the code expiry are enforced server-side.

**Residual risk (documented honestly).** An accomplice could relay a QR code in real time via a video call. Mitigation: traceability (the relaying sponsor is recorded) + the photo head count (D7) as a global check (number of check-ins vs number of people counted).

**Alternatives considered and rejected.**
- Static QR on the projector: can be forwarded to absent friends.
- Rotating QR on the projector: no per-person accountability (anyone in view, or a remote viewer, can scan).
- Ultrasound code: unreliable on iPhone/laptop speakers, relayable by phone call.
- AirDrop/Bluetooth: not available to web pages on iOS; Apple-only.
- GPS/geofence: location is personal data; unreliable indoors.
- Face recognition: biometric personal data (G1).
- Wi-Fi restriction: incompatible with the public tunnel (D13).
- Photo of raised phones with markers: impractical, unreliable at distance.

**Out of scope.** Late arrivals (check-in happens at the end of class).

**Justification.** F1 "automatically (or as simple as possible)"; G1/QA6 no personal data; the statement's own control "shooting a photo [and] performing an automatic student count" (D7) is kept as the global check.

**Impact.** Use cases: Open check-in session, Check in by scanning, Sponsor a classmate, View live list/tree, Close session. Classes for sessions, rotating signed codes, check-ins with sponsor link. QR generated with the `qrcode` library (tools report). Tests: expiry at 10 s, 4th sponsorship rejected, double check-in rejected, lecturer unlimited, scan after close rejected.

**Status:** VALIDATED by the student — awaiting lecturer confirmation (e-mail sent 2026-11-22) **[ASK]**

## D6 — Student identity without personal data (OQ4; R16, R3)

**Options.** 1. *Self-chosen nickname + random device token.* 2. *Anonymous token only* (sheet unreadable). 3. *Pick a name from the course list* (personal data; violates G1, QA6).

**DECISION: option 1, "Moodle-like" simplicity without accounts.** The student enters a self-chosen nickname **once** (first use); the phone remembers a random token (cookie + localStorage). At every later check-in the student is recognised automatically, with no typing. The UI warns "do not use your real name or ID". No name/ID/e-mail field anywhere. Spreadsheet columns: session date, nickname, check-in time, sponsor nickname (or "lecturer"); per-session summary: check-ins, photo count, difference.

**Justification.** G1 "No need integrate with ... מידע אישי"; QA6 the lecturer removed IDs from the list.

**Impact.** Data model; README scope; tests for first-use and returning-device flows.

**Status:** VALIDATED by the student — 2026-11-22

## D7 — Photo-based head count (OQ3; R2, R16, R25)

**DECISION:** count only, no identification. Candidates: OpenCV YuNet face detector (CPU, small, MIT) and Ultralytics YOLO person detector (heavier, AGPL-3.0). **Final pick = the lower error on the 17 provided photos, measured in the tools report** (manual vs detected count, numbers only). Rejected: MediaPipe (selfie-range), cloud vision API (sends a class photo to a third party, G1). The photo is processed in memory and discarded; only the count is kept. Mismatch: show "checked in N / counted M / difference"; the lecturer decides.

**Impact.** `HeadCounter` behind an interface; tools report table with file names only; tests on non-personal images (D25).

**Status:** VALIDATED by the student — 2026-11-22

## D8 — Online/offline spreadsheet; offline comments (OQ5; R3, R5)

**DECISION:** online = live table in the lecturer page; offline = CSV download (+ XLSX via `openpyxl`). F2 "offline" = asynchronous: comments can be posted at any time, also outside a live session, and read later. Rejected: Google Sheets API sync (OAuth, network), PWA offline queue (extra code). Google Sheets import listed as extension.

**Impact.** SRS defines online/offline explicitly; use cases "Download attendance sheet", "Post comment outside class".

**Status:** VALIDATED by the student — 2026-11-22

## D9 — Polls (F3; R6)

**DECISION:** the lecturer types one question and 2-4 options; one vote per device token; live counts/bars (D4); the lecturer closes the poll. No free text, no quizzes, no timers. Rejected: external poll tools (accounts).

**Status:** VALIDATED by the student — 2026-11-22

## D10 — Video summary F4 (OQ6; R7, R8, R15)

**DECISION:** uploaded video -> local transcription with `faster-whisper` (video never leaves the laptop) -> structured Claude summary (topics, key points, homework/action items, questions raised) to beat the Zoom baseline (R8). No Zoom/Meet integration (R15). Plan B only (D1): pre-computed summary of the same file, labelled. Outputs from the provided video stay local unless checked free of personal data (D21). Rejected: cloud transcription (audio sent out), fully local LLM (slow).

**Impact.** `VideoSummarizer` = `Transcriber` + `LLMClient` (D12); tools report records timing on the provided video.

**Status:** VALIDATED by the student — 2026-11-22

## D11 — Homework review with comparison F5 (OQ6; R9, R10, R16)

**DECISION:** public repo URL -> download archive (no token) -> README + main source files capped (~40-60 KB text) -> Claude review against a short rubric -> comparison with 1-2 other repos of the same assignment, shown anonymised ("Submission B, C"), plus simple deterministic metrics (file/line counts). Generated reviews of other students' work are not committed. Rejected: static analysis only (not an LLM review), embeddings over the whole list (over-design).

**Impact.** Classes `RepoFetcher`, `HomeworkReviewer`, `LLMClient`.

**Status:** VALIDATED by the student — 2026-11-22

## D12 — LLM provider and secrets (OQ6; R11, R17)

**DECISION:** Anthropic (Claude), a current fast/cheap model, name configurable via env var (e.g. `ANTHROPIC_MODEL`, with a default). Key in `.env` as `ANTHROPIC_API_KEY` (git-ignored); `.env.example` committed with placeholders. One small `LLMClient` interface (Claude implementation + fake for tests). Only text is sent (transcript, public repo extracts); never photos or the participant list. Without key: the app runs; F4/F5 use plan B (D1).

**Status:** VALIDATED by the student — 2026-11-22

## D13 — Hosting for the live demo (OQ7; R13, R19)

**DECISION:** app on the laptop + Cloudflare quick tunnel (`cloudflared tunnel --url`, no account, public HTTPS URL). **Plan B:** phone hotspot / LAN URL. **Plan C:** screen recording of a full rehearsal + lecturer page with 2-3 simulated phones. Rejected: ngrok (account, interstitial), free cloud hosts (RAM, cold start, deploy effort).

**Impact.** README "Run the demo"; tools report tests cloudflared from a real phone on mobile data. HTTPS also matters for camera access when scanning (D5).

**Status:** VALIDATED by the student — 2026-11-22

## D14 — Documents format and repo layout (OQ11; R20-R35)

**DECISION:** Markdown in English, Mermaid diagrams (rendered by GitHub), one file per deliverable; the README links every document.

```
README.md                  problem, scope, how to run, tools used, links (TD1)
docs/tools_report.md       TD3
docs/sow.md                TD4
docs/srs.md                TD5
docs/use_cases.md          TD6
docs/design.md             TD7-TD8 components, class + sequence diagrams
docs/test_strategy.md      TD9
docs/results.md            TD12
docs/requirements.md, docs/decisions.md   working files (public, no personal data)
app/  tests/  demo_data/  .env.example  requirements.txt
```

**Status:** VALIDATED by the student — 2026-11-22

## D15 — Tools report scope and evidence (OQ12; R24, R25)

**DECISION:** every tool we suggest is actually run; each entry: purpose, alternatives, exact command/code, input (no personal content), observed result, date, version, verdict. Tools: Flask, qrcode, a browser QR scanning approach, OpenCV YuNet, Ultralytics YOLO, faster-whisper, Anthropic API, cloudflared, openpyxl.

**Status:** VALIDATED by the student — 2026-11-22

## D16 — Deadline (OQ8; R36)

**DECISION:** the student confirmed the real deadline is **26/11/2026**. Plan: deliverables committed with margin before it.

**Status:** VALIDATED by the student — 2026-11-22

## D17 — Demo date and results description (OQ9; R34, R35)

**DECISION:** demo-ready by 25/11. `docs/results.md` written from the full rehearsal (what worked, head-count accuracy, timings, limits), with a section to update after the class demo if allowed. **[ASK]** date of the class demo and whether TD12 must include it.

**Status:** VALIDATED by the student — 2026-11-22

## D18 — Submission channel (OQ10; R23, R37)

**DECISION:** Google Form "Ex2 - Github Submission" (TD2), filled by the student only; the repo must be public when the link is submitted; agents never push. **[ASK]** the student checks Moodle for a separate Ex2 upload.

**Status:** VALIDATED by the student — 2026-11-22

## D19 — Live statement and empty items (OQ13)

**DECISION:** the student re-reads the live Google Doc at Phase 2 and before submitting; new Q&A goes into `docs/requirements.md` and may reopen decisions.

**Status:** VALIDATED by the student — 2026-11-22

## D20 — Individual or team (OQ14)

**DECISION:** individual assignment (one repo, one submitter).

**Status:** VALIDATED by the student — 2026-11-22

## D21 — Personal data in demo, tests and repository (R16)

**DECISION:**
- Never in git (tree or history): participant list, class photos, video, Ex1 repo list, outputs derived from them unless checked clean.
- Demo DB and `demo_data/`: fictitious nicknames; non-personal test images.
- Provided files used locally only; only aggregate numbers reported.
- Live demo photo processed in memory and discarded (D7).
- `.gitignore` covers `.env`, `instance/`, uploads, model files.

**Status:** VALIDATED by the student — 2026-11-22

## D22 — Lecturer access

**DECISION:** single lecturer PIN from an env var, kept in the session cookie. Rejected: no protection (students could close sessions), accounts (personal data, over-design).

**Status:** VALIDATED by the student — 2026-11-22

## D23 — Error-message policy (lesson from Ex1)

**DECISION:** short, actionable, plain-English messages ("This code has expired — ask for a fresh one"); never database IDs, tokens, stack traces, file paths or exception names. Details go to the server log only; Flask debug off in the demo. Each error case listed in the SRS and covered by a test.

**Status:** VALIDATED by the student — 2026-11-22

## D24 — Git practice (lesson from Ex1)

**DECISION:** frequent small commits after each validated document or task, spread over 22-26/11; conventional messages (`docs: add SRS`, `feat: chain-of-trust check-in`); existing global git identity unchanged; **no `Co-Authored-By` trailer** (AI use is disclosed in the README "Tools used" section instead); **agents never push**, the student publishes. Before each commit: check that no personal data or secret is staged.

**Status:** VALIDATED by the student — 2026-11-22

## D25 — Test tooling (R32)

**DECISION:** `pytest` + Flask test client; unit tests per class from `docs/design.md`; `LLMClient` and `Transcriber` replaced by fakes (no network, no key); `HeadCounter` tested on non-personal images with a tolerance (e.g. ±20 %), plus the local-only accuracy measurement on the provided photos (reported, not automated). Time-dependent logic (10 s QR expiry, D5) tested with an injectable clock. Manual end-to-end check with 2-3 phones before the demo.

**Status:** VALIDATED by the student — 2026-11-22

---

## Questions still worth asking the lecturer/TA

1. Is the chain-of-trust check-in acceptable as the attendance mechanism (D5)? (e-mail sent 2026-11-22)
2. Date of the class demo; must the results description include it (D17)?
3. Is there a Moodle upload in addition to the Form (D18)?
4. Optional: is a nickname-based attendance sheet acceptable under "no personal information" (D6), and may anonymised comparisons with other students' repos be shown in class (D11)?
