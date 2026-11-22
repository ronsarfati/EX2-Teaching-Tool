# Tools Report (To Do 3)

Covers R24 (technical tools report) and R25 (every suggested tool is tested for real, with evidence).
It follows the validated decisions: D2 (Flask stack), D6 (nicknames), D30 (check-in on the campus network with a
projector QR and a 3-digit code), D7 (photo head count), D8 (spreadsheet), D10 (video summary), D11/D12 (LLM),
D13 (hosting), D25 (pytest). The tests below were run on 22/11 for the earlier chain-of-trust design (D5); a chain of
trust and a local Wi-Fi bubble were then studied and rejected (D30). The tested tools are the same; only the
parameters change (see 2.2).

- **Test date:** 2026-11-22. **Machine:** Apple M3 laptop, 16 GB RAM, macOS, CPU only (no GPU used).
- **Runtime:** Python 3.13.2 in a local virtualenv `.venv` (git-ignored); Node.js 24.14.1 for the JS decoder test.
- **Scripts:** every test is a small script in [`tools_tests/`](../tools_tests/). Scripts contain no personal data;
  paths to the provided files are passed as arguments. All outputs (QR images, spreadsheets, transcripts, model
  files) were written to a temporary folder outside the repository and are not committed.
- **Privacy (R16, D21):** the class photos and the video were processed locally, in memory. No photo, crop or
  derived image was saved. Only file names and numbers appear below. No transcript text is reproduced.

## 1. Summary

| # | Need (R / D) | Recommended tool | Version tested | Real test result | Verdict |
|---|---|---|---|---|---|
| 1 | Web framework (R14, D2) | Flask | 3.1.3 (Werkzeug 3.1.9) | `/ping` served, `curl` got HTTP 200 in 1.6 ms | ADOPT |
| 2 | Rotating attendance tokens: new QR every 10 s, accepted if <= 15 s old at server arrival (R1, D30) | stdlib `hmac` (+ `itsdangerous` as alternative) | Python 3.13 stdlib / itsdangerous 2.2.0 | tested with a 10 s window: fresh token accepted; tampered and 11 s old tokens rejected (real 11 s wait); window is a parameter | ADOPT stdlib `hmac` |
| 3 | QR generation (server) (R1, D30) | `qrcode` | 8.2 | 3/3 QR codes decoded back identically (OpenCV) | ADOPT |
| 4 | QR scanning on the student's phone (R1, D30) | Phone's **native camera app** (QR encodes the check-in URL; no library on the phone) | iOS / Android built-in | not testable by an agent (needs real phones, Section 3); alternative jsQR evaluated: 3/3 clean + 5/5 degraded QR decoded under Node | ADOPT native camera, phone test pending (manual); jsQR not adopted |
| 5 | Photo head count (R2, D7) | OpenCV YuNet face detector, full image, threshold 0.4 | OpenCV 5.1.0.95, model 2023mar | on 4 photos checked box by box: recall 94 %, precision 96 %, mean count error 2.5 people, < 0.1 s/photo; tiling tested and rejected | ADOPT YuNet + alert tolerance (2.5.3); YOLO rejected |
| 6 | Video transcription (R7, D10) | faster-whisper (`small` for Hebrew, `base` for speed) | 1.2.1 (CTranslate2 4.9.1) | m21.mp4: Hebrew detected (p=0.94-0.96); 150 s English test audio: WER 1.5 % (`small`), 25 s | ADOPT (pin `av<17`) |
| 7 | LLM summary / homework review (R7-R10, D12) | Anthropic Python SDK + Claude | anthropic 2.12.0 | 1 real call: 3.5 s, 107 in / 92 out tokens | ADOPT |
| 8 | Offline spreadsheet (R3, D8) | `openpyxl` (XLSX) + stdlib `csv` | 3.1.5 | XLSX and CSV written and read back identically | ADOPT |
| 9 | Public HTTPS URL for the live demo (R13, D13) | Cloudflare quick tunnel (`cloudflared`) | 2026.11.1 | public `https://<random>.trycloudflare.com/ping` returned HTTP 200 (3/3, 0.96-1.99 s) | ADOPT, plan B needed |
| 10 | Tests (R32, D25) | pytest + Flask test client | 9.2.0 | 3 passed in 0.09 s (5 runs); caught a real intermittent token bug | ADOPT |
| 11 | Campus network filter (R1, R13, D30) | stdlib `ipaddress` (CIDR match) + `CF-Connecting-IP` header behind cloudflared | Python stdlib / cloudflared 2026.11.1 | **not tested yet** (PLANNED, 2.11 and Section 3 tests 5-7) | PLANNED |

