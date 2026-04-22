#!/usr/bin/env python3
"""
WAV/MP3 Dead Air Restorer — Python 3.14+
Dependencies: numpy, soundfile

Accepts cleaned WAV or MP3 as input.
MP3 is converted to WAV internally before processing.
Output is always WAV (same format as play_audio.py).
"""

import sys
import os
import json
import wave
import struct


# ──────────────────────────────────────────────
# DEPENDENCIES
# ──────────────────────────────────────────────
def check_dependencies():
    missing = []
    for pkg in ("numpy", "soundfile"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"ERROR: Missing: {', '.join(missing)}")
        print(f"Run:  pip install {' '.join(missing)}")
        sys.exit(1)
    print("  ✅ numpy ready")
    print("  ✅ soundfile ready")


# ──────────────────────────────────────────────
# MP3 → WAV CONVERSION
# ──────────────────────────────────────────────
def mp3_to_wav(mp3_path: str) -> str:
    """
    Convert an MP3 file to a temporary WAV file.
    Tries three methods in order:
      1. audioop-free pydub workaround via ffmpeg subprocess
      2. Direct ffmpeg subprocess call (no Python lib needed)
      3. Raises a clear error if neither works
    Returns the path to the temporary WAV file.
    """
    import tempfile
    import subprocess
    import shutil

    tmp_wav = tempfile.mktemp(suffix="_restored_input.wav")

    print(f"  Converting MP3 → WAV (temporary)...")

    # Method 1: ffmpeg via subprocess (most reliable on Python 3.14)
    if shutil.which("ffmpeg"):
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, tmp_wav],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0 and os.path.exists(tmp_wav):
            print(f"  ✅ MP3 converted via ffmpeg")
            return tmp_wav

    # Method 2: static-ffmpeg (auto-downloads ffmpeg binary)
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        if shutil.which("ffmpeg"):
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, tmp_wav],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0 and os.path.exists(tmp_wav):
                print(f"  ✅ MP3 converted via static-ffmpeg")
                return tmp_wav
    except ImportError:
        pass

    # Nothing worked
    print("\n  ┌─────────────────────────────────────────────────┐")
    print("  │  MP3 conversion requires ffmpeg.                │")
    print("  │                                                 │")
    print("  │  Option A — install static-ffmpeg (easiest):   │")
    print("  │    pip install static-ffmpeg                    │")
    print("  │                                                 │")
    print("  │  Option B — install ffmpeg system-wide:        │")
    print("  │    1. Download from https://www.gyan.dev/ffmpeg │")
    print("  │    2. Extract to C:\\ffmpeg                      │")
    print("  │    3. Add C:\\ffmpeg\\bin to System PATH          │")
    print("  └─────────────────────────────────────────────────┘")
    sys.exit(1)


# ──────────────────────────────────────────────
# FILE PICKERS
# ──────────────────────────────────────────────
def pick_file(title: str, filetypes: list) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    return path


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")

