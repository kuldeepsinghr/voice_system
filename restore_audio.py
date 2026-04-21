#!/usr/bin/env python3
"""
WAV Dead Air Restorer — Python 3.14+
Dependencies: numpy, soundfile

Input  : 5min cleaned WAV  +  JSON report (from play_audio.py)
Output : 20min restored WAV — silence re-inserted at original positions

Process:
  The JSON has a list of removed segments with start_sec / end_sec.
  We walk through the cleaned audio and insert silence blocks at those
  exact timestamps to rebuild the original 20min track.
"""

import sys
import os
import json


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

def save_dialog(default_name: str, initial_dir: str) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.asksaveasfilename(
        title="Save Restored Audio As",
        initialdir=initial_dir,
        initialfile=default_name,
        defaultextension=".wav",
        filetypes=[("WAV Files", "*.wav"), ("All Files", "*.*")],
    )
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
def restore(cleaned_wav: str, report_json: str) -> str:
    import numpy as np
    import soundfile as sf

    print(f"\n{'='*55}")

    # ── Load JSON ─────────────────────────────
    print(f"  Reading report : {os.path.basename(report_json)}")
    with open(report_json, "r", encoding="utf-8") as f:
        report = json.load(f)

    sample_rate    = report["sample_rate_hz"]
    original_dur_s = ts_to_sec(report["original_duration"])
    segments       = sorted(report["removed_segments"], key=lambda x: x["start_sec"])

    print(f"  Original duration  : {fmt(original_dur_s)}  ({original_dur_s:.3f}s)")
    print(f"  Silence blocks     : {len(segments)}")

    # ── Load cleaned audio ────────────────────
    print(f"  Reading audio  : {os.path.basename(cleaned_wav)}")
    cleaned, file_sr = sf.read(cleaned_wav, dtype="float32")

    if file_sr != sample_rate:
        print(f"  ⚠️  Sample rate mismatch — using file rate ({file_sr} Hz)")
        sample_rate = file_sr

    cleaned_dur_s = len(cleaned) / sample_rate
    is_stereo     = cleaned.ndim == 2
    print(f"  Cleaned duration   : {fmt(cleaned_dur_s)}  ({cleaned_dur_s:.3f}s)")

    # ──────────────────────────────────────────
    # CORE LOGIC
    #
    # We walk the original 20min timeline from left to right.
    # The JSON tells us WHEN silence blocks were removed.
    # Everything between those silence blocks = speech from cleaned audio.
    #
    # Timeline example:
    #   0s ──[silence 0→8s]──[speech]──[silence 14→22s]──[speech]──[silence]── 20min
    #
    # We read the cleaned audio sequentially and interleave silence blocks
    # at their original timestamps.
    # ──────────────────────────────────────────

    print(f"\n  Rebuilding original {fmt(original_dur_s)} timeline...")

    output_parts  = []   # list of numpy arrays to concatenate at the end
    cleaned_pos   = 0    # sample cursor into the cleaned audio
    timeline_pos  = 0.0  # current position in the original timeline (seconds)

    for seg in segments:
        seg_start = seg["start_sec"]
        seg_end   = seg["end_sec"]
        seg_dur   = seg["end_sec"] - seg["start_sec"]

        # ── Speech gap BEFORE this silence block ──
        # From current timeline position up to where silence starts
        speech_dur = seg_start - timeline_pos

        if speech_dur > 0.001:
            speech_samples = int(round(speech_dur * sample_rate))
            end_pos        = cleaned_pos + speech_samples

            # Guard: don't read past end of cleaned audio
            end_pos = min(end_pos, len(cleaned))
            chunk   = cleaned[cleaned_pos:end_pos]
            output_parts.append(chunk)
            cleaned_pos = end_pos

        # ── Silence block ──────────────────────
        silence_samples = int(round(seg_dur * sample_rate))
        if silence_samples > 0:
            if is_stereo:
                silence = np.zeros((silence_samples, cleaned.shape[1]), dtype="float32")
            else:
                silence = np.zeros(silence_samples, dtype="float32")
            output_parts.append(silence)

        timeline_pos = seg_end

    # ── Remaining speech AFTER last silence block ──
    remaining_dur = original_dur_s - timeline_pos
    if remaining_dur > 0.001 and cleaned_pos < len(cleaned):
        remaining_samples = int(round(remaining_dur * sample_rate))
        end_pos           = min(cleaned_pos + remaining_samples, len(cleaned))
        output_parts.append(cleaned[cleaned_pos:end_pos])

    # ── Concatenate everything ────────────────
    restored     = np.concatenate(output_parts, axis=0)
    restored_dur = len(restored) / sample_rate
    diff_ms      = abs(restored_dur - original_dur_s) * 1000

    print(f"  Restored duration  : {fmt(restored_dur)}  ({restored_dur:.3f}s)")
    print(f"  Expected duration  : {fmt(original_dur_s)}  ({original_dur_s:.3f}s)")
    print(f"  Difference         : {diff_ms:.1f} ms  "
          f"{'✅' if diff_ms < 100 else '⚠️ '}")

    # ── Save ──────────────────────────────────
    stem         = os.path.splitext(os.path.basename(cleaned_wav))[0]
    default_name = stem.replace("_cleaned", "_restored") + ".wav"
    initial_dir  = os.path.dirname(os.path.abspath(cleaned_wav))

    # print(f"\n  Opening save dialog...")
    # out_path = save_dialog(default_name, initial_dir)

    # if not out_path:
    #     out_path = os.path.join(initial_dir, default_name)
    #     print(f"  Cancelled — saving to default location.")

    out_path = os.path.join(initial_dir, default_name)
    print(f"\n  Saving automatically...")

    sf.write(out_path, restored, sample_rate)

    print(f"\n  ✅ Restored audio saved : {out_path}")
    print(f"{'='*55}\n")

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
    print("\n🔄 WAV Dead Air Restorer")
    print("─" * 30)
    print("  Give me the CLEANED audio + JSON report")
    print("  and I will give you the original track back.")
    print("─" * 30)

    check_dependencies()

    # ── Step 1: Pick cleaned WAV ──────────────
    print("\n  Step 1 — Select the CLEANED WAV  (e.g. interview_cleaned.wav):")
    cleaned_wav = pick_file(
        "Select the Cleaned WAV file",
        [("WAV Files", "*.wav"), ("All Files", "*.*")]
    )
    if not cleaned_wav:
        print("No file selected. Exiting.")
        sys.exit(0)

    # ── Step 2: Find or pick JSON ─────────────
    auto_json = os.path.splitext(cleaned_wav)[0] + "_report.json"
    if os.path.exists(auto_json):
        print(f"\n  ✅ Auto-found report: {os.path.basename(auto_json)}")
        report_json = auto_json
    else:
        print("\n  Step 2 — Select the JSON report  (e.g. interview_cleaned_report.json):")
        report_json = pick_file(
            "Select the JSON Report",
            [("JSON Files", "*.json"), ("All Files", "*.*")]
        )
    if not report_json or not os.path.exists(report_json):
        print("No report file found. Exiting.")
        sys.exit(0)

    # ── Restore ───────────────────────────────
    restored_path = restore(cleaned_wav, report_json)

    print(f"\nDone. File saved at:\n  {restored_path}")


if __name__ == "__main__":
    main()