Other building blocks that need no separate test: SQLite (Python stdlib `sqlite3`, D3), short polling with
`fetch()` every 2-3 s (D4; also compatible with the quick tunnel, which does not support Server-Sent Events).

## 2. Details per capability

### 2.1 Web framework - Flask (R14, R18, D2)

| Candidate | Licence | Notes |
|---|---|---|
| **Flask** | BSD-3 | Minimal, server-rendered Jinja templates, built-in test client. Chosen in D2. |
| FastAPI | MIT | Async/JSON oriented; templates are an add-on. Not needed for a KISS server-rendered app. |
| Django | BSD-3 | Batteries included (ORM, admin, auth) but heavy for a 10-minute demo app. |

- **Command:** `.venv/bin/python tools_tests/flask_min_app.py` then `curl -s -w "\nHTTP %{http_code} in %{time_total}s\n" http://127.0.0.1:5055/ping`
- **Result:** `{"app":"tools-test","status":"ok"}` - `HTTP 200 in 0.001644s`.
- **Verdict:** ADOPT. Fallback: FastAPI.

### 2.2 Rotating signed tokens (R1, D30)

**Rule validated in D30** (first set in D5, kept): the server generates a new projector QR token every **10 s**; a
scanned token is accepted if it is **<= 15 s old when the request arrives at the server** (age measured with the
server clock only, so phone clocks do not matter). An accepted scan opens a **1-minute check-in window** during
which the student types a nickname (first visit only), then the 3-digit code shown under the QR (regenerated every
5 s), and taps "Confirm". The tests below used a **10 s** acceptance window; the window is a single constant of the same code (`TTL` in
the script, `max_age` for itsdangerous), so 15 s and the 1-minute window use the same mechanism without new code.
The 3-digit code needs no extra tool (Python stdlib); its 5 s rotation and its tolerance (current or previous code)
are to be tested with an injected clock in the app tests (D25), not in this report.

| Candidate | Licence | Notes |
|---|---|---|
| **stdlib `hmac` + `hashlib` + `time`** | PSF | No dependency; ~20 lines; full control of payload (session, creation time). |
| `itsdangerous.TimestampSigner` | BSD-3 | Already installed with Flask; `max_age` check built in. |
| PyJWT | MIT | JWT is overkill here (headers, algorithms); extra dependency. |

- **Command:** `.venv/bin/python tools_tests/token_rotation.py` (includes a real `time.sleep(11)`).
- **Result:**

  | Check | stdlib `hmac` | itsdangerous |
  |---|---|---|
  | Token length | 62 chars | 53 chars |
  | Fresh token accepted | True | True |
  | Tampered token rejected | True | True (`BadSignature`) |
  | Token rejected after 11 s (real wait) | True | True (`SignatureExpired`) |

- **Bug found by the tests:** the first version split the decoded token on the `|` separator, but the 16-byte
  binary signature itself contains a `|` byte in about 6 % of tokens, so valid tokens were randomly rejected
  (pytest failed 1 run in 8). Fix: split by the fixed signature length. A regression test now checks 2,000 tokens.
  Lesson for the app: never parse a binary signature with a separator (or use `itsdangerous`, which handles it).
- **Verdict:** ADOPT stdlib `hmac` (no dependency, explicit). Fallback: `itsdangerous` (equally tested).
  The secret key must come from an environment variable in the real app. Expiry is checked on the server only, at
  request arrival. The 15 s acceptance window (10 s rotation + 5 s margin) must cover the camera app opening the URL
  and the request reaching the server on slow Wi-Fi; typing the code and the nickname is outside this window
  (1-minute check-in window).
  To be confirmed by manual test 3 (Section 3).

### 2.3 QR code generation on the server (R1, D30)

| Candidate | Licence | Notes |
|---|---|---|
| **`qrcode` (Python)** | BSD | Generates PNG (Pillow) or SVG; simple API. |
| `segno` | BSD-3 | Pure Python, SVG-first; not tested (no need). |
| JS `qrcode` in the browser | MIT | Possible, but the token is created on the server, so server-side generation is simpler. |

