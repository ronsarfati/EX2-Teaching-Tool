# Tools Report (To Do 3)

Covers R24 (technical tools report) and R25 (every suggested tool is tested for real, with evidence).
It follows the validated decisions: D2 (Flask stack), D5/D6 (QR chain-of-trust attendance, nicknames),
D7 (photo head count), D8 (spreadsheet), D10 (video summary), D11/D12 (LLM), D13 (hosting), D25 (pytest).

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
| 2 | 10 s rotating attendance tokens (R1, D5) | stdlib `hmac` (+ `itsdangerous` as alternative) | Python 3.13 stdlib / itsdangerous 2.2.0 | fresh token accepted; tampered and 11 s old tokens rejected (real 11 s wait) | ADOPT stdlib `hmac` |
| 3 | QR generation (server) (R1, D5) | `qrcode` | 8.2 | 3/3 QR codes decoded back identically (OpenCV) | ADOPT |
| 4 | QR scanning in the phone browser (R1, D5) | jsQR (+ own `getUserMedia` loop) | 1.4.0 | 3/3 clean + 5/5 degraded QR images decoded under Node | ADOPT, phone test pending (manual) |
| 5 | Photo head count (R2, D7) | OpenCV YuNet face detector | OpenCV 5.1.0.95, model 2023mar | 589 faces found vs ~691 people (85 %), mean error 6.4 people/photo, ~50-170 ms/photo | ADOPT YuNet; YOLO rejected |
| 6 | Video transcription (R7, D10) | faster-whisper (`small` for Hebrew, `base` for speed) | 1.2.1 (CTranslate2 4.9.1) | m21.mp4: Hebrew detected (p=0.94-0.96); 150 s English test audio: WER 1.5 % (`small`), 25 s | ADOPT (pin `av<17`) |
| 7 | LLM summary / homework review (R7-R10, D12) | Anthropic Python SDK + Claude | anthropic 2.12.0 | 1 real call: 3.5 s, 107 in / 92 out tokens | ADOPT |
| 8 | Offline spreadsheet (R3, D8) | `openpyxl` (XLSX) + stdlib `csv` | 3.1.5 | XLSX and CSV written and read back identically | ADOPT |
| 9 | Public HTTPS URL for the live demo (R13, D13) | Cloudflare quick tunnel (`cloudflared`) | 2026.11.1 | public `https://<random>.trycloudflare.com/ping` returned HTTP 200 (3/3, 0.96-1.99 s) | ADOPT, plan B needed |
| 10 | Tests (R32, D25) | pytest + Flask test client | 9.2.0 | 3 passed in 0.09 s (5 runs); caught a real intermittent token bug | ADOPT |

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

### 2.2 Rotating signed tokens, 10 s validity (R1, D5)

| Candidate | Licence | Notes |
|---|---|---|
| **stdlib `hmac` + `hashlib` + `time`** | PSF | No dependency; ~20 lines; full control of payload (session, sponsor). |
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
  The secret key must come from an environment variable in the real app. Expiry is checked on the server only;
  the 10 s window must tolerate the time a student needs to scan (to be confirmed in the manual phone test).

### 2.3 QR code generation on the server (R1, D5)

| Candidate | Licence | Notes |
|---|---|---|
| **`qrcode` (Python)** | BSD | Generates PNG (Pillow) or SVG; simple API. |
| `segno` | BSD-3 | Pure Python, SVG-first; not tested (no need). |
| JS `qrcode` in the browser | MIT | Possible, but the token is created on the server, so server-side generation is simpler. |

- **Command:** `python tools_tests/qr_roundtrip.py <tmp_dir>` (generate with `qrcode`, decode with OpenCV `QRCodeDetector`).
- **Result:** 3 payloads (two ~105-108 char URLs with token, one 15 char code): QR version 6 (392 px) and
  version 2 (264 px); generation 4-38 ms; decoding 8-15 ms; **round-trip OK 3/3**.
- **Verdict:** ADOPT. Keep the URL + token short (about 100 chars gives QR version 6, easy to scan from a screen).

### 2.4 QR scanning in the student's phone browser (R1, R14, D5)

| Candidate | Licence | Maturity | Notes |
|---|---|---|---|
| **jsQR** | Apache-2.0 | v1.4.0, stable, no recent release | Pure JS decoder; we write the camera loop (`getUserMedia` + canvas, ~40 lines). Works on iOS Safari and Android Chrome (no native API needed). |
| html5-qrcode | Apache-2.0 | v2.3.8 (2023), maintenance slowed | Ready-made camera UI; uses ZXing-js and the native BarcodeDetector when present. Larger bundle. |
| Native `BarcodeDetector` | browser API | Chrome Android yes, **iOS Safari no** | Zero dependency but would exclude iPhones. Rejected as the only solution. |

- **Command:** `NODE_PATH=<tmp>/node_modules node tools_tests/jsqr_decode.js <tmp>/qr_*.png <tmp>/deg_*.png`
  (jsQR 1.4.0 + pngjs 7.0.0 installed in a temporary folder, not in the repo). Degraded images were made with
  `python tools_tests/qr_degrade.py <tmp>/qr_0.png <tmp>` to simulate a phone camera view.
