# Decisions — Ex2 "Web-based Teaching Tool"

Resolutions of the open questions (OQ1-OQ14 in `docs/requirements.md`) and of the technical choices left open by
the statement. Proposed by the ambiguity analysis, **validated by the student on 2026-11-22** (D31: 2026-11-23;
D32, D33, D34 and D35: 2026-11-23).
Requirements are cited as R<n>, statement locators as F/Req/G/TD/QA (see `docs/requirements.md`).

Guiding rule: the **simplest option that fully satisfies the requirements** (KISS, Req2), that can really be
implemented and shown live (G2, Req1), reusing existing code (Note, G3, TD10), with **no personal data** (G1, QA6),
within the days available (from 22/11/2026; internal target: demo-ready by 29/11/2026, submission by 30/11/2026,
see D16-D17). No over-design (lesson from Ex1).

Legend: **[ASK]** = still worth confirming with the lecturer/TA. **SUPERSEDED** = replaced by a later decision; the
old text is kept below for history only and must not be used for design.

## Summary

| D | Topic | Decision | Status |
|---|---|---|---|
| D1 | Demo scope (OQ1) | All 5 features fully implemented and working live (no pre-computed outputs); F1 first and most robust; F4 ~~deferred (D10)~~ implemented for real recordings of any length (D34) | VALIDATED (F4 part: D34) |
| D2 | Tech stack | Python 3.11+ / Flask, server-rendered mobile-first HTML + small vanilla JS | VALIDATED |
| D3 | Storage | SQLite (stdlib `sqlite3`), one local file, git-ignored | VALIDATED |
| D4 | Real time | Short polling (2-3 s; projector 1 s, D31); no websockets | VALIDATED (amended by D31) |
| D5 | Attendance mechanism (OQ2) | ~~Chain-of-trust check-in (root QR, sponsors, sponsor tree, lecturer phone QR)~~ | SUPERSEDED by D30 (22/11) |
| D6 | Student identity (OQ4) | Nickname entered once, remembered by a random device token (cookie only, D31); automatic recognition afterwards; nickname 1-30 chars, not unique (D31) | VALIDATED (amended by D31) |
| D7 | Photo head count (OQ3) | YuNet, whole image, score threshold 0.4 (recall ~94 %, precision ~96 %); no manual correction; automatic consistency alert (asymmetric tolerance); photo discarded after counting; a new photo replaces D (D31) | VALIDATED (amended by D31) |
| D8 | Spreadsheet online/offline; offline comments (OQ5) | Live in-app table + CSV/XLSX download (format: D31); F2 offline = asynchronous | VALIDATED (amended by D31) |
| D9 | Polls (F3) | One question, 2-4 options, one vote per token, live results | VALIDATED |
| D10 | Video summary F4 (OQ6) | No pre-computed summary; to revisit after F1-F3; candidate: live demo on a short 2-3 min clip (faster-whisper + Claude) | ~~DEFERRED~~ CLOSED by D34 (23/11) |
| D11 | Homework review F5 (OQ6) | Public repo URL -> capped text extract -> Claude review + anonymised comparison with 1-2 other repos (source, masking: D31); runs live, no pre-computed fallback | VALIDATED (amended by D31) |
| D12 | LLM provider and secrets | Anthropic (Claude); model from `ANTHROPIC_MODEL`, default `claude-sonnet-5-5` (to confirm by a real call); key in `.env` | VALIDATED |
| D13 | Demo hosting (OQ7) | Laptop + Cloudflare quick tunnel; plan B hotspot/LAN over plain HTTP (works: no in-page camera); plan C recorded run | VALIDATED (IP notes obsolete since D33) |
| D14 | Documents format and layout (OQ11) | Markdown in `docs/`, one file per deliverable, Mermaid, README links all | VALIDATED |
| D15 | Tools report (OQ12) | Every tool we suggest, tested for real with command, input, result, date, version | VALIDATED |
| D16 | Deadline (OQ8) | Extended by the lecturer: submission by 30/11/2026 | VALIDATED |
| D17 | Demo date and results (OQ9) | Demo-ready by 29/11/2026; results from rehearsal, updated after class demo if allowed | VALIDATED [ASK] |
| D18 | Submission channel (OQ10) | Google Form, filled by the student only; check Moodle for an extra upload | VALIDATED [ASK] |
| D19 | Live statement (OQ13) | Re-read the live Google Doc at Phase 2 and before submission | VALIDATED |
| D20 | Individual vs team (OQ14) | Individual work | VALIDATED |
| D21 | Personal data (R16) | Fictitious data in repo/demo; provided files local only, aggregate results only; no client IP read for attendance (D33) | VALIDATED (amended by D33) |
| D22 | Lecturer access | Single lecturer PIN from an env var; no accounts | VALIDATED |
| D23 | Error messages | Plain user messages, no internal identifiers/stack traces; details in server log | VALIDATED |
| D24 | Git practice | Frequent small commits until submission, conventional messages, no `Co-Authored-By` trailer, agents never push | VALIDATED |
| D25 | Test tooling | pytest + Flask test client; ML/LLM mocked; detector tested on non-personal images | VALIDATED |
| D26 | Slot accounting (root 5, sponsor quota) | ~~Scan reserves a slot; confirmation consumes it; expiry frees it~~ | SUPERSEDED by D30 (22/11) |
| D27 | Attendance sessions | One session open at a time (sponsor-limit part SUPERSEDED by D30) | VALIDATED (partly superseded) |
| D28 | Polls: concurrency and voting | One poll open at a time; one vote per device token per poll; no nickname needed | VALIDATED |
| D29 | Comments anonymity and timing (F2) | Anonymous (text + time only, no nickname); live (D4) and after class; max 500 chars (D31) | VALIDATED (amended by D31) |
| D30 | Attendance check-in flow (replaces D5 chain and D26) | ~~Campus-network IP allow-list~~ (removed by D33) + projector QR (10 s, accepted <= 15 s old) + ~~3-digit~~ 4-digit (D33) code (5 s) typed in a 1-min window + one check-in per device per session; D7 photo alert as safety net | VALIDATED (details: D31; point 1 network filter SUPERSEDED by D33) |
| D31 | Design-level choices validated with `design.md` (OI-1-OI-13) | F5 peer list page, nickname rules, cookie-only token, export format, polling 1 s on projector, etc. | VALIDATED (23/11) |
| D32 | Network origin of a check-in (field findings 23/11; amends D30 point 1) | ~~Every network accepted and classified campus / Apple relay / off campus, shown live and in the export~~ | SUPERSEDED by D33 (23/11) |
| D33 | Remove the IP / network part entirely (supersedes D32 and point 1 of D30); projected code 4 digits (amends D30 point 3) | No client IP read for attendance, no allow-list, no relay list, no origin label; anti-cheat = rotating QR (10 s / 15 s) + projected **4-digit** code (0000-9999, 5 s, P1) + the unchanged D30 rules; D7 photo alert is the room-level check. Code brute force by rescanning: ~500 -> ~5,000 expected tries, residual risk recorded | VALIDATED (23/11) |
| D34 | Video summary F4 for real recordings (closes D10) | PIN page, upload up to 2 GB (configurable, this route only) streamed to a temp file; ffmpeg -> mono 16 kHz audio; faster-whisper `small` (CPU int8, VAD, language auto unless `WHISPER_LANGUAGE`) in **one background thread, one job at a time**; Claude structured summary (map-reduce above a safe size, transcript treated as untrusted); status page polled; video and audio deleted right after transcription (also on failure), transcript never stored, only the summary text + timestamps kept in SQLite; demo on a local-only 4-min Hebrew clip | VALIDATED (23/11) |
| D35 | Display time zone | User-visible times in Israel local time (Asia/Jerusalem, DST); storage stays UTC | VALIDATED (23/11) |

"VALIDATED" = "VALIDATED by the student — 2026-11-22" unless stated otherwise. "DEFERRED" = "DEFERRED by the
student — 2026-11-22".

---

## D1 — Demo scope (OQ1; R4, R5-R10, R12, R17, R19, R33)

**Question.** Must all five features be implemented in the demo app, or only designed?

**Options.** 1. *All five fully implemented.* 2. *F1 only, F2-F5 design only* (weak demo, Req1). 3. *F1 complete, F2-F3 simple, F4-F5 thin wrappers with pre-computed fallback* (initial proposal).