- **Command:** `python tools_tests/qr_roundtrip.py <tmp_dir>` (generate with `qrcode`, decode with OpenCV `QRCodeDetector`).
- **Result:** 3 payloads (two ~105-108 char URLs with token, one 15 char code): QR version 6 (392 px) and
  version 2 (264 px); generation 4-38 ms; decoding 8-15 ms; **round-trip OK 3/3**.
- **Verdict:** ADOPT. Keep the URL + token short (about 100 chars gives QR version 6, easy to scan from a screen).

### 2.4 QR scanning on the student's phone (R1, R14, D30)

| Candidate | Licence | Maturity | Notes |
|---|---|---|---|
| **Native camera app + URL in the QR** | built into the phone | iOS camera reads QR codes since iOS 11; Android camera or Google Lens | The QR encodes the full check-in URL with the token; the camera app opens it in the default browser. **No library, no JS, no camera permission prompt in the page, no HTTPS needed for the camera.** ADOPTED. |
| jsQR | Apache-2.0 | v1.4.0, stable, no recent release | Pure JS decoder + own camera loop (`getUserMedia` + canvas, ~40 lines). Evaluated and tested, **not adopted**. |
| html5-qrcode | Apache-2.0 | v2.3.8 (2023), maintenance slowed | Ready-made camera UI; uses ZXing-js and the native BarcodeDetector when present. Larger bundle. Not adopted. |
| Native `BarcodeDetector` | browser API | Chrome Android yes, **iOS Safari no** | Would exclude iPhones. Rejected. |

**Recommended approach: native camera app.** The app has no in-page scanner. The server only has to generate QR
codes whose content is a short URL (tested in 2.3: about 100 chars gives QR version 6, decoded 3/3). The phone side
cannot be tested by an agent; it is manual tests 1-3 in Section 3. Because the camera is not used by the web page,
the **HTTPS requirement for camera access disappears**: plan B on a hotspot / LAN with plain HTTP (2.9) also works
for attendance. Note: the URL opens in the phone's **default** browser, so the nickname cookie lives there (manual
tests 1-2 check this).

**Evaluated alternative, not adopted: jsQR in the page.**

- **Command:** `NODE_PATH=<tmp>/node_modules node tools_tests/jsqr_decode.js <tmp>/qr_*.png <tmp>/deg_*.png`
  (jsQR 1.4.0 + pngjs 7.0.0 installed in a temporary folder, not in the repo). Degraded images were made with
  `python tools_tests/qr_degrade.py <tmp>/qr_0.png <tmp>` to simulate a phone camera view.
- **Result:** clean QR codes **3/3 decoded** (3-27 ms). Degraded QR (downscaled to 150 px, Gaussian blur k=5,
  15 degree rotation, low contrast, perspective skew): **5/5 decoded** by jsQR (5-41 ms) and 5/5 by OpenCV.
- html5-qrcode was installed (v2.3.8) but needs a DOM and a camera, so it was not run.
- **Why not adopted** (decoding itself works): in-page camera access needs **HTTPS** (so it fails in plan B on a
  LAN), shows a **camera permission prompt** in the browser, and adds **extra JS** (decoder + camera loop) to write,
  load and test, while the native camera app does the same job with zero code.

**Verdict:** ADOPT the native camera app + URL in the QR. A typed **3-digit code** (every 5 s) is used together
with the QR (D30): a relayed screenshot is useless because the code changes before a remote friend can type it, and
the campus-network filter means a relay must come from someone on campus (covered by the photo alert, D7). No
in-app fallback if a student cannot scan: the lecturer adds the student manually after class in the exported
spreadsheet (D30).

### 2.5 Photo head count (R2, D7)

| Candidate | Licence | Cost / size | Notes |
|---|---|---|---|
| **OpenCV YuNet** (`face_detection_yunet_2023mar.onnx`, opencv_zoo) | OpenCV Apache-2.0, model MIT | 0.23 MB model, no torch | Face detector, CPU, built into `cv2.FaceDetectorYN`. |
| Ultralytics YOLO11n / YOLOv8n (person class) | **AGPL-3.0** | 5-6 MB model + PyTorch (hundreds of MB) | Body detector; licence imposes AGPL obligations; heavy install (torch download took tens of minutes here). |
| InsightFace SCRFD (stronger face detector) | code MIT, **pretrained models non-commercial research only** | 15-300 MB model packs | **Not tested** (skipped on purpose): licence restriction, and the analysis below shows that the remaining misses are people whose face is not visible, which no face detector can find. |
| Cloud vision APIs (Google, AWS) | proprietary | paid, account | Rejected: sends class photos to a third party (R16). Not tested. |

