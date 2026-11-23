# Live demo script (To Do 11) - 10 minutes

Goal: show the main feature (F1 attendance) working with the real class on their own phones, then F3, F2 and F5,
in 10 minutes. Items marked **(pending)** depend on a choice not yet made.

Roles: **Presenter** = lecturer-side laptop (projected). **Classmates** = phones. **Helper** (optional) = takes the
class photo and watches the clock.

## 1. Setup checklist (before class, 20 min before)

Run once on the demo laptop, from the repository root (`python -m app` loads `.env` itself; variables already set in the environment win).

1. Environment: copy `.env.example` to `.env`, set a long random `SECRET_KEY`, a `LECTURER_PIN`, and `BASE_URL`
   (the public tunnel URL, or `http://<laptop IP>:<port>` for the hotspot plan B). Optional: `ANTHROPIC_API_KEY` (F5).
2. Demo data (optional, fictional only): `python scripts/seed_demo.py instance/app.db --force`
   fills 3 past sessions, a closed poll, a few comments and fake peer URLs so the export looks populated.
   **(pending)** Seeded or empty database for the live class: decide with the lecturer; with a seeded database the
   figures to report are those of the last (live) session only.
3. YuNet model present at `YUNET_MODEL_PATH` (default `models/face_detection_yunet_2023mar.onnx`); check:
   `ls models/`. Prepare a **class photo** on the laptop (taken in the room, shown only live, never committed).
4. Start the app: `python -m app` (port 5000, or `PORT`; **on a Mac use `PORT=5050`**, AirPlay takes 5000, and set `BASE_URL`
   and the commands below with 5050). Check `http://127.0.0.1:<port>/ping` answers `ok`.
5. Tunnel (plan A): `cloudflared tunnel --no-autoupdate --url http://127.0.0.1:<port>`; copy the printed
   `https://<random>.trycloudflare.com` into `BASE_URL`, then **restart the app**. The URL changes at every run
   (phones then treat themselves as first-time visitors, D31/OI-4).
6. Lecturer login: open `/lecturer/login` and enter the PIN.
7. Projector: on the laptop (logged in), open `/lecturer/projector` full-screen on the projector. Open a second browser tab on
   `/lecturer` (dashboard) for yourself. Leave **no session open** yet.
8. Quick test with your own phone: scan, confirm, then check the row appears, then reset
   (`--force` re-seed) or close the session. Do not leave test rows if the figures are to be reported.
9. Have the plan C material ready: the recorded rehearsal video and screenshots (**pending**: record at rehearsal).

## 2. Timeline

| Time | Who | Action | Audience sees |
|---|---|---|---|
| 0:00-0:45 | Presenter | One-sentence problem; "five features, one phone browser, no install, nicknames only, no personal data". | Slide or lecturer dashboard |
| 0:45-1:15 | Presenter | Dashboard: click **Open session** (PIN already entered). Page jumps to the projector. | Rotating QR (10 s) and a 4-digit code (5 s) |
| 1:15-3:45 | Classmates | Scan the QR with the **native camera**, tap the link, type a nickname (first time), type the 4-digit code, **Confirm**. | Phones show "You are checked in" |
| 1:15-3:45 | Presenter | Switch to the dashboard tab and watch N rise; note the time when N stops rising (this is the measured check-in duration, NFR-6). Count the refusals told by students (wrong code, expired QR). | Live table: nickname + time, N counter |
| 3:45-5:00 | Helper + Presenter | Helper takes a photo of the room; Presenter uploads it in **Count heads on a class photo**. | "Checked in N / detected D / consistent or anomaly" |
| 5:00-5:30 | Presenter | Say: the photo is counted then discarded, only D is kept (D7). If anomaly: say it is an alert, not an accusation. Click **Close session**. | Result page, then QR disappears |
| 5:30-6:00 | Presenter | Dashboard: **Download XLSX**; open it. | Sheets "Check-ins" and "Summary" (past sessions if seeded) |
| 6:00-7:30 | Presenter + classmates | **Polls**: create "Which topic next?" with 2-3 options; classmates open the menu page of the app, tap **Poll**, vote; watch the bars rise, then **Close**. | Live counts, closed poll |
| 7:30-8:30 | Classmates + Presenter | Classmates open **Comments** and post a suggestion; Presenter opens `/lecturer/comments`; comments appear within a few seconds. | Newest comments first, no names |
| 8:30-9:30 | Presenter | **F5 Homework review**: with a key, paste one public repository URL **(pending: which repository)** and show the review with anonymised "Submission B/C" comparison. Without a key, submit anyway and show the clear message "The review service is unavailable right now. Please try again later." | Review text and metrics, or the unavailable message |
| 9:30-10:00 | Presenter | Wrap-up: what was measured today (N, D, duration), F4 video summary **(pending: deferred, state its status)**, known limits (section 4). | Dashboard |