**DECISION: option 1 (changed by the student).**
- All five features are fully designed **and** fully implemented (real working paths, not thin wrappers).
- F1 (R1-R3: check-in flow D30 (formerly the D5 chain, superseded 22/11), photo head count D7, live table + CSV/XLSX D8, check-ins vs counted comparison) is built **first** and is the most robust part.
- F2 (D8), F3 (D9), F4 (D10), F5 (D11) are real implementations.
- **No pre-computed outputs** for F4/F5: every feature must work live on demo day (student's principle). Network/hosting failures are covered by the hosting plans of D13, not by canned results.
- F4 is **deferred** (D10): revisited after F1-F3 are done. **Revisited by D34 (23/11):** F4 is implemented for real recordings of any length (background job).
- No extra features (no accounts, no analytics, no notifications, no PWA offline mode).

**Justification.** F1 "is the main (most important) feature"; Req1 "should work in this class"; G2 "only design what can be implemented"; reuse of existing libraries (Note) keeps the full scope feasible.

**Impact.** README scope (R22) and SoW schedule list all five; task order F1 > F3 > F2 > F5 > F4 (F4 after its D10 revisit); test strategy weights F1; demo script (R19) relies on the D13 hosting plans B/C.

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

**DECISION:** short polling every 2-3 s (fetch JSON). Rejected: SSE (flaky through tunnels), WebSockets (extra dependency, more failure modes live). "Real time" = visible within a few seconds. Also used to refresh the projector QR (10 s) and the projected code (5 s; 4 digits since D33) of D30 (originally: the rotating QR codes of D5, superseded).

**Impact.** Sequence diagrams show a polling loop; SRS NFR "update visible within 5 s".

**Amended by D31 (OI-8, 23/11):** the projector page polls every 1 s (local, one client); other pages stay at 2-3 s.

**Status:** VALIDATED by the student — 2026-11-22

## D5 — Attendance mechanism: chain-of-trust check-in (OQ2; R1, R13, R14, R16)

> **SUPERSEDED by D30 (22/11).** The whole chain of trust (root QR limited to 5 scans, student sponsor QRs and
> limits, sponsor tree, lecturer personal QR, "no typed code") is abandoned. Reason: it is no more secure than a
> projector QR (a present student can screenshot their own rotating QR and send it on WhatsApp within the 15 s
> window, and any browser-only scheme can be defeated by a live video call), while being far more complex.
> Still valid and carried into D30: native camera scanning (no in-page scanner), the 10 s regeneration / 15 s
> acceptance rule, nickname once (D6), one check-in per device token per session, D7 as global check.
> The text below is kept for history only.

**Question.** How can a student mark attendance "automatically (or as simple as possible)" from a phone, without personal data, while making it hard to mark an absent friend?

**DECISION (student's own design): chain-of-trust check-in, done at the END of the class.**
1. **Root QR on the projector.** The lecturer clicks "Attendance": the projector shows a **root QR** that regenerates every 10 s. It accepts only the **first 5 scans** (5 roots, ideally spread across the room), then closes automatically. The lecturer does not move from the desk.
2. **Native camera, no in-page scanner.** Students scan with their phone's **native camera app**. The QR encodes a URL; tapping the camera's link opens the site in the default browser. There is no in-page scanner, no `getUserMedia`, and no camera permission prompt in the browser.
3. **Timing rule.** Every QR (root, student, lecturer) regenerates every **10 s**. The server accepts a QR if it is **<= 15 s old when the request arrives at the server** (checked before the page is sent), then issues a **2-minute claim bound to that browser** (D6 token). Slow page loading or slow nickname typing therefore does not matter: the student taps **"Confirm my presence"** within 2 minutes.
4. **Identity.** First visit: the student types a nickname once (remembered by the browser via a random token, D6). Later visits: recognised automatically, no typing.
5. **Sponsoring.** After confirming, the student's page shows **their own rotating QR** (same 10 s / 15 s rule) that nearby classmates scan with their native camera. Each student can sponsor **up to 3 classmates by default**; the lecturer can configure this limit **per session (1-5)**. Sponsoring is optional: the last students simply do nothing more.
6. **Sponsor tree.** The app stores **who validated whom** (including "root via projector" and "lecturer") and shows the tree to the lecturer, together with the live list; an accomplice is therefore identifiable too (deterrence). The lecturer closes the session.
7. **Fallback when a student cannot scan.** The lecturer shows a **personal lecturer QR on their own phone** (unlimited sponsorships, same 10 s / 15 s rule) up close to that student.
8. **Parallelism and time.** 5 roots x 3 sponsors -> 5 + 15 + 45 = **~65 students in 3 waves**. **Target: whole class checked in in < 2 min.** No class test is possible before the demo: the duration is **measured live during the class demo** (and reported in `docs/results.md`, TD12); beforehand the flow is rehearsed at home with several browser tabs/phones.
9. **Plan B without HTTPS** (hotspot/LAN, D13) works, since no in-page camera access is needed. The QR codes must encode the URL actually reachable by the phones (configurable public base URL).

Identity of each node = the nickname and device token of D6 (no personal data). The root limit (5), the sponsoring limit (1-5, default 3), the 15 s acceptance window, the 2-minute claim and the "one check-in per token per session" rule are all enforced server-side.

**Lecturer feedback (received 2026-11-22).** The lecturer found the idea interesting but raised a concern: the process takes time and attention and could disrupt class management. The lecturer leaves the choice to the student. **The student keeps the chain of trust** (precision and accountability), with these mitigations:
- **Timing:** done at the end of class, so it does not interrupt teaching.
- **Lecturer effort:** one click and a projected QR; the lecturer stays at the desk; the root QR closes by itself after 5 scans.
- **Parallel start:** 5 roots spread across the room, so propagation runs in parallel (3 waves for ~65 students).
- **Low friction:** native camera (no permission prompt, no in-page scanner), nickname typed only once, a generous 2-minute claim to confirm.
- **Measured, not assumed:** the real duration (and number of failed scans) is measured during the live class demo and reported in `docs/results.md` (TD12).

**Explicitly rejected: a short typed code under the QR** (suggested as a scanning fallback in the tools report, 2.4). A typed code can be forwarded by message to an absent friend within the validity window, which defeats the physical-presence guarantee. The lecturer-phone QR fallback (step 7) is used instead.

**Residual risk (documented honestly).** An accomplice could relay a QR code in real time via a video call (the root QR on the projector is also visible to anyone in the room during its first 5 scans). Mitigation: traceability (the relaying sponsor, or the root slot used, is recorded in the tree) + the automatic consistency alert of the photo head count (D7) as a global check (number of check-ins vs number of faces detected).

**Alternatives considered and rejected.**
- Static QR on the projector: can be forwarded to absent friends.
- Rotating projector QR for the whole class: no per-person accountability (anyone in view, or a remote viewer, can scan); kept only as a **root** limited to the first 5 scans.
- Lecturer walking around with a phone to start the branches: disrupts the lecturer and takes longer (replaced by the projector root QR).
- In-page QR scanner (jsQR + `getUserMedia`): requires HTTPS and a browser camera permission prompt, extra code and failure modes; **rejected in favour of the phone's native camera**.
- Fixed "open the app" QR (non-rotating entry point): **rejected by the student** (forwardable, adds a step).
- 5 sponsors per student by default: **rejected in favour of 3, configurable per session (1-5)**.
- Short typed code under each QR: forwardable by message (see above).
- Ultrasound code: unreliable on iPhone/laptop speakers, relayable by phone call.
- AirDrop/Bluetooth: not available to web pages on iOS; Apple-only.
- GPS/geofence: location is personal data; unreliable indoors.
- Face recognition: biometric personal data (G1).
- Wi-Fi restriction: incompatible with the public tunnel (D13).
- Photo of raised phones with markers: impractical, unreliable at distance.

**Out of scope.** Late arrivals (check-in happens at the end of class).

**Justification.** F1 "automatically (or as simple as possible)"; G1/QA6 no personal data; the statement's own control "shooting a photo [and] performing an automatic student count" (D7) is kept as the global check.

**Impact.** Use cases: Open check-in session (projector root QR), Configure sponsoring limit, Check in by scanning (native camera -> claim -> confirm), Sponsor a classmate, Check in via the lecturer's phone QR (fallback), View live list/tree, Close session. Classes for sessions, rotating signed codes (issue time, kind: root/student/lecturer), time-limited claims bound to a device token, check-ins with sponsor link. QR images generated server-side with the `qrcode` library and refreshed by polling (D4); **no QR-decoding library in the app**. No typed-code input anywhere in the UI. Tests (injectable clock, D25): code accepted at 15 s and rejected just after; claim accepted within 2 min and rejected after; 6th root scan rejected (root closes after 5); sponsoring limit enforced for the default 3 and for configured values 1 and 5 (out-of-range values 0 and 6 rejected); lecturer QR unlimited; double check-in rejected; scan or confirm after close rejected. Results: live timing measurement during the class demo (target < 2 min).

**Status:** ~~VALIDATED by the student — 2026-11-22~~ **SUPERSEDED by D30 (22/11)**

## D6 — Student identity without personal data (OQ4; R16, R3)

**Options.** 1. *Self-chosen nickname + random device token.* 2. *Anonymous token only* (sheet unreadable). 3. *Pick a name from the course list* (personal data; violates G1, QA6).

**DECISION: option 1, "Moodle-like" simplicity without accounts.** The student enters a self-chosen nickname **once** (first use); the phone remembers a random token (cookie + localStorage). At every later check-in the student is recognised automatically, with no typing of the nickname (the projected code of D30, 4 digits since D33, is still typed). The UI warns "do not use your real name or ID". No name/ID/e-mail field anywhere. Spreadsheet columns: session date, nickname, check-in time (the former "sponsor" column is dropped: SUPERSEDED by D30); per-session summary: check-ins, faces detected, consistency status (D7).

**Justification.** G1 "No need integrate with ... מידע אישי"; QA6 the lecturer removed IDs from the list.

**Impact.** Data model; README scope; tests for first-use and returning-device flows.

**Amended by D31 (23/11):** the device token is kept in a server-set cookie only, no localStorage copy (OI-4); nickname 1-30 characters after trimming, not unique (OI-2); stored at the first successful check-in.

**Status:** VALIDATED by the student — 2026-11-22 (spreadsheet "sponsor" column superseded by D30, 22/11)

## D7 — Photo-based head count (OQ3; R2, R16, R25)

**DECISION: OpenCV YuNet face detector on the whole image, score threshold 0.4, fully automatic.**
- **Detector:** YuNet (`face_detection_yunet_2023mar.onnx`, 0.23 MB, MIT model, CPU, < 0.1 s per photo). Count only, no identification.
- **Measured accuracy** (tools report 2.5, 4 provided photos re-counted carefully box by box, 173 people): recall ~94 % (163/173), precision ~96 % (6 false positives). All misses are faces **not visible** (head down, asleep, hand over face, hidden behind others, back turned). Practical advice shown to the lecturer: **take the photo when the students look up**.
- **No tiling:** tested and rejected — only +1 real person, about twice the false positives (mostly clasped hands), 5-15x slower.
- **No manual correction by the lecturer** (rejected by the student: the app must stay automatic).
- **Automatic consistency alert** instead. With N = number of check-ins (D30) and D = number of detected faces:
  - "consistent" if `N - max(7, ceil(0.15 * N)) <= D <= N + max(4, ceil(0.10 * N))`, otherwise "anomaly".
  - Asymmetric because the detector undercounts more than it overcounts (measured error -6 to +3). Example: N = 45 -> consistent for D from 38 to 50. 0 false alerts on the 4 refined photos.
  - ~~On "anomaly", the sponsor tree (D5) helps the lecturer investigate (which branches look suspicious).~~ (SUPERSEDED by D30: no sponsor tree.) On "anomaly", the lecturer simply knows the check-in count is not credible for this session.
- **Documented limit:** fraud becomes visible only beyond about 7 check-ins of absent people for N ≈ 45; fewer stay inside the measurement noise. Stated in the SRS, design and results.
- **Two-photo mode** (front rows / back rows): not testable with the provided photos (no real pairs; only a simulation); **not adopted for now**.
- **Rejected:** Ultralytics YOLO (worse counts, AGPL-3.0, PyTorch), InsightFace SCRFD (non-commercial model licence), MediaPipe (selfie-range), cloud vision API (sends a class photo to a third party, G1).
- **Privacy:** the photo is processed in memory and discarded; only the count is kept (D21).

**Impact.** `HeadCounter` behind an interface (YuNet implementation, threshold configurable, default 0.4); a separate `ConsistencyCheck` (pure function of N and D) shown as "checked in N / detected D / consistent|anomaly"; no "edit count" use case. Tests: alert rule at its boundaries (e.g. N = 45: D = 37/38/50/51), small-N cases where the `max(7, ...)`/`max(4, ...)` floors apply; detector on non-personal images (D25). Tools report table with file names only.

**Amended by D31 (OI-5, 23/11):** a new photo for the same session replaces D (re-shooting is not a manual correction).

**Status:** VALIDATED by the student — 2026-11-22 (unchanged by D30, which keeps it as the safety net)

## D8 — Online/offline spreadsheet; offline comments (OQ5; R3, R5)

**DECISION:** online = live table in the lecturer page; offline = CSV download (+ XLSX via `openpyxl`). F2 "offline" = asynchronous: comments can be posted at any time, also outside a live session, and read later. Rejected: Google Sheets API sync (OAuth, network), PWA offline queue (extra code). Google Sheets import listed as extension.

**Impact.** SRS defines online/offline explicitly; use cases "Download attendance sheet", "Post comment outside class".

**Amended by D31 (OI-6, 23/11):** one export covers all sessions; XLSX with two sheets "Check-ins" and "Summary"; CSV as two files `checkins.csv` and `summary.csv`.

**Status:** VALIDATED by the student — 2026-11-22

## D9 — Polls (F3; R6)

**DECISION:** the lecturer types one question and 2-4 options; one vote per device token; live counts/bars (D4); the lecturer closes the poll. No free text, no quizzes, no timers. Rejected: external poll tools (accounts).

**Status:** VALIDATED by the student — 2026-11-22

## D10 — Video summary F4 (OQ6; R7, R8, R15)

**Current direction (not final):** uploaded video -> local transcription with `faster-whisper` (video never leaves the laptop) -> structured Claude summary (topics, key points, homework/action items, questions raised) to beat the Zoom baseline (R8). No Zoom/Meet integration (R15). Rejected: cloud transcription (audio sent out), fully local LLM (slow).

**No pre-computed summary.** The student wants F4 to work live on demo day; a canned output is not acceptable (D1).

**Deferred.** The decision is to be revisited after F1-F3 are done. **Candidate:** a live demo on a short 2-3 min clip, using faster-whisper `base` (speed) or `small` (quality); measured in the tools report (2.6): real-time factor 0.06 (`base`) and 0.17 (`small`) on CPU, i.e. roughly 10-30 s of transcription for a 2-3 min clip, plus one Claude call. Outputs from the provided video stay local unless checked free of personal data (D21).

**Impact.** Design keeps `VideoSummarizer` = `Transcriber` + `LLMClient` (D12) so F4 can be added without redesign; F4 is last in the task order (D1).

**Status:** DEFERRED by the student — to revisit after F1-F3; candidate: live demo on a short 2-3 min clip (faster-whisper base/small measured in tools report) — 2026-11-22.
**CLOSED by D34 (23/11):** F4 is implemented for real class recordings of any length (background job), not only a
short clip; the direction above (local faster-whisper + Claude, no pre-computed summary, no Zoom/Meet integration) is
kept. The "short 2-3 min clip" candidate and the `base` model default are replaced by D34.

## D11 — Homework review with comparison F5 (OQ6; R9, R10, R16)

**DECISION:** public repo URL -> download archive (no token) -> README + main source files capped (~40-60 KB text) -> Claude review against a short rubric -> comparison with 1-2 other repos of the same assignment, shown anonymised ("Submission B, C"), plus simple deterministic metrics (file/line counts). **Runs live; no pre-computed fallback** (same principle as D10: it must work on demo day). If the API or network fails, the user sees a plain error message (D23). Generated reviews of other students' work are not committed. Rejected: static analysis only (not an LLM review), embeddings over the whole list (over-design).

**Impact.** Classes `RepoFetcher`, `HomeworkReviewer`, `LLMClient`.

**Amended by D31 (OI-1, OI-9, OI-10, OI-12, 23/11):** the comparison repos come from a list pasted by the lecturer on the PIN-protected page `/lecturer/peers` (local SQLite); owner and repository names of peers are masked and reviews are never stored; the review page stays open without PIN for the demo; if no peer can be fetched, the review is shown with a sentence saying so.

**Status:** VALIDATED by the student — 2026-11-22

## D12 — LLM provider and secrets (OQ6; R11, R17)

**DECISION:** Anthropic (Claude). Model name read from the env var `ANTHROPIC_MODEL`, with a default set to a current Claude model available on the account. The tools report used `claude-sonnet-4-5`, which reaches end-of-life on **30/11/2026**; the default is therefore a newer model, **`claude-sonnet-5-5`** (listed by the account's `models.list`), **to be confirmed by a real call during coding**. Key in `.env` as `ANTHROPIC_API_KEY` (git-ignored); `.env.example` committed with placeholders. One small `LLMClient` interface (Claude implementation + fake for tests). Only text is sent (transcript, public repo extracts); never photos or the participant list. Without a key: the app runs (F1-F3 unaffected); F4/F5 show a plain "LLM service not configured/unavailable" message (D23), no pre-computed output.

**Status:** VALIDATED by the student — 2026-11-22

## D13 — Hosting for the live demo (OQ7; R13, R19)

**DECISION:** app on the laptop + Cloudflare quick tunnel (`cloudflared tunnel --url`, no account, public HTTPS URL). **Plan B:** phone hotspot / LAN URL over plain HTTP; the check-in still works because students scan with the phone's native camera and no in-page camera access is needed (D30); the QR codes encode the configured base URL of the active plan. **Plan C:** screen recording of a full rehearsal + lecturer page with 2-3 simulated phones. Rejected: ngrok (account, interstitial), free cloud hosts (RAM, cold start, deploy effort).

~~**Note added with D30 (22/11).** With the campus-network filter of D30, plan A reads the client IP from the `CF-Connecting-IP` header (trusted only on requests arriving from the local tunnel); in plan B the client IP is the direct socket address, so the allow-list must also contain the LAN/hotspot range used (e.g. a private `/24`).~~ **SUPERSEDED by D33 (23/11):** no client IP is read and there is no allow-list.

**Field note added with D32 (23/11).** On the campus Wi-Fi, a phone could not reach the laptop
on its LAN address (client isolation, same subnet, laptop firewall off): plan B **on the campus Wi-Fi** is not
usable. Plan B on a phone hotspot was not re-tested (and is limited to a few clients, see D30 rejections). Plan A
(tunnel) is the plan for the class demo.

**Note added with D33 (23/11).** The app no longer reads any client IP: the `CF-Connecting-IP` note above and the
"allow-list for each plan" no longer apply. Switching between plans A and B only changes the base URL encoded in
the QR codes. The field note on client isolation (plan B unusable on the campus Wi-Fi) still holds.

**Impact.** README "Run the demo" (including how to set the base URL encoded in the QR codes for plans A and B, and ~~the allow-list for each plan~~ (removed by D33)); tools report tests cloudflared from a real phone on mobile data (~~now expected to be refused by the D30 filter~~ superseded by D33: every network works) and on the campus Wi-Fi.

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

**DECISION:** every tool we suggest is actually run; each entry: purpose, alternatives, exact command/code, input (no personal content), observed result, date, version, verdict. Tools: Flask, qrcode, QR scanning with the phone's native camera app (adopted in D5, kept in D30; the in-page scanner approach tested earlier is documented as rejected), OpenCV YuNet, Ultralytics YOLO, faster-whisper, Anthropic API, cloudflared, openpyxl. With D30: also the client-IP check behind cloudflared (`CF-Connecting-IP` value seen from a phone on campus Wi-Fi vs on 4G/5G) and stdlib `ipaddress` for CIDR matching (*since D33 these two are field evidence for the decision to drop the network check, no longer tools used by the app*).

**Status:** VALIDATED by the student — 2026-11-22

## D16 — Deadline (OQ8; R36)

**DECISION:** the lecturer **extended the deadline** (replacing the date written in the statement, QA3). Internal schedule: **demo-ready by 29/11/2026, submission by 30/11/2026**.

**Status:** VALIDATED by the student — 2026-11-22

## D17 — Demo date and results description (OQ9; R34, R35)

**DECISION:** demo-ready by 29/11/2026. `docs/results.md` written from the full rehearsal (what worked, head-count accuracy and consistency alert, check-in rehearsal with several tabs/phones (D30; formerly the D5 chain), timings, limits), with a section to update after the class demo, where the whole-class check-in duration is measured live, if allowed. **[ASK]** date of the class demo and whether TD12 must include it.

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
- ~~Client IP addresses are used only for the D30 accept/refuse check and never stored with attendance records; the campus allow-list holds network ranges only (no individual addresses). With D32 (23/11) a check-in stores only its network origin label (`campus` / `apple_relay` / `off_campus`), never the address.~~ **Amended by D33 (23/11):** no client IP address is read for attendance any more (no allow-list, no `CF-Connecting-IP`, no origin label). The werkzeug access log stays off, so the app neither stores nor logs client addresses.
- `.gitignore` covers `.env`, `instance/`, uploads, and model files (the Apple relay file line of D32 was removed with D33, together with the local file).
- **Added by D34 (23/11):** an uploaded recording and its extracted audio live only in temporary files outside the repository and are deleted right after transcription (also on failure); the transcript is never stored; only the summary text, status and timestamps are kept; the original file name is not stored. The demo lecture clip stays local only in `docs/supplementary/`.

**Status:** VALIDATED by the student — 2026-11-22

## D22 — Lecturer access

**DECISION:** single lecturer PIN from an env var, kept in the session cookie. Rejected: no protection (students could close sessions), accounts (personal data, over-design). ~~The PIN also protects editing the D30 campus allow-list.~~ (The allow-list is removed by D33.)

**Status:** VALIDATED by the student — 2026-11-22

## D23 — Error-message policy (lesson from Ex1)

**DECISION:** short, actionable, plain-English messages ("This code has expired — ask for a fresh one"); never database IDs, tokens, stack traces, file paths or exception names. Details go to the server log only; Flask debug off in the demo. Each error case listed in the SRS and covered by a test.

**Status:** VALIDATED by the student — 2026-11-22

## D24 — Git practice (lesson from Ex1)

**DECISION:** frequent small commits after each validated document or task, spread from 22/11 until submission; conventional messages (`docs: add SRS`, `feat: attendance check-in`); existing global git identity unchanged; **no `Co-Authored-By` trailer** (AI use is disclosed in the README "Tools used" section instead); **agents never push**, the student publishes. Before each commit: check that no personal data or secret is staged.

**Status:** VALIDATED by the student — 2026-11-22

## D25 — Test tooling (R32)

**DECISION:** `pytest` + Flask test client; unit tests per class from `docs/design.md`; `LLMClient` and `Transcriber` replaced by fakes (no network, no key); `HeadCounter` tested on non-personal images with a tolerance (e.g. ±20 %), plus the local-only accuracy measurement on the provided photos (reported, not automated); the D7 consistency rule tested exhaustively at its boundaries (pure function). Time-dependent logic of D30 (10 s QR regeneration, 15 s acceptance window checked on request arrival, 5 s code rotation, 1-minute check-in window) tested with an injectable clock; ~~the client IP is injectable too (allow-list tests)~~ (no client IP since D33). (Originally: D5's 2-minute claim, superseded.) Manual end-to-end rehearsal with several browser tabs and 2-3 phones before the demo.
**Added by D34 (23/11):** F4 is tested with `FakeTranscriber`, a fake audio extractor, `FakeLLMClient` and an inline
job runner (no ffmpeg, Whisper model or network); one optional integration test is skipped unless `ffmpeg` and the
cached model are present; tests never trigger a model download.

**Status:** VALIDATED by the student — 2026-11-22

## D26 — Slot accounting for root QR and sponsor quota (R1; refines D5)

> **SUPERSEDED by D30 (22/11).** There are no root slots, sponsors or claims any more. Kept for history only.

**Question.** When is a limited slot (the 5 root slots of the projector QR, a student's sponsor quota of 3 by default, configurable 1-5) used up: at scan time or at confirmation?

**Options.** 1. *Consume at scan.* 2. *Consume only at confirmation.* 3. *Reserve at scan, consume at confirmation, free on expiry.*

**DECISION: option 3.** A valid scan **reserves** a slot (the 2-minute claim of D5); confirmation within the claim **consumes** it; if the claim expires unconfirmed, the slot is **freed automatically**. The attendance table and the CSV/XLSX export show **only confirmed check-ins and confirmed sponsorships**.

**Rejected.** Option 1: an abandoned scan wastes a slot, and the sponsor count in the table would differ from the confirmed sponsorships. Option 2: more than 5 roots (or more sponsored classmates than the quota) could claim within the 15 s window.

**Impact.** Slot count = confirmed + live (unexpired) claims; expiry checked lazily with the injectable clock (D25). Tests: 6th root claim rejected while 5 claims are live; slot available again after a claim expires; sponsor quota counted the same way; only confirmed rows in table/export.

**Status:** ~~VALIDATED by the student — 2026-11-22~~ **SUPERSEDED by D30 (22/11)**

## D27 — Attendance sessions: one at a time, fixed sponsor limit (R1; refines D5)

**Question.** Can several attendance sessions be open at once, and can the sponsor limit change during a session?

**Options.** 1. *One open session at a time, limit fixed at opening.* 2. *Several sessions / limit editable during the session* (extra states and edge cases, KISS).

**DECISION: option 1.** Only one attendance session is open at a time. ~~The sponsor limit (1-5, default 3) is chosen when the session is opened and cannot be changed during the session.~~ (SUPERSEDED by D30, 22/11: no sponsor limit any more; opening a session is a single click.)

**Impact.** Opening a second session while one is open is rejected with a plain message (D23). Tests for this rule. (The "sponsor limit fixed / out of range" tests are dropped with D30.)

**Status:** VALIDATED by the student — 2026-11-22 (sponsor-limit part SUPERSEDED by D30, 22/11)

## D28 — Polls: one at a time, voting rule (F3, R6; refines D9)

**Question.** How many polls may be open at once, and what identifies a voter?

**Options.** 1. *One open poll; one vote per device token per poll; no nickname.* 2. *Several open polls / nickname required to vote* (more UI, needless identity).

**DECISION: option 1.** Only one poll is open at a time; one vote per device token (D6) per poll; voting does not require a nickname.

**Impact.** Student poll page shows the single open poll; second vote from the same token rejected (D23); opening a second poll while one is open rejected. Tests for each rule.

**Status:** VALIDATED by the student — 2026-11-22

## D29 — Comments anonymity and timing (F2, R5; refines D8)

**Question.** Are comments/suggestions linked to a nickname, and when can they be posted?

**Options.** 1. *Anonymous: text and time only.* 2. *Signed with the nickname* (discourages honest feedback, more identity data).

**DECISION: option 1.** Comments are anonymous: the lecturer sees the text and the time, never a nickname. Usable **during class** (real time, visible within a few seconds, D4) and **after class** (asynchronous, D8).

**Impact.** Comment data model has no nickname/token column shown to the lecturer; lecturer page polls for new comments (D4). Tests: comment appears without nickname; posting outside a live session works.

**Amended by D31 (OI-11, 23/11):** a comment has at most 500 characters (message "Please keep your comment under 500 characters.").

**Status:** VALIDATED by the student — 2026-11-22

## D30 — Attendance check-in flow (replaces D5 chain and D26) (OQ2; R1, R13, R14, R16)

> **Partly SUPERSEDED by D33 (23/11).** Point 1 (campus network filter), its technical/privacy notes, the
> allow-list editor, the `CF-Connecting-IP` handling, the off-campus error, the IP tests and the D32 amendment below
> are **removed**: no client IP is read for attendance any more. Point 3 is **amended**: the projected code has
> **4 digits** (0000-9999) instead of 3, still new every 5 s with the previous one accepted (P1). Points 2, 4, 5 and
> P1-P3 are unchanged, as are the D31 details that do not concern the network (new scan = new window with 0
> attempts, empty nickname not counted, QR creation time = start of its 10 s slice). The text below is kept as
> history; its argument "combined with the campus-network filter the relay must come from someone on campus" no
> longer holds (see D33, consequences).

**Question.** How does a student check in from a phone, as simply as possible, without personal data, while making it hard to check in an absent friend?

**Why the chain of trust (D5, D26) was dropped.** It is no more secure than a projector QR: a present student can screenshot their own rotating personal QR and send it on WhatsApp within the 15 s window, and any browser-only scheme can be defeated by a live video call. It was also far more complex (root slots, sponsor quotas, claims, tree, lecturer QR).

**DECISION (student's design).** Session open/close by the lecturer (PIN, D22; one session at a time, D27) is unchanged.
1. **Campus network filter.** A check-in request is accepted only if the client IP is in an **allow-list edited by the lecturer in the app** (IPv4 and IPv6 ranges in CIDR notation). Students on 4G/5G are refused with a plain message (D23) that asked them to join the university Wi-Fi (message replaced on 23/11, see D32) (*amended by D32: now accepted and flagged "off campus network"*). The university has no VPN (confirmed by the student). The student measures the campus public IP(s) on site on 23/11; until then the list holds placeholders, and for home testing the student's own IP is used.
   - *Technical note:* the app runs behind a Cloudflare quick tunnel (D13), so the real client IP is read from the `CF-Connecting-IP` header, **trusted only when the request comes through the tunnel (socket peer is localhost)**; otherwise the socket address is used. CIDR matching with stdlib `ipaddress`.
   - *Privacy:* the client IP is used only for the accept/refuse check and **never stored** with attendance records (D21).
   - *Honest limit:* the filter proves "on the campus network", not "in this room".
2. **Projector QR.** The projector shows a QR (a URL, scanned with the phone's **native camera**, no in-page scanner), **regenerated every 10 s**, HMAC-signed with its creation time. The request must reach the server **at most 15 s after the QR's creation** (covers slow Wi-Fi). Once accepted, the student gets a **1-minute window** bound to that browser's device token (D6) to finish the check-in.
3. **Short code.** Under the QR, the projector shows a **3-digit numeric code regenerated every 5 s** (*4 digits since D33*). On the check-in page, before confirming, the student types their nickname (first time only, D6) and then this code (numeric keypad), and taps "Confirm" (order clarified by the student on 23/11). A screenshot relayed by WhatsApp is useless because the code changes before a remote friend can type it.
4. **One device = one check-in per session** (device token, D6).
5. **Safety net: photo head count (D7), unchanged.** The lecturer takes a class photo; the app compares the face count with the number of check-ins and flags "anomaly". This catches non-attendees helped by a live relay (e.g. video call), on campus or (since D32) off campus, where the off-campus marker also shows them.

All rules are enforced server-side. The QR and the code are refreshed on the projector page by polling (D4).

**Additional rules (validated by the student on 22/11).**
- **P1 — Code tolerance (VALIDATED 22/11).** The server accepts the code currently displayed **or the immediately previous one** (~10 s of slack for slow typing / slow Wi-Fi).
- **P2 — Attempt limit (VALIDATED 22/11).** At most **5 code attempts per 1-minute window** (3 digits = 1000 combinations; prevents guessing). (*D33: 4 digits = 10,000 combinations; the limit is per window and a new scan resets it, see the D33 residual risk.*)
- **P3 — Student whose camera cannot scan the QR (VALIDATED 22/11).** No in-app fallback; the lecturer records them manually after class in the exported spreadsheet (D8).

**Alternatives considered and rejected.** The **chain of trust** (D5/D26: no more secure than a projector QR, far more complex, see above); a **local Wi-Fi bubble with a travel router** (iPhone/Android hotspots are limited to ~5-10 clients and iOS 18+ hotspots block IPv4 between clients; a router must be bought, and 60 clients cannot be verified before class; the range leaks into the corridor); a **random seat + printed desk QR** (a static QR can be photographed; 60 stickers per room); **server-assigned mutual pairs** (finding an anonymous partner among 60 is harder than the chain); **camera gesture liveness** (films students: personal data, G1). The D5 list of earlier rejections (GPS, face recognition, ultrasound, AirDrop/Bluetooth, in-page scanner, static QR) still applies. D5's rejection of a typed code is reversed here: a 5 s code alone would be relayable, but combined with the campus-network filter the relay must come from someone on campus, and the photo alert covers that case. (*Amended by D32, 23/11:* the network check now only labels the check-in, so a relayed code can be used off campus; such a check-in is marked "off campus network" for the lecturer, and D7 still flags an inflated N.)

**Justification.** F1 "automatically (or as simple as possible)"; G1/QA6 no personal data (no IP stored, no camera use by the app); G2 only what can be implemented; the statement's own control "shooting a photo [and] performing an automatic student count" (R2, D7) stays the global check.

**Impact.**
- *Design:* classes for the session, a signed rotating QR token (creation time), a rotating short code (5 s), a check-in window bound to a device token (1 min), a `NetworkPolicy`/allow-list (CIDR, IPv4+IPv6, client-IP resolution behind the tunnel), check-ins (session, nickname, time). No sponsor, slot, claim or tree classes. QR images generated server-side (`qrcode`); no QR-decoding library in the app.
- *Use cases:* Open/close session; Show projector QR + code; Check in (scan -> [nickname, first time only] -> type code -> confirm); Edit campus allow-list (lecturer); View live list; Take photo / consistency alert; Download sheet.
- *UI:* student check-in page has a nickname field on first use only, then a numeric code field (`inputmode="numeric"`), then a "Confirm" button; lecturer page has an allow-list editor.
- *Errors (D23, wording indicative):* off-campus IP -> "Check-in only works on the university Wi-Fi. Please connect to it and scan again." (message replaced on 23/11, see D32); QR older than 15 s / bad signature -> "This QR code has expired. Scan a fresh one."; window over 1 min -> "Your check-in time ran out. Scan the QR code again."; wrong code -> "Wrong code. Type the code shown under the QR now."; (P2) too many attempts -> "Too many tries. Scan the QR code again."; already checked in, session closed, no open session: unchanged.
- *Tests (injectable clock and client IP, D25):* IPv4 and IPv6 inside/outside the allow-list; `CF-Connecting-IP` honoured from localhost and ignored from any other peer (spoofing); QR accepted at 15 s, rejected just after; window accepted at 1 min, rejected just after; current code accepted, stale code rejected (P1: previous code accepted, the one before rejected); (P2) 6th attempt rejected; double check-in from the same token rejected; check-in after close rejected; no IP column in the stored records/export.
- *Hosting (D13):* allow-list must include the LAN range for plan B.
- *Results (D17):* measure live the whole-class check-in duration and the number of refusals (off-campus, expired, wrong code).

**Amended by D32 (23/11), then removed by D33 (23/11):** point 1 first became a classification (campus / Apple
relay / off campus labels), then was removed entirely. Points 2-5 and P1-P3 are unchanged, except the code length
(4 digits, D33).

**Details fixed by D31 (23/11):** the allow-list is runtime data entered by the lecturer (UC-6), nothing hard-coded, and an empty list refuses everyone (OI-3); a new scan opens a new 1-minute window and resets the attempts to 0 (OI-7); an empty-nickname rejection is not counted as an attempt; the QR creation time is the start of its 10 s slice; `CF-Connecting-IP` is trusted only from a loopback peer.

**Status:** VALIDATED by the student — 2026-11-22 (points 1-5 and P1-P3).

## D31 — Design-level choices validated with design.md (23/11)

**Question.** The open points OI-1-OI-13 of `docs/design.md` section 9 and the architect's detailed choices.

**DECISION:** all accepted as proposed by the architect.

| Item | Choice | Amends |
|---|---|---|
| OI-1 | F5 comparison source: list of public repo URLs pasted by the lecturer on `/lecturer/peers` (PIN), stored in local SQLite; first 2, excluding the reviewed repo | D11 |
| OI-2 | Nickname 1-30 characters after trimming; not unique (the device token is the identity) | D6 |
| OI-3 | Campus IP ranges = data entered by the lecturer via UC-6; no code change; value pending the on-site measurement | D30 |
| OI-4 | Device token in a server-set cookie only (HttpOnly, 1 year), no localStorage. Known limit: restarting the quick tunnel changes the host name, so phones are treated as first-time (nickname typed again) | D6 |
| OI-5 | A new photo replaces D for the session | D7 |
| OI-6 | Export covers all sessions; XLSX with sheets "Check-ins" and "Summary"; CSV as `checkins.csv` + `summary.csv` | D8 |
| OI-7 | A new scan opens a new 1-minute window and resets attempts to 0 | D30 P2 |
| OI-8 | Projector page polls every 1 s; other pages 2-3 s | D4 |
| OI-9 | F5 masks owner and repository names of peer repos; reviews never stored | D11, D21 |
| OI-10 | F5 page open without PIN, accepted for the demo; mitigation: spending limit on the Anthropic account, URL known only in class | D11, D22 |
| OI-11 | Comment max 500 characters; message "Please keep your comment under 500 characters." | D29 |
| OI-12 | No fetchable comparison repo -> the review is shown with "No other submission was available for comparison." | D11 |
| OI-13 | GitHub archive download tested for real in task T16 and recorded in the tools report | D15 |
| Design | QR creation time = start of its 10 s slice | D30 |
| Design | `CF-Connecting-IP` trusted only from a loopback peer | D30 |
| Design | Empty allow-list refuses everyone | D30 |
| Design | Empty-nickname rejection does not count as an attempt | D30 P2 |
| Design | Nickname stored at the first successful check-in | D6 |
| Design | One `SECRET_KEY` with domain prefixes (`qr`, `code`) | D30 |
| Design | `GET /checkin` without token while a session is open -> "Scan the QR code on the projector." | D23 |

**Impact.** `docs/design.md` section 9 marked VALIDATED; SRS FR/NFR and error table, use cases aligned.

**Partly obsolete since D33 (23/11):** OI-3 and the design rows "`CF-Connecting-IP` trusted only from a loopback
peer" and "Empty allow-list refuses everyone" no longer apply (no network check). The other rows are unchanged.

**Status:** VALIDATED by the student — 2026-11-23

## D32 — Network origin of a check-in: campus, Apple relay or off campus, flagged (amends D30 point 1; closes open item 8) (R1, R13, R14, R16)

> **SUPERSEDED by D33 (23/11).** Short history only; must not be used for design.

**What was tried (23/11).** Field tests on campus showed that the D30 filter refused present students: iPhones with
iCloud Private Relay reach the app from Apple relay addresses, some phones leave through a VPN, and the campus Wi-Fi
is not reliable (a phone fell back to 5G on its own). D32 therefore accepted every network and **labelled** each
check-in `campus` (in the campus public range, measured on site, several exit addresses), `apple_relay` (Apple's
published Private Relay egress ranges for Israel, downloaded by a script) or `off_campus`, with markers and counters
for the lecturer and a column in the export. Rejected at the time: asking students to turn the relay off (no right to
require a setting change), local-LAN mode (the campus Wi-Fi isolates clients), GPS (personal data), refusing mobile
data (locks present students out).

**Why it was removed.** It was built (task T19) and tested on real phones: the campus and off-campus labels worked,
one relay case stayed unexplained. Since most students are on mobile data, most rows would read "off campus", so the
label did not single anybody out (noise) while costing a downloaded file, a script, a column and a migration. D33
removes it entirely.

**Status:** ~~VALIDATED by the student — 2026-11-23~~ **SUPERSEDED by D33 (23/11)**

## D33 — Remove the IP / network part entirely; 4-digit projected code (supersedes D32 and point 1 of D30; amends D30 point 3, D13, D21, D22, D25) (R1, R13, R14, R16)

**Question.** After the field tests of 23/11, does the network check (D30 filter, then D32 labels) still tell the
lecturer anything about who is in the room?

**Field findings (23/11, measured on campus by the student).**
- The campus public range is **shared by the whole campus** (several exit addresses), not by a room: at best the
  check proved "on campus", never "in this room".
- **Most students use 4G/5G**, whose IP says nothing about location (carrier-grade NAT, national egress pools; an IP
  geolocation lookup placed a phone on campus in another city). iPhones with **iCloud Private Relay** show Apple
  addresses.
- **LAN mode is impossible** (the campus Wi-Fi isolates clients), **GPS is personal data** (R16, D5), and students
  **may not be asked to change phone settings**.
- **D32 was built and tested on real phones:** campus and off-campus labels worked, one relay case stayed
  unexplained; the labels were judged **noise** (most rows would read "off campus").

**Options.**
1. *Keep D32 (accept everything, label campus / Apple relay / off campus).* **Rejected:** mostly "off campus" labels
   on present students, i.e. noise; and it costs a downloaded Apple file, a script, a column, a migration, markers and
   counters (KISS, R17).
2. *Return to the D30 filter (refuse anything but the campus range).* **Rejected:** locks out present students on
   4G/5G or behind Private Relay (D32 options 1 and 4).
3. *Data-over-sound token (a classmate's approach, considered 23/11).* **Rejected:** no stronger than the projected
   code (a sound can be relayed by a phone call just like a code by message), fragile in a noisy room, needs the
   microphone permission; already rejected in D5 ("ultrasound").
4. *Google sign-in (same classmate's approach).* **Rejected:** identifies students (personal data, R16, G1), and
   Google cannot restrict sign-in to a room.
5. *GPS / geolocation.* **Rejected** (R16, D5, D32 option 3).
6. *Remove the network part entirely and rely on the rotating QR, the projected code and the photo check.*
   **Chosen** (student, 23/11).

**DECISION: option 6.**
- **No client IP is read for attendance.** Removed: the campus allow-list and its lecturer page, the
  `CF-Connecting-IP` handling, the Apple relay range list, its download script and loader, the stored origin label,
  the live markers and counters, the export columns, and the off-campus error message.
- **Attendance anti-cheat keeps only** the rotating QR (new every 10 s, accepted if at most 15 s old on arrival) and
  the projected code, plus the unchanged rules of that flow: 1-minute window bound to the device cookie, at most 5
  code attempts per window (P2), a new scan opens a new window with 0 attempts (D31), nickname 1-30 characters (D31),
  one check-in per device per session, P3 (no in-app fallback), and the photo head-count consistency alert (D7,
  separate feature, unchanged).
- **The projected code has 4 digits (amendment, student, 23/11).** Range `0000`-`9999` (leading zeros kept, always
  exactly 4 characters), still regenerated every 5 s, the current or the immediately previous code accepted (P1).
  The student must type exactly 4 digits; anything else is a wrong code (counted as an attempt, like today).
  5 attempts per window and the reset on a new scan are unchanged.
- **No "surprise call" or other new feature** is added (not requested).
- **Hosting (D13):** plans A and B differ only by the base URL; no network configuration is needed before class.

**Consequences (written honestly).**
- The network no longer limits **where** a relayed QR and code can be used. A remote student with a **live
  accomplice** in the room (video call, or a message within the 5-10 s code tolerance) can check in from anywhere,
  and nothing marks that row any more.
- The **photo consistency alert (D7) is the room-level check**: it flags an inflated N (beyond about 7 absent
  check-ins for N about 45, documented limit of D7).
- What still holds: a forwarded screenshot alone is useless (the code changes every 5 s and the QR expires after
  15 s); one device = one check-in per session.
- **Code brute force (red-team finding F-02).** A new scan resets the attempts to 0 (D31), so a script holding one
  relayed QR image (valid for 15 s) can open window after window and guess the code without seeing it. Before D33
  this attacker had to be on the campus network (D30) or was labelled "off campus" (D32); now it can be anywhere.
  Options proposed to the student: (a) count wrong codes per device for the whole session (e.g. 10 -> blocked), (b) a
  4-digit code. **The student chose (b); (a) is not adopted.** Effect: with 2 valid codes at any time (P1) the
  expected number of guesses goes from about 500 (3 digits) to about **5,000** (4 digits), i.e. **x10**. This slows a
  script, it does **not** stop it. **Residual risk accepted and recorded** (to be reported in `docs/results.md` and
  the defence notes); the D7 photo alert remains the safety net for an inflated N.

**Justification.** R1 "as simple as possible"; R14 (no setting to change, no student locked out); R16 / G1 (no
location, no identity, and now no IP read at all); R17 KISS (a whole mechanism removed because, measured in the
field, it did not inform the lecturer); D7 kept as the statement's own control (R2).

**Impact.**
- D30 point 1 and the D32 amendment removed; D30 point 3 amended (4 digits); D13 and D22 notes obsolete; D21: no
  client IP read for attendance; D25: no injectable client IP; open item 8 obsolete; question 5 to the lecturer
  obsolete.
- *Design (`design.md`):* `NetworkPolicy`, `NetworkOrigin`, `count_origins`, `relay_ranges`, `ParsedRanges`, the
  update script, `client_ip()`, the allow-list route and page, `OffCampusError`, `InvalidNetworkRangeError`,
  `Config.relay_ranges_path`, `CheckIn.network_origin`, `SessionSummary.origin_counts` and the migration helper
  removed; `RotatingCredentials` gives 4-digit codes; tasks T4, T9 and T19 marked "removed by D33"; new tasks T20
  (remove the network part) and T21 (4-digit code). An existing database keeps its `network_origin` column and its
  `campus_range` rows untouched and unused (KISS, no migration).
- *SRS:* FR-1.2-FR-1.4 and FR-1.19 removed (numbering kept); FR-1.8, FR-1.14, FR-1.18, error table, glossary and NFRs
  updated; "3-digit" becomes "4-digit".
- *Results (D17):* report the check-in duration and refusals; no network counts any more.

**Status:** VALIDATED by the student — 2026-11-23 (including the 4-digit amendment for F-02, option (b))

## D34 — Video summary F4 for real class recordings, background job (closes D10) (R7, R8, R15, R16; amends D1, D21, D25)

**Question.** D10 deferred F4 with a candidate "live demo on a short 2-3 min clip". F1-F3 and F5 are done. Should F4
only show a short clip in class, or give the lecturer a real summary of the recordings they actually make
(Zoom / Meet / Classroom files, 60-90 minutes)?

**Facts.** Measured in the tools report (2.6) on the demo laptop (Apple M3, CPU, int8, `beam_size=1`, VAD on):
real-time factor 0.06 (`base`) and about 0.17-0.22 (`small`); Hebrew detected on `m21.mp4` (p = 0.94-0.96); a 90-minute lecture
therefore takes about **6 min (`base`) to roughly 15-20 min (`small`)** to transcribe (extrapolation), far longer than an HTTP request (and the
quick tunnel cuts requests at 100 s, tools report 2.9). `faster-whisper` 1.2.1 needs `av<17`. The provided `m21.mp4`
is only 5.7 s long. The `small` model (~460 MB) is downloaded once from Hugging Face at its first use.

**Options.**
1. *Short-clip-only demo (D10 candidate): transcribe inside the request, clip of 2-3 min.* **Rejected:** it shows the
   pipeline but does not serve the lecturer's real need (R7: "their class video"); a real recording would time out.
2. *Full recordings of any length, processed by a background job with a status page.* **Chosen** (student, 23/11).
3. *Pre-computed summary shown in class.* **Rejected:** against D1 and the spirit of D10 (everything runs live).
4. *Cloud transcription API (OpenAI, Google, ...).* **Rejected:** the audio of the class (voices, possibly students)
   would leave the laptop (R16), and it needs another account and key; local faster-whisper is fast enough.
5. *Job queue (Celery / RQ + Redis) or a separate worker process.* **Rejected:** a second service to install and run
   live for one job at a time (R17 KISS); one Python thread + SQLite status is enough.

**DECISION: option 2.**
1. **Page "Video summary"** in the lecturer area (PIN, D22): upload one recording (video or audio: mp4, m4v, mov,
   mkv, webm, avi, m4a, mp3, wav, aac, ogg, opus, flac). The upload limit is raised **for this route only** to
   `VIDEO_MAX_BYTES` (default 2 GB); the global limit stays 25 MB. The upload is streamed to a temporary file, never
   held entirely in memory.
2. **Audio extraction** with `ffmpeg` (subprocess, argument list, mono 16 kHz WAV) into a temporary file; a file that
   ffmpeg cannot read, or that has no audio track, is refused with `UnreadableVideoError` ("We could not read this
   video file.").
3. **Transcription** with faster-whisper behind the port `Transcriber` (adapter `FasterWhisperTranscriber`): default
   model **`small`** (Hebrew quality), language auto-detected unless `WHISPER_LANGUAGE` is set, CPU, int8, VAD on.
   It runs in **one background thread, one job at a time**; a second upload while a job is running is refused with a
   plain message.
4. **Summary** with the existing `LLMClient` (Claude, D12): structured (topics covered, key notions, definitions and
   examples, what to review), in the transcript's language unless the lecturer asks for another one (the four section headings are translated into that language, and no remark about the instructions or the transcript is allowed outside them; real trial, 23/11); a transcript
   above a safe size is summarised by **map-reduce** (chunks summarised, then merged). The prompt states that the
   transcript is untrusted content (prompt injection) and must not be obeyed.
5. **Status page** polled every few seconds (D4): queued / extracting audio / transcribing / summarising / done /
   failed, in plain words (D23); the lecturer can leave and come back. The finished summary is shown and downloadable
   as `.md` and `.txt`.
6. **Privacy (R16, D21):** the uploaded file and the audio are deleted right after transcription (and on every
   failure path, in a `finally`); the transcript is never written to disk or the database and is dropped after
   summarising; only the summary text, the job status and timestamps are kept (SQLite table `summary_job`; a lecture
   summary is not personal data). The original file name is not stored. Nothing is written inside the repository
   except the SQLite database in `instance/` (temporary files go to the system temp directory, the model to the
   Hugging Face cache in the user's home).
7. **Failures:** LLM unavailable (no key, network or API error) -> `LLMUnavailableError("summary")`, job failed,
   files deleted (with no key, the upload is refused at once, before 15 minutes of transcription). Whisper model
   missing or not loadable, or `ffmpeg` missing -> a plain "transcription unavailable" message. The model download
   happens only at the first real use, never in tests.
8. **Demo:** a 4-minute Hebrew lecture clip (Technion, "Introduction to graph theory 1", standard YouTube licence),
   kept **local only** in `docs/supplementary/` and never committed; `m21.mp4` (5.7 s) is too short to show a summary.
   R8: `docs/results.md` compares our summary with the provided Zoom example qualitatively.
9. **Tests (D25 amended):** `FakeTranscriber`, a fake audio extractor, `FakeLLMClient` and an inline job runner: no
   ffmpeg, model or network needed; one optional integration test runs only if `ffmpeg` and the cached model exist.

**Consequences.**
- One background thread exists (the only one in the app); its status lives in SQLite, so a page reload or another
  browser shows it. If the app stops during a job, the job is marked failed at the next start and its temporary files
  are deleted.
- The `WHISPER_MODEL` default changes from `base` to `small`; new settings `VIDEO_MAX_BYTES` and `VIDEO_WORK_DIR`.
- The transcript (text only) is sent to the Anthropic API, as already allowed by D12; voices are never sent.
- New system dependency: the `ffmpeg` command line tool (to be installed and recorded in the tools report, D15).

**Risks (written honestly).**
- **Long processing time:** roughly 15-20 min for a 90-minute lecture with `small` (6 min with `base`, set by
  `WHISPER_MODEL`); no promise is made beyond the measured real-time factors.
- **CPU load during class:** transcription uses the laptop's CPU; a long job started during the attendance check-in
  may slow the server. Advice: start long recordings outside the check-in; the class demo uses the 4-minute clip
  (T18f: about 70 s in total for a 244 s clip, of which about 54 s of transcription with `small`).
- **Model download ~460 MB, once**, at the first real use (needs network); to be done before class.
- **Upload through the tunnel:** Cloudflare's free plan documents a 100 MB request-body limit (not measured here)
  and the tunnel cuts requests at 100 s: large recordings are uploaded on the laptop itself (`http://localhost`).
- **Demo clip licence:** standard YouTube licence: used locally for the class demo only, never committed or
  redistributed; no output derived from it is committed unless checked free of personal data (D21).
- **Personal data spoken in a recording** (e.g. a student's name said aloud) may reach the transcript and the LLM;
  the prompt asks the model not to name students; residual risk accepted.

**Red team 24/11 (clear defects fixed, no product choice taken).** (a) `python -m app` takes an exclusive `flock` on
`instance/app.lock` before `create_app`: a second instance exits with "The app is already running in another
terminal." without touching the database (skipped where `fcntl` does not exist); (b) `_run` re-reads the job before
the transcription and summary stages and stops quietly, without an LLM call, if it is no longer active; (c) each map
note is neutralised like the transcript before it is wrapped in `<notes part="i">`; (d) the too-large message shows MB
below 1 GB ("100 MB"), GB above; (e) an ffmpeg timeout gives the new `VideoTooLongError` ("This recording is too long
to process. Please upload a shorter recording."). **Known limit (R-F4-6):** the upload needs about **twice the file
size of free disk space**, because Werkzeug spools it to a temporary file before the copy into the job directory.
Still open for the student: duration cap, cancel button, LLM retries, export date format.

**Justification.** R7 (the lecturer's own recordings), R8 (structured summary beats the Zoom example), R15 (file
upload, no Zoom/Meet API), R16 (media deleted, transcript not kept, no file name), R17/R18 (reuse ffmpeg,
faster-whisper, Claude; one thread instead of a queue), D1 (live, no pre-computed output).

**Impact.** D10 closed; D1 summary row updated; D21 and D25 extended as above. *Design:* `VideoSummaryService`,
`LectureSummariser`, `SummaryRepository`, `SummaryJob` / `JobStatus`, ports `Transcriber`, `AudioExtractor`,
`JobRunner` with adapters `FasterWhisperTranscriber`, `FfmpegAudioExtractor`, `ThreadJobRunner`; table
`summary_job`; task T18 rewritten (T18a-T18f). *SRS:* section 3.4 FR-4.1-FR-4.9, error table, NFR-13.

**Status:** VALIDATED by the student — 2026-11-23

---

## D35 — Display time zone: Israel local time (R3, R14, R16; amends D8, D34)

**Question.** The first end-to-end check (23/11) showed that the attendance export and the pages showed UTC, so a
check-in at 21:29 local time appeared as 19:29. Which time should users see?

**Facts.** The class and the lecturer are in Israel; the clock changes between winter time (UTC+2) and summer time
(UTC+3). Times are stored as UTC epoch seconds (design 3.1, `Clock`).

**DECISION.** Every user-visible time (attendance spreadsheet export, lecturer and projector pages, F4 summary date) is
shown in **Israel local time**, IANA zone `Asia/Jerusalem`, with daylight-saving rules. **Storage stays UTC.** The
export headers name the zone ("Session date (Jerusalem time)", "Checked in at (Jerusalem time)") so nobody reads the values as UTC. The zone is the constant
`DISPLAY_TIMEZONE = "Asia/Jerusalem"` in `app/timezone.py` (not an environment variable); the `tzdata` package is added to
`requirements.txt` so the zone database exists on every platform (Windows, containers).
Rejected: showing UTC (confusing for the lecturer); the browser's own zone (the export is a file generated by the
server; dates would differ between devices); storing local time (breaks at the daylight-saving change).

**Impact.** *SRS:* FR-1.18 (export in local time, zone named in the header), NFR-7 unchanged. *Design:* helper
`app/timezone.py` (`to_local`, `format_local`), used by templates and `AttendanceExporter`; `Config` note. *README:*
configuration table. *Tests:* conversion in winter (UTC+2) and summer (UTC+3), header names the zone, stored values
remain UTC.

**Status:** validated by the student — 2026-11-23

---

## Questions still worth asking the lecturer/TA

1. ~~Is the chain-of-trust check-in acceptable (D5)?~~ Answered 2026-11-22 (the lecturer left the choice to the student, with a concern about time/attention); the chain has since been replaced by D30 (22/11), which is simpler and addresses that concern. Optional: tell the lecturer about the change.
2. Date of the class demo; must the results description include it (D17)?
3. Is there a Moodle upload in addition to the Form (D18)?
4. Optional: is a nickname-based attendance sheet acceptable under "no personal information" (D6), and may anonymised comparisons with other students' repos be shown in class (D11)?
5. ~~Optional: does the campus Wi-Fi share its public IP range with other networks (e.g. dormitories, eduroam guests), which would widen what the D30 filter accepts?~~ Obsolete since D33 (no network check).

## Items still OPEN — to be decided by the student

6. ~~OPEN — F5 comparison source (D11).~~ **CLOSED by D31 (23/11):** list pasted by the lecturer on `/lecturer/peers`.
7. ~~OPEN — Nickname rules (D6).~~ **CLOSED by D31 (23/11):** 1-30 characters, not unique.
8. ~~OPEN (value only) — Campus IP allow-list (D30).~~ **CLOSED by D32 (23/11)** (campus public range measured on
   site), then **obsolete since D33 (23/11):** the allow-list no longer exists.
9. ~~OPEN — Brute force of the projected code through rescans (red-team F-02).~~ **CLOSED by D33 (23/11):** the
   student chose a 4-digit code (option (b)); the per-device session-wide error count (option (a)) is not adopted.
   Residual risk recorded in D33 (about 5,000 expected guesses instead of about 500: slower, not stopped).
