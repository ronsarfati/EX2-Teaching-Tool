# Requirements — Ex2 "Vibe Coding & Deep Designing: Web-based Teaching Tool"

Source of truth: the assignment statement (PDF, 3 pages; page 3 is a photo of the class illustrating Q&A 2).
Locators: **Goal**, **Note**, **Problem**, **F1..F5** (Features), **Req1..Req2** (Requirements),
**G1..G6** (Guidelines; G4-G6 are empty in the statement), **TD1..TD12** (To Do), **QA1..QA6** (Q&A).

Legend. Type: FUNC = functional, NONFUNC = non-functional, DELIV = deliverable, CONSTR = constraint.
Priority: **MUST-MAIN** (main feature), **MUST**, **SHOULD**, **COULD**.
Priority of F2..F5 vs. demo scope is an open question (OQ1); the values below reflect only what the statement says.

## 1. Requirements

### 1.1 Features

| ID | Type | Priority | Requirement | Source | Acceptance criterion |
|---|---|---|---|---|---|
| R1 | FUNC | MUST-MAIN | Students can mark their own attendance in class automatically, or as simply as possible, from their smartphone. | F1: "Students can mark their attendance in class automatically (or as simple as possible)" | In the demo, a student marks attendance from a phone browser in a few taps (no install), and the lecturer sees it recorded. |
| R2 | FUNC | MUST-MAIN | The lecturer can evaluate attendance with a simple and efficient method, e.g. shooting a photo of the class and getting an automatic student count. | F1: "evaluate the attendance ... (e.g., shooting a photo can performing an automatic student count)" | Uploading/shooting a class photo returns a head count; count is compared with the number of marked students. Tested on the provided class photos (locally). |
| R3 | FUNC | MUST-MAIN | The lecturer can get a spreadsheet with the attendance details, available online and offline. | F1: "The lecturer can get an online/offline spreadsheet with the details" | Lecturer obtains a spreadsheet (e.g. viewable online and downloadable as a file openable offline) listing attendance details for a session. |
| R4 | CONSTR | MUST-MAIN | Feature 1 (R1-R3) is the main, most important feature and must be designed and demonstrated first and most thoroughly. | F1: "this is the main (most important) feature" | Design docs and demo give F1 the largest coverage; F1 works end-to-end in the demo. |
| R5 | FUNC | MUST | Students can post comments and raise suggestions, both in real time (during class) and offline (outside class / asynchronously). | F2: "Students can comment and raise suggestions in real time / offline." | A comment posted from a phone appears on the lecturer view without reload (real time) and a comment posted outside a session is stored and visible later. |
| R6 | FUNC | MUST | Lecturers can create on-the-spot, KISS polls about the current learning material; students answer them. | F3: "Lecturers can create on-the-spot (KISS) polls regarding the current learning materials." | Lecturer creates a poll in under a minute during the demo; students vote from phones; results are shown. |
| R7 | FUNC | MUST | Lecturers can get an ML-generated summary of their recorded class video (Zoom, Meet, Google Classroom recordings). | F4: "Lecturers can get an ML summary for their class video (as recorded by Zoom, Meet, G.Classroom)." | Given a recorded video file (e.g. the provided m21.mp4), the system produces a text summary. |
| R8 | NONFUNC | SHOULD | The video summary should be better than the automatic Zoom summary given as example ("nothing to write home about"). | QA5 | The results description compares our summary with the Zoom example (qualitatively). |
| R9 | FUNC | MUST | Students and teachers can get a deep LLM review of a homework submission. | F5: "Students & teachers can get a deep review (LLM) of their homework" | Given a homework (e.g. a repo link from the provided list), the system returns an LLM review. |
| R10 | FUNC | MUST | The homework review includes a comparison with other students' work. | F5: "including comparisons to other students' work" | The review output contains an explicit comparison against at least one other submission from the provided list. |
| R11 | NONFUNC | SHOULD | The tools are simpler than current online teaching tools and "LLM-ready". | Problem: "we need better, simpler and LLM-ready tools for proper learning" | Design docs justify simplicity and show where LLM/ML is used or pluggable. |
| R12 | DESIGN | MUST | The work is an end-to-end design of a web application for teaching in class. | Goal | Design documents cover the full flow from student phone to lecturer output for each feature. |

### 1.2 Requirements and guidelines (constraints)