If time runs short, cut in this order: F5, comments, poll. Never cut check-in, photo count or export.

## 3. Plan B for each risk

| Risk | Detect | Plan B |
|---|---|---|
| No Wi-Fi in the room | Phones cannot load the page | Phones on mobile data still work if the tunnel is up (the check-in does not depend on the network, D33). Otherwise use the plan C video and screenshots, show the pages from the laptop browser only. |
| Tunnel down or URL not reachable | `cloudflared` exits, phones time out | Restart `cloudflared`, update `BASE_URL`, restart the app (1 min). If still down: plan B phone hotspot with `BASE_URL=http://<laptop IP>:<port>`. |
| Code typed wrongly by many students | Many "Wrong code" messages | Remind them to type the code shown now (the current or previous one is accepted); after 5 attempts they scan again (D30, D33). |
| YuNet model missing or corrupt | Upload shows "Head count is not available right now." | Show the message as the designed behaviour; continue; show the recorded photo-count screenshot (plan C) and give D from the rehearsal. Check `ls models/` during setup. |
| No API key | F5 shows the unavailable message | Show the message (designed behaviour, 503); explain the key is an environment variable; show a rehearsal screenshot of a real review. |
| LLM slow (> 30 s) | Spinner / no answer | Do F5 last; if no answer after 30 s, switch to the screenshot of the rehearsal review and move on. The call times out after 60 s with the same message. |
| Student phone cannot scan | One student blocked | Nothing in the app (by design, D30): the lecturer adds the student by hand in the exported spreadsheet after class. |
| App crashes or laptop freezes | Page unreachable | Restart `python -m app` (data persists in SQLite); worst case plan C video. |
| QR too small / unreadable on projector | Students cannot scan | Zoom the browser (Ctrl +) on the projector page. |

## 4. What to say about known residual risks (neutral wording)

- The check-in proves "a device scanned the projector QR and typed the code shown in the room", not that a person is
  physically present (D33). A remote student with a live accomplice relaying the QR and the code can check in. The
  rotating QR (10 s), the 4-digit code (5 s), the 1-minute window, 5 attempts, one check-in per device and the photo
  head count alert reduce this; they do not remove it. Guessing the code by rescanning needs about 5,000 tries on average.
- The identity is a nickname and a random device token in a cookie: clearing cookies or using a private tab gives a
  new device, and nicknames are not verified or unique.
- The head count is an estimate (about 94 % recall and 96 % precision on the test photos, tools report); the alert
  has a tolerance and is meant to prompt a look, not to decide.
- The homework review page has no PIN in the demo (decision D31/OI-10); the cost is limited by the account limit.
- Real-time is short polling every 1-3 s, not push; "offline" means a downloadable spreadsheet and comments posted
  later, not an offline-first app.
- The quick-tunnel address changes at each run, so phones may ask for the nickname again.
- F4 (video summary) status: **(pending)**.
