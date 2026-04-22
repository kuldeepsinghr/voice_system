#!/usr/bin/env python3
"""
WAV Dead Air Remover — works on Python 3.14+
Dependencies: numpy, soundfile  (no ffmpeg, no pydub)

- Supports multiple file selection
- User chooses output folder once for all files
- Adaptive thresholding per file
- JSON report saved per file
"""

import sys
import os
import json
from datetime import datetime


# ──────────────────────────────────────────────
# CHECK DEPENDENCIES
# ──────────────────────────────────────────────
def check_dependencies():
    missing = []
    for pkg in ("numpy", "soundfile"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"ERROR: Missing packages: {', '.join(missing)}")
        print(f"Run:  pip install {' '.join(missing)}")
        sys.exit(1)
    print("  ✅ numpy ready")
    print("  ✅ soundfile ready")


# ──────────────────────────────────────────────
# FILE PICKER  — multiple files
# ──────────────────────────────────────────────
def select_files() -> list:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    paths = filedialog.askopenfilenames(
        title="Select WAV File(s) — hold Ctrl to select multiple",
        filetypes=[("WAV Files", "*.wav"), ("All Files", "*.*")],
    )
    root.destroy()
    return list(paths)


# ──────────────────────────────────────────────
# OUTPUT FOLDER PICKER
# ──────────────────────────────────────────────
def select_output_folder(initial_dir: str) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(
        title="Choose folder to save cleaned files",
        initialdir=initial_dir,
    )
    root.destroy()
    return folder


# ──────────────────────────────────────────────
# OPEN OUTPUT FOLDER
# ──────────────────────────────────────────────
def open_folder(file_path: str):
    import platform
    system = platform.system()
    if system == "Windows":
        os.system(f'explorer /select,"{file_path}"')
    elif system == "Darwin":
        os.system(f'open -R "{file_path}"')
    elif system == "Linux":
        os.system(f'xdg-open "{os.path.dirname(os.path.abspath(file_path))}"')


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    elif m:
        return f"{m}m {s}s"
    else:
        return f"{s}s"

def seconds_to_timestamp(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


# ──────────────────────────────────────────────
# SAVE REPORT (JSON)
# ──────────────────────────────────────────────
def save_report(report: dict, output_audio_path: str):
    base      = os.path.splitext(output_audio_path)[0]
    json_path = base + "_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  📄 JSON report : {json_path}")
    return json_path


# ──────────────────────────────────────────────
# ADAPTIVE THRESHOLD
# ──────────────────────────────────────────────
def compute_adaptive_threshold(mono, sample_rate: int,
                                frame_ms: int = 10,
                                noise_percentile: int = 10,
                                multiplier: float = 8.0) -> tuple:
    import numpy as np
    frame_size = int(sample_rate * frame_ms / 1000)
    num_frames = len(mono) // frame_size
    rms_vals = np.array([
        np.sqrt(np.mean(mono[i * frame_size:(i + 1) * frame_size] ** 2))
        for i in range(num_frames)
    ])
    noise_floor = float(np.percentile(rms_vals, noise_percentile))
    threshold   = noise_floor * multiplier
    return threshold, noise_floor, rms_vals


# ──────────────────────────────────────────────
# CROSSFADE CONCAT
# ──────────────────────────────────────────────
def crossfade_concat(chunks, audio, sample_rate, fade_ms=8):
    import numpy as np
    fade_samples = int(sample_rate * fade_ms / 1000)
    output = audio[chunks[0][0]:chunks[0][1]].copy()
    for start, end in chunks[1:]:
        segment = audio[start:end]
        if len(output) > fade_samples and len(segment) > fade_samples:
            fade_out = np.linspace(1, 0, fade_samples)
            fade_in  = np.linspace(0, 1, fade_samples)
            output[-fade_samples:] = (
                output[-fade_samples:] * fade_out +
                segment[:fade_samples] * fade_in
            )
            output = np.concatenate([output, segment[fade_samples:]], axis=0)
        else:
            output = np.concatenate([output, segment], axis=0)
    return output