- **Result:** clean QR codes **3/3 decoded** (3-27 ms). Degraded QR (downscaled to 150 px, Gaussian blur k=5,
  15 degree rotation, low contrast, perspective skew): **5/5 decoded** by jsQR (5-41 ms) and 5/5 by OpenCV.
- **Not tested here:** live camera access in a phone browser. It needs HTTPS (provided by the tunnel) and a
  real phone - see Section 3. html5-qrcode was installed (v2.3.8) but needs a DOM and a camera, so it was not run.
- **Verdict:** ADOPT jsQR with our own small camera loop. Fallback: html5-qrcode. Recommended design fallback:
  show a short text code under every QR so a student can type it if the camera fails.

### 2.5 Photo head count (R2, D7)

| Candidate | Licence | Cost / size | Notes |
|---|---|---|---|
| **OpenCV YuNet** (`face_detection_yunet_2023mar.onnx`, opencv_zoo) | OpenCV Apache-2.0, model MIT | 0.23 MB model, no torch | Face detector, CPU, built into `cv2.FaceDetectorYN`. |
| Ultralytics YOLO11n / YOLOv8n (person class) | **AGPL-3.0** | 5-6 MB model + PyTorch (hundreds of MB) | Body detector; licence imposes AGPL obligations; heavy install (torch download took tens of minutes here). |
| Cloud vision APIs (Google, AWS) | proprietary | paid, account | Rejected: sends class photos to a third party (R16). Not tested. |

- **Input:** the provided class photos `p1.jpeg, p2.jpeg, p3.jpeg, p11-p15.jpeg, p21-p24.jpeg, p31-p34.jpeg`
  (2000 x 1500 px). The folder has **16** JPEG files (not 17), and **p15.jpeg is a byte-identical copy of p12.jpeg**
  (same MD5), so there are 15 distinct photos.
- **Manual reference:** counted by looking at each photo (reduced resolution). Back rows are small and partly
  hidden, so the reference is **approximate (about +/- 3 people)**.
- **Command:** `python tools_tests/head_count.py <yunet.onnx> <yolo11n.pt|yolov8n.pt|none> <photos...>`
  (YuNet: score threshold 0.6, NMS 0.3; YOLO: class person, conf 0.25, image size 640 and 1280).
- **Result** (error = detected - manual; runtimes are per photo, after model warm-up):

  | Photo | Manual (approx.) | YuNet | YuNet error | YOLO11n @1280 | YOLO11n error | YOLO11n @640 |
  |---|---|---|---|---|---|---|
  | p1.jpeg | 40 | 32 | -8 | 26 | -14 | 10 |
  | p2.jpeg | 44 | 38 | -6 | 29 | -15 | 15 |
  | p3.jpeg | 28 | 23 | -5 | 24 | -4 | 12 |
  | p11.jpeg | 45 | 44 | -1 | 38 | -7 | 17 |
  | p12.jpeg | 33 | 28 | -5 | 27 | -6 | 14 |
  | p13.jpeg | 32 | 27 | -5 | 26 | -6 | 11 |
  | p14.jpeg | 44 | 40 | -4 | 33 | -11 | 13 |
  | p15.jpeg (= p12) | 33 | 28 | -5 | 27 | -6 | 14 |
  | p21.jpeg | 46 | 40 | -6 | 36 | -10 | 14 |
  | p22.jpeg | 46 | 38 | -8 | 31 | -15 | 13 |
  | p23.jpeg | 46 | 36 | -10 | 35 | -11 | 12 |
  | p24.jpeg | 46 | 35 | -11 | 24 | -22 | 13 |
  | p31.jpeg | 52 | 44 | -8 | 32 | -20 | 14 |
  | p32.jpeg | 52 | 43 | -9 | 33 | -19 | 13 |
  | p33.jpeg | 52 | 48 | -4 | 31 | -21 | 13 |
  | p34.jpeg | 52 | 45 | -7 | 32 | -20 | 13 |
  | **Total / mean abs. error** | **691** | **589 (85 %)** | **6.4** | **484 (70 %)** | **12.9** | 211 (31 %), 30.0 |

  - Runtime: YuNet 48-129 ms/photo (OpenCV-only venv) and ~170 ms/photo (venv with torch loaded);
    YOLO11n 35-38 ms @640 and 125-134 ms @1280 (first call 9.6 s including model load).
    YOLOv8n gave similar or lower counts (12-14 @640, 22-32 @1280).
  - YuNet parameter sweep (upscale x1.5 / x2, threshold 0.5): at most +3 faces on a photo, 3-6 x slower. Not worth it.
  - Main error source for both: students looking down at laptops, partly hidden faces/bodies in back rows.
