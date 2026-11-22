# Decisions — Ex2 "Web-based Teaching Tool"

Resolutions of the open questions (OQ1-OQ14 in `docs/requirements.md`) and of the technical choices left open by
the statement. Proposed by the ambiguity analysis, **validated by the student on 2026-11-22**.
Requirements are cited as R<n>, statement locators as F/Req/G/TD/QA (see `docs/requirements.md`).

Guiding rule: the **simplest option that fully satisfies the requirements** (KISS, Req2), that can really be
implemented and shown live (G2, Req1), reusing existing code (Note, G3, TD10), with **no personal data** (G1, QA6),
within the days available (from 22/11/2026; internal target: demo-ready by 29/11/2026, submission by 30/11/2026,
see D16-D17). No over-design (lesson from Ex1).

Legend: **[ASK]** = still worth confirming with the lecturer/TA.

## Summary

| D | Topic | Decision | Status |
|---|---|---|---|
| D1 | Demo scope (OQ1) | All 5 features fully implemented and working live (no pre-computed outputs); F1 first and most robust; F4 deferred (D10) | VALIDATED |
| D2 | Tech stack | Python 3.11+ / Flask, server-rendered mobile-first HTML + small vanilla JS | VALIDATED |
| D3 | Storage | SQLite (stdlib `sqlite3`), one local file, git-ignored | VALIDATED |
| D4 | Real time | Short polling (2-3 s); no websockets | VALIDATED |
| D5 | Attendance mechanism (OQ2) | Chain-of-trust check-in at end of class: projector root QR (first 5 scans only), then student-to-student QR sponsoring (3 by default, configurable 1-5); scanned with the phone's native camera; QR regenerates every 10 s, accepted if <= 15 s old on arrival, then 2-min claim to confirm; sponsor tree stored; lecturer phone QR as fallback; no typed code | VALIDATED — lecturer consulted (concern: time/attention), measured during the live class demo |
| D6 | Student identity (OQ4) | Nickname entered once, remembered by a random device token (cookie/localStorage); automatic recognition afterwards | VALIDATED |
| D7 | Photo head count (OQ3) | YuNet, whole image, score threshold 0.4 (recall ~94 %, precision ~96 %); no manual correction; automatic consistency alert (asymmetric tolerance); photo discarded after counting | VALIDATED |
| D8 | Spreadsheet online/offline; offline comments (OQ5) | Live in-app table + CSV/XLSX download; F2 offline = asynchronous | VALIDATED |
| D9 | Polls (F3) | One question, 2-4 options, one vote per token, live results | VALIDATED |
| D10 | Video summary F4 (OQ6) | No pre-computed summary; to revisit after F1-F3; candidate: live demo on a short 2-3 min clip (faster-whisper + Claude) | DEFERRED |
| D11 | Homework review F5 (OQ6) | Public repo URL -> capped text extract -> Claude review + anonymised comparison with 1-2 other repos; runs live, no pre-computed fallback | VALIDATED |
| D12 | LLM provider and secrets | Anthropic (Claude); model from `ANTHROPIC_MODEL`, default `claude-sonnet-5-5` (to confirm by a real call); key in `.env` | VALIDATED |
| D13 | Demo hosting (OQ7) | Laptop + Cloudflare quick tunnel; plan B hotspot/LAN over plain HTTP (works: no in-page camera); plan C recorded run | VALIDATED |
| D14 | Documents format and layout (OQ11) | Markdown in `docs/`, one file per deliverable, Mermaid, README links all | VALIDATED |
| D15 | Tools report (OQ12) | Every tool we suggest, tested for real with command, input, result, date, version | VALIDATED |
| D16 | Deadline (OQ8) | Extended by the lecturer: submission by 30/11/2026 | VALIDATED |
| D17 | Demo date and results (OQ9) | Demo-ready by 29/11/2026; results from rehearsal, updated after class demo if allowed | VALIDATED [ASK] |
| D18 | Submission channel (OQ10) | Google Form, filled by the student only; check Moodle for an extra upload | VALIDATED [ASK] |
| D19 | Live statement (OQ13) | Re-read the live Google Doc at Phase 2 and before submission | VALIDATED |
| D20 | Individual vs team (OQ14) | Individual work | VALIDATED |
| D21 | Personal data (R16) | Fictitious data in repo/demo; provided files local only, aggregate results only | VALIDATED |
| D22 | Lecturer access | Single lecturer PIN from an env var; no accounts | VALIDATED |
| D23 | Error messages | Plain user messages, no internal identifiers/stack traces; details in server log | VALIDATED |
| D24 | Git practice | Frequent small commits until submission, conventional messages, no `Co-Authored-By` trailer, agents never push | VALIDATED |
| D25 | Test tooling | pytest + Flask test client; ML/LLM mocked; detector tested on non-personal images | VALIDATED |