**Input.** The provided class photos `p1.jpeg, p2.jpeg, p3.jpeg, p11-p15.jpeg, p21-p24.jpeg, p31-p34.jpeg`
(2000 x 1500 px, four lecture sessions: p1-p3, p11-p15, p21-p24, p31-p34). The folder has **16** JPEG files
(not 17), and **p15.jpeg is a byte-identical copy of p12.jpeg** (same MD5).

#### 2.5.1 Reference counts

- **Refined reference (4 photos, one per session: p1, p11, p22, p32).** For these photos the detections were drawn on
  temporary 2x zoomed crops of the back rows and inspected one by one (temporary files outside the repo, deleted
  right after review). Every person was classified as detected / missed, and every extra box as a real person /
  false positive. Uncertainty: about +/- 1 person per photo (people almost fully hidden behind others).
- **Rough reference (other 12 photos):** counted on the whole photo at reduced resolution (about +/- 3). It turned out
  to be too high: on the 4 refined photos the rough count was 1-6 people too high (p22: 46 -> 42, p32: 52 -> 46).
  The first version of this report (85 % recall) used only rough counts and **underestimated** the detector.

| Photo | Rough count | **Refined count** | Missed by YuNet (t=0.6), with reason |
|---|---|---|---|
| p1.jpeg | 40 | **39** | 7: asleep head on desk, head down (2), hand over face, standing with back turned, cut by the photo edge, almost hidden |
| p11.jpeg | 45 | **46** | 2: head down at laptop, face in shadow |
| p22.jpeg | 46 | **42** | 4: head down, hand over face, 2 almost hidden behind others |
| p32.jpeg | 52 | **46** | 3: head down (2), head resting on desk |
| **Total** | 183 | **173** | **16 missed, none of them with a clearly visible face** |

#### 2.5.2 Improvements tested (A: tiling, lower threshold, larger input; B: two photos)

- **Command:** `python tools_tests/head_count_tiled.py <yunet.onnx> <photos...>` (in-memory only, prints counts and
  runtime). Tiling: overlapping grid (20 % overlap), each tile upscaled (u2 = x2, u3 = x3), detections merged
  by score-ordered NMS (IoU > 0.3, or > 60 % of a box inside a kept box, to remove faces cut by tile borders).
- **B, two photos:** none of the provided series is a front-rows / back-rows pair. All 16 photos are wide shots of
  the whole room taken from the lectern; photos of the same session are repeats at different moments and angles.
  So two-photo counting is **SIMULATED** on single photos (`detect_two_bands`): the top 60 % of the image (back rows)
  is processed as a second, zoomed photo (upscaled x2 or x3), the bottom part at normal size. To avoid double
  counting, each face is assigned to exactly one band by the y coordinate of its centre (a rule a real two-photo
  protocol would apply with a row boundary, e.g. "photo 2 = rows 5 and above"). Limit of the simulation: an
  upscaled crop adds no real detail, unlike a real zoomed photo.

Count error (detected - refined count) on the 4 refined photos, and median runtime per photo over all 16 photos
(Apple M3 CPU):

| Configuration | p1 (39) | p11 (46) | p22 (42) | p32 (46) | Total (173) | Mean abs. error | Median runtime |
|---|---|---|---|---|---|---|---|
| Baseline: full image, threshold 0.6 | -7 | -2 | -4 | -3 | 157 (-16) | 4.0 | 73 ms |
| Full image, threshold 0.5 | -7 | -1 | -1 | -1 | 163 (-10) | 2.5 | 103 ms |
| **Full image, threshold 0.4** | -6 | 0 | -1 | +3 | 169 (-4) | 2.5 | 86 ms |
| Full image, threshold 0.3 | -4 | +1 | +2 | +6 | 178 (+5) | 3.25 | 99 ms |
| Tiles 2x2, x2, threshold 0.4 | -2 | +1 | +1 | +4 | 177 (+4) | 2.0 | 469 ms |
| Tiles 3x3, x2, threshold 0.4 | -2 | +1 | +4 | +5 | 181 (+8) | 3.0 | 505 ms |
| Tiles 3x3, x3, threshold 0.5 | -1 | +2 | -1 | +4 | 177 (+4) | 2.0 | 1,163 ms |
| Tiles 4x4, x3, threshold 0.5 | -3 | +2 | +1 | +6 | 179 (+6) | 3.0 | 1,200 ms |
| SIMULATED 2 photos, back x2, threshold 0.4 | -3 | -1 | +3 | +3 | 175 (+2) | 2.5 | 321 ms |
| SIMULATED 2 photos, back x3, threshold 0.5 | -3 | -1 | +2 | +1 | 174 (+1) | 1.75 | 631 ms |