- **Verdict:** ADOPT **YuNet** (closest to the manual count on 15 of 16 photos, tiny, permissive licence, no torch).
  Show the number as an **estimate** ("about N faces seen") next to the number of attendance marks, since it
  undercounts by about 15 % on these photos. Fallback: YOLO11n @1280 (only if AGPL and torch are acceptable).

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
  `small`. So the demo must use a **pre-computed** transcript/summary as planned in D10, with a live run on a short clip.
- **Verdict:** ADOPT faster-whisper; `small` for Hebrew lectures (quality), `base` for a quick live demo.
  Hebrew accuracy could not be measured (5.7 s of speech only, no reference text). Fallback: openai-whisper.

### 2.7 LLM - Anthropic Claude via the Python SDK (R7-R11, D11, D12)

| Candidate | Licence / cost | Notes |
|---|---|---|
| **Anthropic Python SDK + Claude** | MIT SDK; paid per token | Student key available (`ANTHROPIC_API_KEY` in git-ignored `.env`). |
| OpenAI SDK + GPT | MIT SDK; paid | Would need another key. Not tested. |
| Local LLM (Ollama) | free | Large download; weaker summaries on a laptop CPU. Not tested. |

- **Command:** `python tools_tests/llm_call.py <text_file> claude-sonnet-4-5` (the key is read from the environment
  or `.env`, never printed). **One** real call: "summarise this lecture excerpt in 3 bullet points" on a fictitious
  4-sentence excerpt (no personal data).
- **Result:** `model=claude-sonnet-4-5-20250929 latency_s=3.5 input_tokens=107 output_tokens=92 stop=end_turn`.
- **Note:** the SDK warned that `claude-sonnet-4-5` reaches end-of-life on **2026-11-30**. The account's model list
  (API `models.list`, no generation) includes `claude-sonnet-5-5`, `claude-haiku-5-5` and `claude-opus-5-5`.
  The script default is now `claude-sonnet-5-5`; the app should read the model name from an env variable.
- **Privacy:** only transcripts and public repository code are sent; no names or photos (R16).
- **Verdict:** ADOPT. Fallback: pre-computed outputs (D10, D11) if the network or the key fails during the demo.

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
| **Cloudflare quick tunnel** (`cloudflared`) | none | HTTPS (needed for phone camera access); random hostname each run. |
| ngrok | free account + token | Similar; interstitial page on the free plan. Not tested. |
| Free PaaS (Render, PythonAnywhere) | account | Deploy step; cold starts; local ML models are heavy. Not tested. |
| Laptop hotspot / LAN | none | Plain HTTP: phone browsers block the camera without HTTPS. |

- **Command:** `cloudflared tunnel --no-autoupdate --url http://127.0.0.1:5055` then `curl <public URL>/ping` (3 times).
- **Result:** cloudflared 2026.11.1 (Homebrew); URL `https://<random>.trycloudflare.com` printed after ~8 s;
  connection registered (edge location fra19, QUIC); **3/3 requests HTTP 200** with the Flask JSON, 0.96-1.99 s each.
  Tunnel stopped after ~25 s.
- **Documented limits** (Cloudflare docs): no uptime guarantee, **200 in-flight requests max** (enough for one class
  with 2-3 s polling), no Server-Sent Events (polling is fine), hostname changes at each start.
- **Verdict:** ADOPT. Plan B: phone hotspot + LAN IP (QR scan replaced by typed code, since there is no HTTPS);
  plan C: recorded run (D13).

### 2.10 Testing (R32, D25)

- **Command:** `.venv/bin/python -m pytest -q tools_tests/test_smoke.py -p no:cacheprovider`
- **Result:** first version `1 failed, 1 passed` intermittently (1 run in 8), which revealed the token parsing bug
  described in 2.2. After the fix: `3 passed in 0.09s` on 5 consecutive runs (Flask test client on `/ping`; token
  accepted at +5 s and rejected at +11 s with injected time; 2,000 random-key tokens verified).
- **Verdict:** ADOPT pytest 9.2.0 + Flask test client. Inject time into the token code to test expiry without sleeping.

## 3. Manual tests still to do by the student

These need a real phone, a camera or the classroom, so they could not be run by an agent.

1. **iPhone (Safari) camera scan over HTTPS:** start the app and the tunnel, open the tunnel URL on an iPhone,
   allow camera access, scan the lecturer QR shown on the laptop screen. Check that the permission prompt appears
   and the QR is decoded within the 10 s token window.
2. **Android (Chrome) camera scan:** same test on an Android phone.
3. **Phone-to-phone scan:** phone A shows its sponsor QR, phone B scans it (screen brightness at maximum).
   Measure the time from opening the page to "marked", and check that a QR older than 10 s is refused.
4. **Classroom network:** check that the university Wi-Fi does not block `*.trycloudflare.com` (open the URL from a
   phone on the campus network once before the demo).
5. **Head count on a fresh photo** taken with the lecturer's phone in the actual room (count only, photo not stored).
6. **Longer lecture recording:** the provided `m21.mp4` is 5.7 s, which is too short to judge the summary against the
   Zoom example (R8). If a longer recording is available, run `tools_tests/transcribe.py` on it with `small` and
   `language` set, then the LLM summary.

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