"VALIDATED" = "VALIDATED by the student — 2026-11-22" unless stated otherwise. "DEFERRED" = "DEFERRED by the
student — 2026-11-22".

---

## D1 — Demo scope (OQ1; R4, R5-R10, R12, R17, R19, R33)

**Question.** Must all five features be implemented in the demo app, or only designed?

**Options.** 1. *All five fully implemented.* 2. *F1 only, F2-F5 design only* (weak demo, Req1). 3. *F1 complete, F2-F3 simple, F4-F5 thin wrappers with pre-computed fallback* (initial proposal).

**DECISION: option 1 (changed by the student).**
- All five features are fully designed **and** fully implemented (real working paths, not thin wrappers).
- F1 (R1-R3: chain-of-trust check-in D5, photo head count D7, live table + CSV/XLSX D8, check-ins vs counted comparison) is built **first** and is the most robust part.
- F2 (D8), F3 (D9), F4 (D10), F5 (D11) are real implementations.
- **No pre-computed outputs** for F4/F5: every feature must work live on demo day (student's principle). Network/hosting failures are covered by the hosting plans of D13, not by canned results.
- F4 is **deferred** (D10): revisited after F1-F3 are done.
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

**DECISION:** short polling every 2-3 s (fetch JSON). Rejected: SSE (flaky through tunnels), WebSockets (extra dependency, more failure modes live). "Real time" = visible within a few seconds. Also used to refresh the rotating QR codes of D5.

**Impact.** Sequence diagrams show a polling loop; SRS NFR "update visible within 5 s".

**Status:** VALIDATED by the student — 2026-11-22

## D5 — Attendance mechanism: chain-of-trust check-in (OQ2; R1, R13, R14, R16)

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

**Status:** VALIDATED by the student — 2026-11-22 (lecturer consulted: concern about time/attention; addressed above; measured during the live class demo)

## D6 — Student identity without personal data (OQ4; R16, R3)

**Options.** 1. *Self-chosen nickname + random device token.* 2. *Anonymous token only* (sheet unreadable). 3. *Pick a name from the course list* (personal data; violates G1, QA6).

**DECISION: option 1, "Moodle-like" simplicity without accounts.** The student enters a self-chosen nickname **once** (first use); the phone remembers a random token (cookie + localStorage). At every later check-in the student is recognised automatically, with no typing. The UI warns "do not use your real name or ID". No name/ID/e-mail field anywhere. Spreadsheet columns: session date, nickname, check-in time, sponsor nickname (or "root via projector" / "lecturer"); per-session summary: check-ins, faces detected, consistency status (D7).

**Justification.** G1 "No need integrate with ... מידע אישי"; QA6 the lecturer removed IDs from the list.

**Impact.** Data model; README scope; tests for first-use and returning-device flows.

**Status:** VALIDATED by the student — 2026-11-22

## D7 — Photo-based head count (OQ3; R2, R16, R25)

**DECISION: OpenCV YuNet face detector on the whole image, score threshold 0.4, fully automatic.**
- **Detector:** YuNet (`face_detection_yunet_2023mar.onnx`, 0.23 MB, MIT model, CPU, < 0.1 s per photo). Count only, no identification.
- **Measured accuracy** (tools report 2.5, 4 provided photos re-counted carefully box by box, 173 people): recall ~94 % (163/173), precision ~96 % (6 false positives). All misses are faces **not visible** (head down, asleep, hand over face, hidden behind others, back turned). Practical advice shown to the lecturer: **take the photo when the students look up**.
- **No tiling:** tested and rejected — only +1 real person, about twice the false positives (mostly clasped hands), 5-15x slower.
- **No manual correction by the lecturer** (rejected by the student: the app must stay automatic).
- **Automatic consistency alert** instead. With N = number of check-ins (D5) and D = number of detected faces:
  - "consistent" if `N - max(7, ceil(0.15 * N)) <= D <= N + max(4, ceil(0.10 * N))`, otherwise "anomaly".
  - Asymmetric because the detector undercounts more than it overcounts (measured error -6 to +3). Example: N = 45 -> consistent for D from 38 to 50. 0 false alerts on the 4 refined photos.
  - On "anomaly", the sponsor tree (D5) helps the lecturer investigate (which branches look suspicious).
- **Documented limit:** fraud becomes visible only beyond about 7 check-ins of absent people for N ≈ 45; fewer stay inside the measurement noise. Stated in the SRS, design and results.
- **Two-photo mode** (front rows / back rows): not testable with the provided photos (no real pairs; only a simulation); **not adopted for now**.
- **Rejected:** Ultralytics YOLO (worse counts, AGPL-3.0, PyTorch), InsightFace SCRFD (non-commercial model licence), MediaPipe (selfie-range), cloud vision API (sends a class photo to a third party, G1).
- **Privacy:** the photo is processed in memory and discarded; only the count is kept (D21).

**Impact.** `HeadCounter` behind an interface (YuNet implementation, threshold configurable, default 0.4); a separate `ConsistencyCheck` (pure function of N and D) shown as "checked in N / detected D / consistent|anomaly"; no "edit count" use case. Tests: alert rule at its boundaries (e.g. N = 45: D = 37/38/50/51), small-N cases where the `max(7, ...)`/`max(4, ...)` floors apply; detector on non-personal images (D25). Tools report table with file names only.

**Status:** VALIDATED by the student — 2026-11-22

## D8 — Online/offline spreadsheet; offline comments (OQ5; R3, R5)

**DECISION:** online = live table in the lecturer page; offline = CSV download (+ XLSX via `openpyxl`). F2 "offline" = asynchronous: comments can be posted at any time, also outside a live session, and read later. Rejected: Google Sheets API sync (OAuth, network), PWA offline queue (extra code). Google Sheets import listed as extension.

**Impact.** SRS defines online/offline explicitly; use cases "Download attendance sheet", "Post comment outside class".

**Status:** VALIDATED by the student — 2026-11-22

## D9 — Polls (F3; R6)

**DECISION:** the lecturer types one question and 2-4 options; one vote per device token; live counts/bars (D4); the lecturer closes the poll. No free text, no quizzes, no timers. Rejected: external poll tools (accounts).

**Status:** VALIDATED by the student — 2026-11-22

## D10 — Video summary F4 (OQ6; R7, R8, R15)

**Current direction (not final):** uploaded video -> local transcription with `faster-whisper` (video never leaves the laptop) -> structured Claude summary (topics, key points, homework/action items, questions raised) to beat the Zoom baseline (R8). No Zoom/Meet integration (R15). Rejected: cloud transcription (audio sent out), fully local LLM (slow).

**No pre-computed summary.** The student wants F4 to work live on demo day; a canned output is not acceptable (D1).

**Deferred.** The decision is to be revisited after F1-F3 are done. **Candidate:** a live demo on a short 2-3 min clip, using faster-whisper `base` (speed) or `small` (quality); measured in the tools report (2.6): real-time factor 0.06 (`base`) and 0.17 (`small`) on CPU, i.e. roughly 10-30 s of transcription for a 2-3 min clip, plus one Claude call. Outputs from the provided video stay local unless checked free of personal data (D21).

**Impact.** Design keeps `VideoSummarizer` = `Transcriber` + `LLMClient` (D12) so F4 can be added without redesign; F4 is last in the task order (D1).

**Status:** DEFERRED by the student — to revisit after F1-F3; candidate: live demo on a short 2-3 min clip (faster-whisper base/small measured in tools report) — 2026-11-22

## D11 — Homework review with comparison F5 (OQ6; R9, R10, R16)

**DECISION:** public repo URL -> download archive (no token) -> README + main source files capped (~40-60 KB text) -> Claude review against a short rubric -> comparison with 1-2 other repos of the same assignment, shown anonymised ("Submission B, C"), plus simple deterministic metrics (file/line counts). **Runs live; no pre-computed fallback** (same principle as D10: it must work on demo day). If the API or network fails, the user sees a plain error message (D23). Generated reviews of other students' work are not committed. Rejected: static analysis only (not an LLM review), embeddings over the whole list (over-design).

**Impact.** Classes `RepoFetcher`, `HomeworkReviewer`, `LLMClient`.

**Status:** VALIDATED by the student — 2026-11-22

## D12 — LLM provider and secrets (OQ6; R11, R17)

**DECISION:** Anthropic (Claude). Model name read from the env var `ANTHROPIC_MODEL`, with a default set to a current Claude model available on the account. The tools report used `claude-sonnet-4-5`, which reaches end-of-life on **30/11/2026**; the default is therefore a newer model, **`claude-sonnet-5-5`** (listed by the account's `models.list`), **to be confirmed by a real call during coding**. Key in `.env` as `ANTHROPIC_API_KEY` (git-ignored); `.env.example` committed with placeholders. One small `LLMClient` interface (Claude implementation + fake for tests). Only text is sent (transcript, public repo extracts); never photos or the participant list. Without a key: the app runs (F1-F3 unaffected); F4/F5 show a plain "LLM service not configured/unavailable" message (D23), no pre-computed output.

**Status:** VALIDATED by the student — 2026-11-22

## D13 — Hosting for the live demo (OQ7; R13, R19)

**DECISION:** app on the laptop + Cloudflare quick tunnel (`cloudflared tunnel --url`, no account, public HTTPS URL). **Plan B:** phone hotspot / LAN URL over plain HTTP; the check-in still works because students scan with the phone's native camera and no in-page camera access is needed (D5); the QR codes encode the configured base URL of the active plan. **Plan C:** screen recording of a full rehearsal + lecturer page with 2-3 simulated phones. Rejected: ngrok (account, interstitial), free cloud hosts (RAM, cold start, deploy effort).

**Impact.** README "Run the demo" (including how to set the base URL encoded in the QR codes for plans A and B); tools report tests cloudflared from a real phone on mobile data.

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

**DECISION:** every tool we suggest is actually run; each entry: purpose, alternatives, exact command/code, input (no personal content), observed result, date, version, verdict. Tools: Flask, qrcode, QR scanning with the phone's native camera app (adopted in D5; the in-page scanner approach tested earlier is documented as rejected), OpenCV YuNet, Ultralytics YOLO, faster-whisper, Anthropic API, cloudflared, openpyxl.

**Status:** VALIDATED by the student — 2026-11-22

## D16 — Deadline (OQ8; R36)

**DECISION:** the lecturer **extended the deadline** (replacing the date written in the statement, QA3). Internal schedule: **demo-ready by 29/11/2026, submission by 30/11/2026**.

**Status:** VALIDATED by the student — 2026-11-22

## D17 — Demo date and results description (OQ9; R34, R35)

**DECISION:** demo-ready by 29/11/2026. `docs/results.md` written from the full rehearsal (what worked, head-count accuracy and consistency alert, chain-of-trust rehearsal with several tabs/phones, timings, limits), with a section to update after the class demo, where the whole-class check-in duration of D5 is measured live, if allowed. **[ASK]** date of the class demo and whether TD12 must include it.

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

**DECISION:** frequent small commits after each validated document or task, spread from 22/11 until submission; conventional messages (`docs: add SRS`, `feat: chain-of-trust check-in`); existing global git identity unchanged; **no `Co-Authored-By` trailer** (AI use is disclosed in the README "Tools used" section instead); **agents never push**, the student publishes. Before each commit: check that no personal data or secret is staged.

**Status:** VALIDATED by the student — 2026-11-22

## D25 — Test tooling (R32)

**DECISION:** `pytest` + Flask test client; unit tests per class from `docs/design.md`; `LLMClient` and `Transcriber` replaced by fakes (no network, no key); `HeadCounter` tested on non-personal images with a tolerance (e.g. ±20 %), plus the local-only accuracy measurement on the provided photos (reported, not automated); the D7 consistency rule tested exhaustively at its boundaries (pure function). Time-dependent logic of D5 (10 s QR regeneration, 15 s acceptance window checked on request arrival, 2-minute claim) tested with an injectable clock. Manual end-to-end rehearsal with several browser tabs and 2-3 phones before the demo.

**Status:** VALIDATED by the student — 2026-11-22

---

## Questions still worth asking the lecturer/TA

1. ~~Is the chain-of-trust check-in acceptable (D5)?~~ Answered 2026-11-22: the lecturer leaves the choice to the student, with a concern about time/attention. No class test is possible before the demo: the duration is measured live during the class demo (D5, D17).
2. Date of the class demo; must the results description include it (D17)?
3. Is there a Moodle upload in addition to the Form (D18)?
4. Optional: is a nickname-based attendance sheet acceptable under "no personal information" (D6), and may anonymised comparisons with other students' repos be shown in class (D11)?
