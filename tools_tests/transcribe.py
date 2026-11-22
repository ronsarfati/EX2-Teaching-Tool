"""Transcribe a lecture video with faster-whisper; print stats only (never the transcript).

Run:  python tools_tests/transcribe.py <video.mp4> <model_size> <transcript_out_path_outside_repo>
"""
import sys
import time

from faster_whisper import WhisperModel


def main(video, size, out_path):
    t0 = time.perf_counter()
    model = WhisperModel(size, device="cpu", compute_type="int8")
    t1 = time.perf_counter()
    segments, info = model.transcribe(video, beam_size=1, vad_filter=True)
    text = []
    n = 0
    for seg in segments:
        text.append(seg.text.strip())
        n += 1
    t2 = time.perf_counter()
    full = " ".join(text)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(full)
    print(f"model={size} load_s={t1-t0:.1f} language={info.language} p={info.language_probability:.2f} "
          f"audio_s={info.duration:.1f} transcribe_s={t2-t1:.1f} rtf={(t2-t1)/max(info.duration,1e-9):.2f} "
          f"segments={n} words={len(full.split())}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