Precision / recall checked box by box (all extra boxes inspected visually) for two configurations:

| Configuration | True detections (recall) | False positives (precision) |
|---|---|---|
| Baseline, threshold 0.6 | 157 / 173 (**90.8 %**) | 0 seen (one possible double box) (~100 %) |
| **Full image, threshold 0.4** | 163 / 173 (**94.2 %**) | 6 (96.4 %): clasped hands, a hair bun from behind, double box on a face |
| Tiles 3x3, x3, threshold 0.5 | 164 / 173 (94.8 %) | 13 (92.7 %): clasped hands (6), cup, laptop, T-shirt print, floor, double boxes; also lost 1 baseline face |

The full table for all 16 photos (12 configurations) is printed by the script. With threshold 0.4 the counts of the
other photos are: p2 42, p3 25, p12 30, p13 27, p14 43, p15 30, p21 40, p23 39, p24 36, p31 48, p33 52, p34 49.

**Findings.**
1. The real recall of the baseline is about **91 %**, not 85 %. The 16 missed people have no visible face (head down,
   asleep, hand over face, back turned, cut by the edge, hidden). Detail and resolution are not the problem.
2. Tiling and upscaling only add +1 real person over a plain threshold of 0.4, while doubling the false positives
   (mostly clasped hands) and costing 5-15 x more time. The count looks better only because false positives cancel
   misses. Not worth it.
3. The simulated two-photo variant gives the smallest count error (1.75) but is simulated, needs two shots and a
   row boundary, and its gain is within the uncertainty of the reference. A real test would need two real photos.
4. Lowering the threshold from 0.6 to 0.4 is the only cheap gain: recall 90.8 % -> 94.2 %, precision 96.4 %,
   mean absolute count error 4.0 -> 2.5 people, same speed (< 0.1 s per photo).

#### 2.5.3 Tolerance for the automatic consistency alert

The app compares N = number of attendance check-ins with D = number of faces detected on the lecturer's photo.
Measured error of the recommended configuration (full image, threshold 0.4) on the refined photos: D - true count
from **-6 to +3** (from -15 % to +7 %). The detector undercounts more than it overcounts (hidden faces), so the
tolerance is asymmetric.

- **Recommended rule:** "consistent" if `N - max(7, ceil(0.15 * N)) <= D <= N + max(4, ceil(0.10 * N))`, otherwise
  "anomaly". Example: N = 45 gives consistent for D from 38 to 50.
- **False alerts on the provided photos** (assuming N = true number present): **0 of 4** refined photos, with
  threshold 0.4 and also with the baseline 0.6 (worst case p1: -7, exactly at the limit). The safety margin is 1
  person below the worst observed error. On the other 12 photos no exact reference exists, so no false alert rate
  is claimed. As a cross-check, photos taken minutes apart in the same session differ by up to 4-5 detections
  (p21-p24: 36-41; p31-p34: 48-52), so a tighter tolerance would fire on normal variation.
- **What the alert can and cannot catch:** about 7 or more check-ins for absent people (for N about 45) trigger
  it. Fewer extra check-ins stay inside the measurement noise. This limit must be stated in the design.
- Taking the photo when students look up (e.g. "look at the camera") lowers the misses, since all measured misses
  were faces not visible.

**Verdict:** ADOPT **YuNet on the full image, score threshold 0.4** (recall 94 %, precision 96 %, < 0.1 s per photo,
0.23 MB model, permissive licence) together with the tolerance rule above. Tiling: rejected (cost and false
positives). Two photos: only if a real test with two real photos shows a gain (not possible with the provided
photos). YOLO: rejected (worse counts: 70 % at 1280 px, AGPL, torch). First comparison, kept for traceability
(rough reference, YuNet threshold 0.6 vs YOLO11n):