def ts_to_sec(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(".")
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

def open_folder(path: str):
    import platform
    system = platform.system()
    if system == "Windows":
        os.system(f'explorer /select,"{path}"')
    elif system == "Darwin":
        os.system(f'open -R "{path}"')
    else:
        os.system(f'xdg-open "{os.path.dirname(os.path.abspath(path))}"')


# ──────────────────────────────────────────────
# RESTORE CORE
# ──────────────────────────────────────────────
def restore(input_audio: str, report_json: str) -> str:
    import numpy as np
    import soundfile as sf

    print(f"\n{'='*55}")

    # ── Handle MP3 input ──────────────────────
    ext = os.path.splitext(input_audio)[1].lower()
    tmp_wav_path = None

    if ext == ".mp3":
        print(f"  Input format   : MP3 — converting to WAV first")
        tmp_wav_path = mp3_to_wav(input_audio)
        wav_to_read  = tmp_wav_path
    elif ext == ".wav":
        print(f"  Input format   : WAV — loading directly")
        wav_to_read  = input_audio
    else:
        print(f"  ERROR: Unsupported format '{ext}'. Use WAV or MP3.")
        sys.exit(1)

    # ── Load JSON ─────────────────────────────
    print(f"  Reading report : {os.path.basename(report_json)}")
    with open(report_json, "r", encoding="utf-8") as f:
        report = json.load(f)

    sample_rate    = report["sample_rate_hz"]
    original_dur_s = ts_to_sec(report["original_duration"])
    segments       = sorted(report["removed_segments"], key=lambda x: x["start_sec"])

    print(f"  Original duration  : {fmt(original_dur_s)}  ({original_dur_s:.3f}s)")
    print(f"  Silence blocks     : {len(segments)}")

    # ── Load audio ────────────────────────────
    print(f"  Reading audio  : {os.path.basename(input_audio)}")
    cleaned, file_sr = sf.read(wav_to_read, dtype="float32")

    if file_sr != sample_rate:
        print(f"  ⚠️  Sample rate mismatch — using file rate ({file_sr} Hz)")
        sample_rate = file_sr

    cleaned_dur_s = len(cleaned) / sample_rate
    is_stereo     = cleaned.ndim == 2
    print(f"  Cleaned duration   : {fmt(cleaned_dur_s)}  ({cleaned_dur_s:.3f}s)")

    # ── Walk timeline and rebuild ─────────────
    print(f"\n  Rebuilding original {fmt(original_dur_s)} timeline...")

    output_parts = []
    cleaned_pos  = 0
    timeline_pos = 0.0

    for seg in segments:
        seg_start = seg["start_sec"]
        seg_end   = seg["end_sec"]
        seg_dur   = seg_end - seg_start

        # Speech gap BEFORE this silence
        speech_dur = seg_start - timeline_pos
        if speech_dur > 0.001:
            speech_samples = int(round(speech_dur * sample_rate))
            end_pos        = min(cleaned_pos + speech_samples, len(cleaned))
            output_parts.append(cleaned[cleaned_pos:end_pos])
            cleaned_pos = end_pos

        # Silence block (zeros)
        silence_samples = int(round(seg_dur * sample_rate))
        if silence_samples > 0:
            if is_stereo:
                output_parts.append(np.zeros((silence_samples, cleaned.shape[1]), dtype="float32"))
            else:
                output_parts.append(np.zeros(silence_samples, dtype="float32"))

        timeline_pos = seg_end

    # Remaining speech after last silence
    remaining_dur = original_dur_s - timeline_pos
    if remaining_dur > 0.001 and cleaned_pos < len(cleaned):
        end_pos = min(cleaned_pos + int(round(remaining_dur * sample_rate)), len(cleaned))
        output_parts.append(cleaned[cleaned_pos:end_pos])

    # ── Concatenate ───────────────────────────
    restored     = np.concatenate(output_parts, axis=0)
    restored_dur = len(restored) / sample_rate
    diff_ms      = abs(restored_dur - original_dur_s) * 1000

    print(f"  Restored duration  : {fmt(restored_dur)}  ({restored_dur:.3f}s)")
    print(f"  Expected duration  : {fmt(original_dur_s)}  ({original_dur_s:.3f}s)")
    print(f"  Difference         : {diff_ms:.1f} ms  "
          f"{'✅' if diff_ms < 100 else '⚠️ '}")

    # ── Save output ───────────────────────────
    # Always save next to the original input file
    stem         = os.path.splitext(os.path.basename(input_audio))[0]
    default_name = stem.replace("_cleaned", "_restored") + ".wav"
    out_path     = os.path.join(os.path.dirname(os.path.abspath(input_audio)), default_name)

    sf.write(out_path, restored, sample_rate)
    print(f"\n  ✅ Restored audio saved : {out_path}")
    print(f"{'='*55}\n")

    # ── Cleanup temp WAV if we made one ───────
    if tmp_wav_path and os.path.exists(tmp_wav_path):
        os.remove(tmp_wav_path)
        print(f"  Temp WAV removed.")

    open_folder(out_path)
    return out_path


# ──────────────────────────────────────────────
# PLAYBACK
# ──────────────────────────────────────────────
def play_audio(path: str):
    print(f"Playing: {os.path.basename(path)}")
    print("Press Ctrl+C to stop.\n")
    import platform
    system = platform.system()
    if system == "Windows":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
    elif system == "Darwin":
        os.system(f'afplay "{path}"')
    elif system == "Linux":
        os.system(f'aplay "{path}"')


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("\n🔄 WAV/MP3 Dead Air Restorer")
    print("─" * 30)
    print("  Give me the CLEANED audio + JSON report")
    print("  and I will give you the original track back.")
    print("─" * 30)

    check_dependencies()

    # ── Pick cleaned audio (WAV or MP3) ───────
    print("\n  Step 1 — Select the CLEANED audio file (WAV or MP3):")
    cleaned_audio = pick_file(
        "Select the Cleaned Audio file",
        [
            ("Audio Files", "*.wav *.mp3"),
            ("WAV Files",   "*.wav"),
            ("MP3 Files",   "*.mp3"),
            ("All Files",   "*.*"),
        ]
    )
    if not cleaned_audio:
        print("No file selected. Exiting.")
        sys.exit(0)

    # ── Auto-find JSON or pick manually ───────
    auto_json = os.path.splitext(cleaned_audio)[0] + "_report.json"
    if os.path.exists(auto_json):
        print(f"\n  ✅ Auto-found report: {os.path.basename(auto_json)}")
        report_json = auto_json
    else:
        print("\n  Step 2 — Select the JSON report:")
        report_json = pick_file(
            "Select the JSON Report",
            [("JSON Files", "*.json"), ("All Files", "*.*")]
        )

    if not report_json or not os.path.exists(report_json):
        print("No report file found. Exiting.")
        sys.exit(0)

    # ── Restore ───────────────────────────────
    restored_path = restore(cleaned_audio, report_json)
    print(f"\nDone. File saved at:\n  {restored_path}")


if __name__ == "__main__":
    main()