| ID | Type | Priority | Requirement | Source | Acceptance criterion |
|---|---|---|---|---|---|
| R13 | CONSTR | MUST | The application must work in this actual class, shown in a real (live) demo. | Req1: "It should work in this class, represented in a real demo." | Live demo in class, reachable by classmates' phones over the network available in the room. |
| R14 | NONFUNC | MUST | KISS: students use a simple smartphone app that is a web application (no native install). | Req2: "KISS - the students should have a simple smartphone app (web-based application)." | Student pages are usable on a phone browser (responsive, minimal steps, no install, no account creation beyond what is strictly needed). |
| R15 | CONSTR | MUST | No integration with Moodle or Zoom is required (and none should be built). | G1: "No need integrate with Moodle, Zoom" | No Moodle/Zoom API in the design; video input is a file. |
| R16 | CONSTR | MUST | No personal information (מידע אישי): the system must not require or store personal data; the repository contains none. | G1: "or מידע אישי"; QA6 (IDs removed from the student list) | No names/IDs/e-mails/class photos in the repo; demo uses fictitious or anonymised data; attendance identifies students without personal data (exact scheme: OQ4). |
| R17 | CONSTR | MUST | Only design what can actually be implemented. | G2: "You should only design what can be implemented." | Every designed component maps to an existing tool/library or to demo code; no speculative components. |
| R18 | CONSTR | MUST | Composing/reusing existing code is preferred over writing code; the result must still be compiled into a runnable web app. | Note: "using other code is preferred"; G3: "There is no need to code, yet you should be able to compose (aka compile) a web application"; TD10: "vibe code vs find and compose" | Tools report and README list reused components/services; the app builds and runs. |
| R19 | DEMO | MUST | The in-class demo lasts 10 minutes. | G3: "demo it in class (10 m')" | Demo script fits in 10 minutes, with a fallback plan. |

### 1.3 Deliverables (To Do 1-12)

| ID | Type | Priority | Requirement | Source | Acceptance criterion |
|---|---|---|---|---|---|
| R20 | DELIV | MUST | Create a (GitHub) repository. | TD1: "Create a repository" | Public repo exists with README at root. |
| R21 | DELIV | MUST | The README defines the problem. | TD1: "define the problem ... (all in the README)" | README has a "Problem" section. |
| R22 | DELIV | MUST | The README defines the scope of the project (in/out of scope). | TD1: "define ... the scope of the project (all in the README)" | README has a "Scope" section listing in-scope and out-of-scope items. |
| R23 | SUBMIT | MUST | Submit the repository link via the Google form "Ex2 - Github Submission" (filled by the student only, never by an agent). | TD2: "Submit it via this form."; QA3: "see Ex2 submission link" | Student confirms the form was submitted with the repo URL. |
| R24 | DELIV | MUST | Write a technical tools report. | TD3: "Perform a technical-related tools report" | A tools report document exists in the repo, covering candidate tools per feature. |
| R25 | DELIV | MUST | Every tool suggested in the report is tested in real life, with evidence of the test. | TD3: "make sure to test (in real life) with any suggested tool" | For each suggested tool: what was run, on which input, observed result (and date). No untested tool is recommended. |
| R26 | DELIV | MUST | Write a Statement of Work (SoW) document. | TD4: "Define a SoW document" | SoW document exists (objectives, scope, deliverables, schedule, acceptance). |
| R27 | DELIV | MUST | Write a Software Requirements Specification (SRS) document. | TD5: "Define an SRS document (Software Requirements Spec)." | SRS document exists with functional and non-functional requirements, traceable to R1-R19. |
| R28 | DELIV | MUST | Define the main use cases (client stories). | TD6: "Define the main use cases (client stories)." | Use cases / user stories exist for each feature, at least for student and lecturer actors. |
| R29 | DELIV | MUST | Define the main software components. | TD7: "Define the main software components." | Component document/diagram exists with responsibilities and interfaces. |
| R30 | DELIV | MUST | Define low-level class diagrams. | TD8: "Define low-level class diagrams" | Class diagrams with attributes, methods, relations exist. |
| R31 | DELIV | MUST | Define sequence diagrams. | TD8: "and sequence diagrams" | Sequence diagrams exist at least for the main flows (attendance first). |
| R32 | DELIV | MUST | Define a testing strategy that addresses the classes/components defined in TD7. | TD9: "Define a testing strategy; make sure to address the classes (as in 7)" | Testing strategy document maps each class/component to its tests. |
| R33 | DELIV | MUST | Implement a demo KISS web application, preferably by finding and composing existing code rather than vibe coding from scratch. | TD10: "Implement(vibe code vs find and compose) a demo (KISS) web application." | The demo app runs from the repo following README instructions. |
| R34 | DEMO | MUST | Perform the demo in class. | TD11: "Perform a demo in class." | Demo performed live (date set by the course; OQ9). |
| R35 | DELIV | MUST | Conclude the assignment with a short description of the results. | TD12: "Conclude the assignment; write down a short description of the results." | A short results/conclusion section or document exists in the repo. |