| Photo | Rough count | YuNet t=0.6 | YOLO11n @1280 | YOLO11n @640 |
|---|---|---|---|---|
| p1 / p2 / p3 | 40 / 44 / 28 | 32 / 38 / 23 | 26 / 29 / 24 | 10 / 15 / 12 |
| p11 / p12 / p13 / p14 / p15 | 45 / 33 / 32 / 44 / 33 | 44 / 28 / 27 / 40 / 28 | 38 / 27 / 26 / 33 / 27 | 17 / 14 / 11 / 13 / 14 |
| p21 / p22 / p23 / p24 | 46 / 46 / 46 / 46 | 40 / 38 / 36 / 35 | 36 / 31 / 35 / 24 | 14 / 13 / 12 / 13 |
| p31 / p32 / p33 / p34 | 52 / 52 / 52 / 52 | 44 / 43 / 48 / 45 | 32 / 33 / 31 / 32 | 14 / 13 / 13 / 13 |
| Total | 691 | 589 | 484 | 211 |

Command: `python tools_tests/head_count.py <yunet.onnx> <yolo11n.pt|yolov8n.pt|none> <photos...>`. YOLO11n runtime
35-38 ms @640 and 125-134 ms @1280 (first call 9.6 s with model load); YOLOv8n gave similar or lower counts.

### 2.6 Video transcription - faster-whisper (R7, R8, R15, D10)

| Candidate | Licence | Cost | Privacy | Notes |
|---|---|---|---|---|
| **faster-whisper** | MIT (models MIT) | free, local | audio stays on the laptop | CTranslate2 int8 on CPU; supports Hebrew and English. |
| openai-whisper | MIT | free, local | local | Needs PyTorch; slower on CPU. Not tested. |
| whisper.cpp | MIT | free, local | local | C++ build step; not tested. |
| Cloud speech-to-text (OpenAI, Google) | proprietary | paid, account | audio leaves the laptop | Not tested. |

- **Command:** `python tools_tests/transcribe.py <video_or_audio> <tiny|base|small> <transcript_path_outside_repo>`
  (CPU, `compute_type=int8`, `beam_size=1`, VAD filter on). The script prints statistics only.
- **Input 1:** `m21.mp4` (848x478 H.264 + AAC). **The provided video is only 5.7 s long.** Topic (neutral):
  a few words of Hebrew speech.

  | Model | Language detected (prob.) | Load time | Transcribe time | Segments / words |
  |---|---|---|---|---|
  | tiny | he (0.84) | 2.0 s | 4.5 s | 2 / 10 |
  | base | he (0.96) | 1.4 s | 1.0 s | 1 / 9 |
  | small | he (0.94) | 185 s (first run, includes ~460 MB model download), then ~1.5 s | 3.9 s | 1 / 10 |

- **Input 2 (speed and accuracy check):** a fictitious ~400-word English lecture text, synthesised to a 150 s audio
  file with macOS `say -v Samantha` (temporary file, not committed). Word error rate (WER) computed against the text.

  | Model | Language | Transcribe time | Real-time factor | WER |
  |---|---|---|---|---|
  | base | en (1.00) | 8.3 s | 0.06 | 4.5 % |
  | small | en (1.00) | 25.1 s | 0.17 | 1.5 % |

  (A first attempt with the default macOS voice, which is French on this machine, was detected as "fr": the
  language should be forced per lecture, e.g. `language="he"` or `"en"`.)
- **Issue found and fixed:** faster-whisper 1.2.1 crashes with PyAV 19 (`TypeError: open() got an unexpected keyword
  argument 'metadata_errors'`). **Pin `av<17`** (tested with av 16.1.0).
- **Estimate for a real 90-minute lecture** (from the RTF above, CPU): about 6 min with `base`, about 15 min with
  `small`, which is too long for a 10-minute demo. F4 is **deferred** (D10) and must run live, with no pre-computed
  output. The candidate is a live demo on a **short 2-3 min clip**. From the measured real-time factors, transcribing
  such a clip takes about 7-11 s with `base` (RTF 0.06) or 20-30 s with `small` (RTF 0.17), plus model loading
  (1-2 s once the model is cached) and one Claude call (3.5 s measured in 2.7).
- **Verdict:** ADOPT faster-whisper; `small` for Hebrew lectures (quality), `base` for a quick live demo.
  Hebrew accuracy could not be measured (5.7 s of speech only, no reference text). Fallback: openai-whisper.

### 2.7 LLM - Anthropic Claude via the Python SDK (R7-R11, D11, D12)