# ──────────────────────────────────────────────
# PROCESS ONE FILE
# ──────────────────────────────────────────────
def remove_dead_air(file_path: str, output_dir: str,
                    min_silence_ms: int = 700,
                    padding_ms: int = 200) -> str:
    import numpy as np
    import soundfile as sf

    print(f"\n{'='*55}")
    print(f"  File    : {os.path.basename(file_path)}")

    audio, sample_rate = sf.read(file_path, dtype="float32")

    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    original_duration_s = len(mono) / sample_rate

    print(f"  Duration: {format_duration(original_duration_s)}")

    # ── Adaptive threshold ────────────────────
    frame_ms   = 10
    frame_size = int(sample_rate * frame_ms / 1000)

    silence_thresh, noise_floor, rms_vals = compute_adaptive_threshold(
        mono, sample_rate, frame_ms=frame_ms
    )
    num_frames = len(rms_vals)

    print(f"  Noise floor (auto) : {noise_floor:.6f} RMS")
    print(f"  Threshold  (auto)  : {silence_thresh:.6f} RMS")
    print(f"  Scanning...")

    # ── Detect speech chunks ──────────────────
    is_speech          = rms_vals > silence_thresh
    min_silence_frames = max(1, min_silence_ms // frame_ms)
    padding_frames     = max(1, padding_ms     // frame_ms)

    speech_chunks = []
    in_speech     = False
    start         = 0
    silence_count = 0

    for i, speech in enumerate(is_speech):
        if speech:
            if not in_speech:
                start     = max(0, i - padding_frames)
                in_speech = True
            silence_count = 0
        else:
            if in_speech:
                silence_count += 1
                if silence_count >= min_silence_frames:
                    end = min(num_frames, i + padding_frames)
                    speech_chunks.append((start, end))
                    in_speech     = False
                    silence_count = 0

    if in_speech:
        speech_chunks.append((start, num_frames))

    if not speech_chunks:
        print("  WARNING: No speech detected. Skipping file.")
        return None

    # ── Build removed segments ────────────────
    removed_segments = []
    seg_index = 1

    def add_removed(s_frame, e_frame):
        nonlocal seg_index
        start_s = (s_frame * frame_size) / sample_rate
        end_s   = (e_frame * frame_size) / sample_rate
        dur     = end_s - start_s
        if dur > 0.1:
            removed_segments.append({
                "index":           seg_index,
                "start_sec":       round(start_s, 3),
                "end_sec":         round(end_s, 3),
                "duration_sec":    round(dur, 3),
                "start_timestamp": seconds_to_timestamp(start_s),
                "end_timestamp":   seconds_to_timestamp(end_s),
            })
            seg_index += 1

    if speech_chunks[0][0] > 0:
        add_removed(0, speech_chunks[0][0])
    for i in range(len(speech_chunks) - 1):
        add_removed(speech_chunks[i][1], speech_chunks[i + 1][0])
    if speech_chunks[-1][1] < num_frames:
        add_removed(speech_chunks[-1][1], num_frames)

    # ── Crossfade stitch ─────────────────────
    sample_chunks   = []
    last_end_sample = 0
    for fs, fe in speech_chunks:
        start_sample = max(int(fs * frame_size), last_end_sample)
        end_sample   = int(fe * frame_size)
        if end_sample > start_sample:
            sample_chunks.append((start_sample, end_sample))
            last_end_sample = end_sample

    cleaned = crossfade_concat(sample_chunks, audio, sample_rate)

    cleaned_duration_s = len(cleaned) / sample_rate
    removed_s          = original_duration_s - cleaned_duration_s
    pct                = (removed_s / original_duration_s) * 100

    print(f"  Speech chunks   : {len(speech_chunks)}")
    print(f"  Dead air removed: {format_duration(removed_s)}  ({pct:.1f}%)")
    print(f"  New duration    : {format_duration(cleaned_duration_s)}")

    # ── Print segments table ──────────────────
    if removed_segments:
        print(f"\n  {'#':<5} {'Start':<15} {'End':<15} {'Duration':>10}")
        print(f"  {'-'*48}")
        for seg in removed_segments:
            print(f"  {seg['index']:<5} {seg['start_timestamp']:<15} "
                  f"{seg['end_timestamp']:<15} {seg['duration_sec']:>8.2f}s")

    # ── Save cleaned audio ────────────────────
    stem        = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, stem + "_cleaned.wav")
    import soundfile as sf
    sf.write(output_path, cleaned, sample_rate)
    print(f"\n  ✅ Saved : {output_path}")

    # ── Save JSON report ──────────────────────
    report = {
        "generated_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file":        os.path.abspath(file_path),
        "output_file":        os.path.abspath(output_path),
        "sample_rate_hz":     sample_rate,
        "noise_floor_rms":    f"{noise_floor:.8f}",
        "auto_threshold_rms": f"{silence_thresh:.8f}",
        "min_silence_ms":     min_silence_ms,
        "padding_ms":         padding_ms,
        "original_duration":  seconds_to_timestamp(original_duration_s),
        "cleaned_duration":   seconds_to_timestamp(cleaned_duration_s),
        "total_removed":      seconds_to_timestamp(removed_s),
        "removed_percent":    f"{pct:.1f}%",
        "segments_removed":   len(removed_segments),
        "removed_segments":   removed_segments,
    }
    save_report(report, output_path)
    print(f"{'='*55}")

    return output_path


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("\n🎵 WAV Dead Air Remover")
    print("─" * 30)

    check_dependencies()

    # ── Step 1: Select files ──────────────────
    print("\n  Step 1 — Select WAV file(s)  [hold Ctrl for multiple]:")
    file_paths = select_files()

    if not file_paths:
        print("No files selected. Exiting.")
        sys.exit(0)

    # Filter non-WAV
    wav_files = [f for f in file_paths if f.lower().endswith(".wav")]
    skipped   = [f for f in file_paths if not f.lower().endswith(".wav")]
    if skipped:
        print(f"\n  ⚠️  Skipping {len(skipped)} non-WAV file(s).")
    if not wav_files:
        print("  No valid WAV files selected. Exiting.")
        sys.exit(0)

    print(f"\n  {len(wav_files)} file(s) selected:")
    for f in wav_files:
        print(f"    • {os.path.basename(f)}")

    # ── Step 2: Choose output folder ─────────
    print(f"\n  Step 2 — Choose where to save the cleaned files:")
    default_dir = os.path.dirname(os.path.abspath(wav_files[0]))
    output_dir  = select_output_folder(default_dir)

    if not output_dir:
        print("  No folder selected — saving next to original files.")
        output_dir = None  # handled per-file below

    # ── Step 3: Process each file ─────────────
    print(f"\n  Processing {len(wav_files)} file(s)...\n")
    results = []

    for i, file_path in enumerate(wav_files, 1):
        print(f"\n  [{i}/{len(wav_files)}] {os.path.basename(file_path)}")

        # If no output folder chosen, save next to each source file
        out_dir = output_dir if output_dir else os.path.dirname(os.path.abspath(file_path))

        try:
            cleaned_path = remove_dead_air(file_path, out_dir)
            if cleaned_path:
                results.append(("OK",    file_path, cleaned_path))
            else:
                results.append(("SKIP",  file_path, None))
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append(("ERROR", file_path, str(e)))

    # ── Summary ───────────────────────────────
    print(f"\n\n{'='*55}")
    print(f"  SUMMARY — {len(wav_files)} file(s) processed")
    print(f"  {'─'*50}")
    ok    = [r for r in results if r[0] == "OK"]
    skips = [r for r in results if r[0] == "SKIP"]
    errs  = [r for r in results if r[0] == "ERROR"]

    for status, src, out in results:
        icon = "✅" if status == "OK" else ("⚠️ " if status == "SKIP" else "❌")
        print(f"  {icon} {os.path.basename(src)}")
        if status == "OK":
            print(f"       → {os.path.basename(out)}")

    print(f"\n  Done : {len(ok)} cleaned  |  {len(skips)} skipped  |  {len(errs)} errors")
    print(f"{'='*55}\n")

    # Open output folder once at the end
    if ok:
        open_folder(ok[0][2])

    input("  Press Enter to exit...")


if __name__ == "__main__":
    main()