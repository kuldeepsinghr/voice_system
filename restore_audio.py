#!/usr/bin/env python3
"""
WAV/MP3 Dead Air Restorer — Python 3.14+
Dependencies: numpy, soundfile

- Select multiple cleaned files at once (WAV or MP3)
- JSON reports auto-detected per file, or picked manually
- Choose output folder once for all files
- Summary printed at the end
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
# MP3 → WAV CONVERSION
# ──────────────────────────────────────────────
def mp3_to_wav(mp3_path: str) -> str:
    import tempfile, subprocess, shutil
    tmp_wav = tempfile.mktemp(suffix="_restored_input.wav")
    print(f"  Converting MP3 → WAV (temporary)...")

    if shutil.which("ffmpeg"):
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, tmp_wav],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if r.returncode == 0 and os.path.exists(tmp_wav):
            print(f"  ✅ MP3 converted via ffmpeg")
            return tmp_wav

    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        if shutil.which("ffmpeg"):
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", mp3_path, tmp_wav],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if r.returncode == 0 and os.path.exists(tmp_wav):
                print(f"  ✅ MP3 converted via static-ffmpeg")
                return tmp_wav
    except ImportError:
        pass

    print("\n  ┌─────────────────────────────────────────────────┐")
    print("  │  MP3 conversion requires ffmpeg.                │")
    print("  │  Option A:  pip install static-ffmpeg           │")
    print("  │  Option B:  install ffmpeg + add to PATH        │")
    print("  └─────────────────────────────────────────────────┘")
    sys.exit(1)


# ──────────────────────────────────────────────
# FILE / FOLDER PICKERS
# ──────────────────────────────────────────────
def pick_files(title: str, filetypes: list) -> list:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    paths = filedialog.askopenfilenames(title=title, filetypes=filetypes)
    root.destroy()
    return list(paths)

def pick_file(title: str, filetypes: list) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    return path

def pick_folder(title: str, initial_dir: str) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title=title, initialdir=initial_dir)
    root.destroy()
    return folder


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
# FIND JSON FOR A GIVEN AUDIO FILE
# Returns the json path if auto-found, else None
# ──────────────────────────────────────────────
def find_json(audio_path: str) -> str | None:
    auto = os.path.splitext(audio_path)[0] + "_report.json"
    return auto if os.path.exists(auto) else None


# ──────────────────────────────────────────────
# RESTORE ONE FILE
# ──────────────────────────────────────────────
def restore_one(input_audio: str, report_json: str, output_dir: str) -> str:
    import numpy as np
    import soundfile as sf

    print(f"\n{'='*55}")

    # ── Handle MP3 ────────────────────────────
    ext          = os.path.splitext(input_audio)[1].lower()
    tmp_wav_path = None

    if ext == ".mp3":
        print(f"  Input format   : MP3 — converting to WAV first")
        tmp_wav_path = mp3_to_wav(input_audio)
        wav_to_read  = tmp_wav_path
    elif ext == ".wav":
        print(f"  Input format   : WAV")
        wav_to_read  = input_audio
    else:
        raise ValueError(f"Unsupported format '{ext}'. Use WAV or MP3.")

    # ── Load JSON ─────────────────────────────
    print(f"  Report         : {os.path.basename(report_json)}")
    with open(report_json, "r", encoding="utf-8") as f:
        report = json.load(f)

    sample_rate    = report["sample_rate_hz"]
    original_dur_s = ts_to_sec(report["original_duration"])
    segments       = sorted(report["removed_segments"], key=lambda x: x["start_sec"])

    print(f"  Original dur   : {fmt(original_dur_s)}")
    print(f"  Silence blocks : {len(segments)}")

    # ── Load audio ────────────────────────────
    cleaned, file_sr = sf.read(wav_to_read, dtype="float32")

    if file_sr != sample_rate:
        print(f"  ⚠️  SR mismatch — using file rate ({file_sr} Hz)")
        sample_rate = file_sr

    cleaned_dur_s = len(cleaned) / sample_rate
    is_stereo     = cleaned.ndim == 2
    print(f"  Cleaned dur    : {fmt(cleaned_dur_s)}")
    print(f"  Rebuilding timeline...")

    # ── Walk timeline ─────────────────────────
    output_parts = []
    cleaned_pos  = 0
    timeline_pos = 0.0

    for seg in segments:
        speech_dur = seg["start_sec"] - timeline_pos
        if speech_dur > 0.001:
            n   = int(round(speech_dur * sample_rate))
            end = min(cleaned_pos + n, len(cleaned))
            output_parts.append(cleaned[cleaned_pos:end])
            cleaned_pos = end

        sil_n = int(round((seg["end_sec"] - seg["start_sec"]) * sample_rate))
        if sil_n > 0:
            shape = (sil_n, cleaned.shape[1]) if is_stereo else (sil_n,)
            output_parts.append(np.zeros(shape, dtype="float32"))

        timeline_pos = seg["end_sec"]

    remaining = original_dur_s - timeline_pos
    if remaining > 0.001 and cleaned_pos < len(cleaned):
        end = min(cleaned_pos + int(round(remaining * sample_rate)), len(cleaned))
        output_parts.append(cleaned[cleaned_pos:end])

    restored     = np.concatenate(output_parts, axis=0)
    restored_dur = len(restored) / sample_rate
    diff_ms      = abs(restored_dur - original_dur_s) * 1000

    print(f"  Restored dur   : {fmt(restored_dur)}")
    print(f"  Diff           : {diff_ms:.1f} ms  {'✅' if diff_ms < 100 else '⚠️ '}")

    # ── Save ──────────────────────────────────
    stem     = os.path.splitext(os.path.basename(input_audio))[0]
    out_name = stem.replace("_cleaned", "_restored") + ".wav"
    out_path = os.path.join(output_dir, out_name)

    sf.write(out_path, restored, sample_rate)
    print(f"  ✅ Saved        : {out_path}")
    print(f"{'='*55}")

    # ── Cleanup temp ──────────────────────────
    if tmp_wav_path and os.path.exists(tmp_wav_path):
        os.remove(tmp_wav_path)

    return out_path


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("\n🔄 WAV/MP3 Dead Air Restorer")
    print("─" * 30)

    check_dependencies()

    # ── Step 1: Select cleaned audio files ────
    print("\n  Step 1 — Select CLEANED audio file(s)  [hold Ctrl for multiple]:")
    audio_files = pick_files(
        "Select Cleaned Audio file(s) — WAV or MP3",
        [
            ("Audio Files", "*.wav *.mp3"),
            ("WAV Files",   "*.wav"),
            ("MP3 Files",   "*.mp3"),
            ("All Files",   "*.*"),
        ]
    )
    if not audio_files:
        print("No files selected. Exiting.")
        sys.exit(0)

    print(f"\n  {len(audio_files)} file(s) selected:")
    for f in audio_files:
        print(f"    • {os.path.basename(f)}")

    # ── Step 2: Match each file to its JSON ───
    # Auto-detect where possible, ask manually for the rest
    pairs = []   # list of (audio_path, json_path)
    missing_json = []

    for audio in audio_files:
        json_path = find_json(audio)
        if json_path:
            print(f"\n  ✅ Auto-found JSON: {os.path.basename(json_path)}")
            pairs.append((audio, json_path))
        else:
            missing_json.append(audio)

    for audio in missing_json:
        print(f"\n  ⚠️  No JSON found for: {os.path.basename(audio)}")
        print(f"  Please select the JSON report manually:")
        json_path = pick_file(
            f"Select JSON report for {os.path.basename(audio)}",
            [("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if json_path and os.path.exists(json_path):
            pairs.append((audio, json_path))
        else:
            print(f"  Skipping {os.path.basename(audio)} — no JSON provided.")

    if not pairs:
        print("\nNo files could be matched to a JSON report. Exiting.")
        sys.exit(0)

    # ── Step 3: Choose output folder ──────────
    print(f"\n  Step 3 — Choose where to save the restored files:")
    default_dir = os.path.dirname(os.path.abspath(pairs[0][0]))
    output_dir  = pick_folder(
        "Choose folder to save restored files",
        default_dir
    )
    if not output_dir:
        print("  No folder chosen — saving next to each source file.")

    # ── Step 4: Process each pair ─────────────
    print(f"\n  Processing {len(pairs)} file(s)...\n")
    results = []

    for i, (audio, json_path) in enumerate(pairs, 1):
        print(f"\n  [{i}/{len(pairs)}] {os.path.basename(audio)}")
        out_dir = output_dir if output_dir else os.path.dirname(os.path.abspath(audio))
        try:
            out = restore_one(audio, json_path, out_dir)
            results.append(("OK",    audio, out))
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append(("ERROR", audio, str(e)))

    # ── Summary ───────────────────────────────
    print(f"\n\n{'='*55}")
    print(f"  SUMMARY — {len(pairs)} file(s) processed")
    print(f"  {'─'*50}")

    ok   = [r for r in results if r[0] == "OK"]
    errs = [r for r in results if r[0] == "ERROR"]

    for status, src, out in results:
        icon = "✅" if status == "OK" else "❌"
        print(f"  {icon} {os.path.basename(src)}")
        if status == "OK":
            print(f"       → {os.path.basename(out)}")
        else:
            print(f"       Error: {out}")

    print(f"\n  Done : {len(ok)} restored  |  {len(errs)} errors")
    print(f"{'='*55}\n")

    if ok:
        open_folder(ok[0][2])

    input("  Press Enter to exit...")


if __name__ == "__main__":
    main()