| Candidate | Licence / cost | Notes |
|---|---|---|
| **Anthropic Python SDK + Claude** | MIT SDK; paid per token | Student key available (`ANTHROPIC_API_KEY` in git-ignored `.env`). |
| OpenAI SDK + GPT | MIT SDK; paid | Would need another key. Not tested. |
| Local LLM (Ollama) | free | Large download; weaker summaries on a laptop CPU. Not tested. |

- **Command:** `ANTHROPIC_MODEL=claude-sonnet-4-5 python tools_tests/llm_call.py <text_file>` (equivalent to passing the
  model as second argument, which is how it was run; the key is read from the environment
  or `.env`, never printed). **One** real call: "summarise this lecture excerpt in 3 bullet points" on a fictitious
  4-sentence excerpt (no personal data).
- **Result:** `model=claude-sonnet-4-5-20250929 latency_s=3.5 input_tokens=107 output_tokens=92 stop=end_turn`.
- **Note:** the SDK warned that `claude-sonnet-4-5` reaches end-of-life on **2026-11-30**. The account's model list
  (API `models.list`, no generation) includes `claude-sonnet-5-5`, `claude-haiku-5-5` and `claude-opus-5-5`.
  As validated in D12, the model name comes from the env variable **`ANTHROPIC_MODEL`** (the test script does the same).
  The tested model `claude-sonnet-4-5` retires on 30/11/2026, so the default is `claude-sonnet-5-5`, which still has to
  be confirmed by a real call during coding (only one call was allowed in this test).
- **Privacy:** only transcripts and public repository code are sent; no names or photos (R16).
- **Verdict:** ADOPT. No pre-computed outputs (D1). F5 (homework review) runs live; if the key is missing or the API
  call fails, the app shows a plain "LLM service unavailable" message (D12, D23) and F1-F3 keep working.

### 2.8 Spreadsheet export (R3, D8)

| Candidate | Licence | Notes |
|---|---|---|
| **stdlib `csv`** | PSF | Opens in Excel, LibreOffice and Google Sheets; zero dependency. |
| **`openpyxl`** | MIT | Real `.xlsx` (frozen header row, sheet name). |
| pandas | BSD-3 | Heavy for a 4-column table. |
| Google Sheets API | proprietary | Needs an account and OAuth; data leaves the app. Rejected. |

- **Command:** `python tools_tests/xlsx_roundtrip.py <tmp_dir>` (fictitious nicknames only).
- **Result:** XLSX 5,019 bytes, 4 rows read back, `identical: True`; CSV `identical: True`.
- **Verdict:** ADOPT both: live HTML table online, CSV + XLSX download for offline use.

### 2.9 Public HTTPS URL for the live demo (R13, D13)

| Candidate | Account | Notes |
|---|---|---|
| **Cloudflare quick tunnel** (`cloudflared`) | none | Public HTTPS URL reachable from any network; random hostname each run. |
| ngrok | free account + token | Similar; interstitial page on the free plan. Not tested. |
| Free PaaS (Render, PythonAnywhere) | account | Deploy step; cold starts; local ML models are heavy. Not tested. |
| Laptop hotspot / LAN | none | Plain HTTP, phones must join the same network. Fine for attendance because scanning uses the native camera app (2.4). |

- **Command:** `cloudflared tunnel --no-autoupdate --url http://127.0.0.1:5055` then `curl <public URL>/ping` (3 times).
- **Result:** cloudflared 2026.11.1 (Homebrew); URL `https://<random>.trycloudflare.com` printed after ~8 s;
  connection registered (edge location fra19, QUIC); **3/3 requests HTTP 200** with the Flask JSON, 0.96-1.99 s each.
  Tunnel stopped after ~25 s.
- **Documented limits** (Cloudflare docs): no uptime guarantee, **200 in-flight requests max** (enough for one class
  with 2-3 s polling), no Server-Sent Events (polling is fine), hostname changes at each start.
- **Verdict:** ADOPT. Plan B (D13): phone hotspot + LAN URL over plain HTTP. Since the app has no in-page scanner
  (2.4), the missing HTTPS does not block attendance: the native camera app opens the `http://<laptop-ip>:<port>/...`
  URL encoded in the QR. Still to confirm on real phones (Section 3, test 9). With the D30 filter, the LAN / hotspot
  range must be added to the campus allow-list in plan B. Plan C: recorded run (D13).

### 2.10 Testing (R32, D25)