### 1.4 Deadline and submission

| ID | Type | Priority | Requirement | Source | Acceptance criterion |
|---|---|---|---|---|---|
| R36 | SUBMIT | MUST | Statement deadline: 25/11/2026 ("updated in Moodle soon"). The lecturer has since extended the deadline: submission is allowed until 30/11/2026 (D16); the team aims to finish before that. | QA3: "25/11/2026 - updated in Moodle soon, see Ex2 submission link"; lecturer extension (D16) | All repo deliverables committed and submitted no later than 30/11/2026. |
| R37 | SUBMIT | MUST | The deliverables are in the submitted repository (committed, reachable from the link given in the form). | TD1, TD2 | A fresh clone of the repo contains all documents and the app. |

## 2. Grading priorities

1. **Design over implementation** — "This assignment should be addressed as a design challenge (the implementation is
   secondary" (Note). Most effort goes into TD3-TD9 (tools report, SoW, SRS, use cases, components, class and
   sequence diagrams, testing strategy).
2. **Feature 1 (attendance) is the main feature** (F1). Design it most deeply and demo it first.
3. **Reuse / compose existing code** is preferred over coding (Note, G3, TD10).
4. **Realism**: only design what can be implemented (G2), and it must work in this class in a real demo (Req1).
5. **KISS** everywhere: student smartphone web app (Req2), simple polls (F3), simple demo app (TD10).
6. **Tools tested in real life** (TD3): an untested tool in the report is a likely deduction.

## 3. Step-by-step plan (order implied by the statement)

1. TD1: create repo; README with problem + scope (R20-R22).
2. TD2: student submits repo link via the form (R23).
3. TD3: tools report with real tests of each suggested tool, using the provided files locally (R24-R25).
4. TD4-TD6: SoW, SRS, use cases (R26-R28).
5. TD7-TD8: components, class diagrams, sequence diagrams (R29-R31).
6. TD9: testing strategy per class (R32).
7. TD10: compose the KISS demo app, attendance first (R33, R1-R4), then F2-F5 per scope decision.
8. TD11: rehearse and perform the 10-minute live demo (R34, R19, R13).
9. TD12: short description of the results (R35); final commit before the submission date (R36-R37).

## 4. Pitfalls

- **Git history**: lesson from Ex1 — history must be spread out with frequent, meaningful commits (one per validated
  document/task), not one big final commit.
- **Over-design**: lesson from Ex1 and G2 — design only what is implemented or clearly implementable; no speculative
  layers, no class without a role in a use case.
- **Error messages**: lesson from Ex1 — user-facing error messages must be clear and must not expose internal
  identifiers (database IDs, stack traces, internal codes).
- **Personal data** (G1, QA6): never commit the participants list (pdf/xlsx), the class photos, the video, or the Ex1
  repo list with names. Demo with fictitious/anonymised data. Check git history, not just the working tree. The
  statement's own page 3 contains a class photo: do not copy it into the repo.
- **Secrets**: API keys only via environment variables; `.env` ignored, `.env.example` committed.
- **TD3 wording**: "test (in real life) with any suggested tool" — every tool named as suggested needs evidence of a
  real test, not just a description.
- **TD9 wording**: the testing strategy must explicitly address the classes/components from TD7, one by one.
- **TD8**: both class diagrams AND sequence diagrams; "low-level" means attributes, methods and types.
- **TD1**: problem and scope must be IN the README (not only in a separate doc).
- **TD2**: the form asks for the student's e-mail and ID; only the student fills it. The repo must be public (or
  accessible) when the link is submitted. The form links to the live Google Doc of the statement, whose Q&A may be
  newer than the PDF — re-check before submitting.
- **Deadline**: the statement says 25/11/2026 "updated in Moodle soon"; the lecturer has extended it to 30/11/2026
  (D16). Do not miss the extended date (see OQ8).