- **Command:** `.venv/bin/python -m pytest -q tools_tests/test_smoke.py -p no:cacheprovider`
- **Result:** first version `1 failed, 1 passed` intermittently (1 run in 8), which revealed the token parsing bug
  described in 2.2. After the fix: `3 passed in 0.09s` on 5 consecutive runs (Flask test client on `/ping`; token
  accepted at +5 s and rejected at +11 s with injected time; 2,000 random-key tokens verified).
- **Verdict:** ADOPT pytest 9.2.0 + Flask test client. Inject time into the token code to test expiry without sleeping.

### 2.11 Campus network filter (R1, R13, D30) - PLANNED, not tested yet

| Candidate | Licence | Notes |
|---|---|---|
| **stdlib `ipaddress`** (`ip_address(x) in ip_network(cidr)`) | PSF | IPv4 and IPv6 CIDR matching, no dependency. |
| **`CF-Connecting-IP` header** set by Cloudflare | built into the tunnel | Carries the phone's address through the quick tunnel; trusted only when the socket peer is localhost (D30). In plan B the socket address is used directly. |

No result is reported yet. The checks to run are manual tests 5-7 in Section 3 (address seen from a phone on the
campus Wi-Fi vs on 4G/5G, IPv6 case, measurement of the campus public IP on 23/11); the CIDR matching and the
header rule will also be unit-tested with an injected client IP (D25).

## 3. Manual tests still to do by the student

These need a real phone, a camera or the classroom, so they could not be run by an agent.

1. **iPhone native camera opens the QR URL:** start the app and the tunnel, point the iPhone's Camera app at the
   projector QR, tap the link banner. Check that the check-in page opens in the default browser, the numeric
   keypad appears for the 3-digit code, the nickname is asked on the first visit only (cookie kept on the second
   scan), and the check-in is recorded.
2. **Android native camera / Google Lens opens the QR URL:** same test on an Android phone (built-in camera app,
   and Google Lens if the camera app has no QR reader).
3. **Time from scan to check-in on slow Wi-Fi:** on the campus Wi-Fi (or a throttled hotspot), measure the time
   from pointing the camera to the server accepting the token (must be < 15 s from QR generation) and then to the
   recorded check-in (code typed within the 1-minute window). Also check that a QR photographed and opened later
   than 15 s is refused.
4. **Classroom network:** check that the university Wi-Fi does not block `*.trycloudflare.com` (open the URL from a
   phone on the campus network once before the demo).
5. **PLANNED - client IP seen through the tunnel (D30):** with the app behind cloudflared, log the
   `CF-Connecting-IP` value for a request from a phone on the campus Wi-Fi, then from the same phone on 4G/5G.
   Expected: the campus address is inside the allow-list and accepted; the 4G/5G address is refused with the
   off-campus message.
6. **PLANNED - IPv6 case (D30):** check whether a phone on the campus Wi-Fi (and on 4G/5G) reaches the tunnel over
   IPv6; if so, note the IPv6 prefix and check that an IPv6 range in the allow-list matches it.
7. **PLANNED - campus public IP measurement (23/11, D30):** on site, record the public IPv4/IPv6 address(es) of the
   campus Wi-Fi seen by the server (from several places in the building if possible) and enter the range(s) in the
   allow-list (only network ranges are kept, D21).
8. **Head count on a fresh photo** taken with the lecturer's phone in the actual room (count only, photo not stored).
9. **Plan B without HTTPS (hotspot / LAN):** repeat test 1 with an `http://<laptop-ip>` URL in the QR (iPhone and
   Android), with the LAN range in the allow-list, and check that the camera app opens plain-HTTP links without
   blocking.
10. **Longer lecture recording:** the provided `m21.mp4` is 5.7 s, which is too short to judge the summary against
    the Zoom example (R8). If a longer recording is available, run `tools_tests/transcribe.py` on it with `small`
    and `language` set, then the LLM summary.

## 4. Reproduce

```
python3.13 -m venv .venv
.venv/bin/pip install flask itsdangerous "qrcode[pil]" opencv-python-headless openpyxl pytest anthropic faster-whisper "av<17"
.venv/bin/pip install ultralytics   # only to reproduce the YOLO comparison (pulls PyTorch)
# YuNet model: https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
# Node decoder test: npm install jsqr pngjs (in a temporary folder), then NODE_PATH=<folder>/node_modules
brew install cloudflared
```
Model files (`*.onnx`, `*.pt`) and the `.env` file are git-ignored; keep them outside the repository or in a
git-ignored folder.