- **Demo**: 10 minutes, live, in class, on classmates' phones; the network in the room, the hosting and a fallback
  plan matter. The main feature must be shown first.
- **"Offline"** appears twice (F1 spreadsheet, F2 comments) — easy to forget.
- **F5 comparison** with other students' work is part of the feature, not optional.
- **Results description** (TD12) is a separate deliverable, easy to forget after the demo.
- **Honesty**: README should have a "Tools used" section (AI assistance disclosed).

## 5. External resources

| Resource | Purpose | Link (from PDF) | Local copy |
|---|---|---|---|
| Google Form "Ex2 - Github Submission" | TD2 submission of repo link (asks e-mail + student ID; student only) | Link in the course statement (not reproduced here) | N/A |
| QA3 "Ex2 submission link" | Deadline / submission reference | Not found as a separate URI in the PDF (only 4 unique links); presumably the same form or a Moodle link (OQ10) | N/A |
| Supplementary Drive folder | QA1-QA2: student list, class photos (and video) | Link in the course statement (not reproduced here) | Yes: `docs/supplementary/participants.pdf`, `class_photos_and_lists/*.xlsx` (2 files), 17 photos `p*.jpeg`, video `m21.mp4` — local only, personal data |
| List of assignments (Ex1 repos) | QA4: test data for F5 (homework review + comparison) | Link in the course statement (not reproduced here) | Yes: `docs/supplementary/ex1_repo_links.pdf` (local only) |
| Zoom automatic summary example | QA5: baseline for F4 video summary | Link in the course statement (not reproduced here) | Yes: `docs/supplementary/zoom_summary_example.pdf` |
| Class photo in the statement (page 3) | QA2 "see below": sample for student counting | Embedded image in the PDF | In `docs/assignment.pdf` (local only) |

## 6. Open questions (for the ambiguity detective — not decided here)

- **OQ1** Demo MVP scope: must all 5 features be implemented in the demo app, or only designed, with F1 implemented and
  others partially/stubbed? (Goal says "design", TD10 says "demo (KISS)", F1 is "main".)
- **OQ2** "Automatically" for attendance (F1): what mechanism (QR code/session code shown on the projector, geolocation,
  Wi-Fi, one-tap link)? How to prevent marking from outside the class?
  *Resolved by D30* (campus-network allow-list + rotating projector QR + 3-digit code; superseded by D33: no allow-list, 4-digit code); it replaces D5 (chain of
  trust), which was studied and rejected. No R describes the check-in mechanism itself: R1 only asks for a simple
  phone check-in, R16 for no personal data.
- **OQ3** Photo-based count (F1): count only (heads) or also identify students? Identification would conflict with G1
  (personal information). What to do when the count differs from marked attendances?
- **OQ4** Student identity without personal information (G1): anonymous token, nickname, student-chosen code, or the
  anonymised course list? What appears in the attendance spreadsheet?
- **OQ5** "Online/offline spreadsheet" (F1): online = Google Sheets or an in-app table; offline = CSV/XLSX download?
  "Offline" for comments (F2): asynchronous posting outside class, or working without network (PWA/local queue)?
- **OQ6** ML/LLM services (F4, F5): which provider (local model vs. API with key), cost, and whether sending video
  transcripts or student repos to an external API is acceptable under G1.
- **OQ7** Hosting for the live demo (Req1): public cloud host vs. laptop on the class network; tunnel; fallback plan.
- **OQ8** Deadline: statement says 25/11/2026 ("updated in Moodle soon"); extended by the lecturer to 30/11/2026
  (resolved by D16) — confirm the Moodle deadline shows the extended date.
- **OQ9** Date of the in-class demo (TD11): not stated; is it before or after the submission deadline? Does the TD12
  results description have to include the demo outcome?
- **OQ10** QA3 "see Ex2 submission link": is it the same Google Form as TD2 or a Moodle assignment? Is a Moodle upload
  also required?
- **OQ11** Format/location of the documents (single file vs. separate files; Markdown vs. PDF); diagram tool (Mermaid
  acceptable?).
- **OQ12** Tools report (TD3): "any suggested tool" — tools suggested by us, or tools suggested by the lecturer/class?
  How much test evidence (screenshots, logs) is expected?
- **OQ13** Guidelines 4-6 and Q&A 13-14 are empty in the PDF: the live Google Doc may contain newer items — check
  before final submission.
- **OQ14** Individual or team assignment? The statement does not say.
