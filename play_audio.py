#!/usr/bin/env python3
"""
WAV Dead Air Remover — works on Python 3.14+
Dependencies: numpy, soundfile  (no ffmpeg, no pydub)
- Removes dead air from WAV files
- Saves cleaned WAV output
- Saves a detailed JSON + CSV report with timestamps of every removed segment
"""

import sys
import os
import json
import csv
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
# FILE PICKER (WAV input)
# ──────────────────────────────────────────────
def select_file() -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Select a WAV Audio File",
        filetypes=[
            ("WAV Files", "*.wav"),
            ("All Files", "*.*"),
        ]
    )
    root.destroy()
    return file_path


# ──────────────────────────────────────────────
# SAVE AS DIALOG
# ──────────────────────────────────────────────
def save_file_dialog(default_name: str, initial_dir: str) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    output_path = filedialog.asksaveasfilename(
        title="Save Cleaned Audio As",
        initialdir=initial_dir,
        initialfile=default_name,
        defaultextension=".wav",
        filetypes=[
            ("WAV Files", "*.wav"),
            ("All Files", "*.*"),
        ]
    )
    root.destroy()
    return output_path


# ──────────────────────────────────────────────
# OPEN OUTPUT FOLDER
# ──────────────────────────────────────────────
def open_folder(file_path: str):
    import platform
    folder = os.path.dirname(os.path.abspath(file_path))
    system = platform.system()
    if system == "Windows":
        os.system(f'explorer /select,"{file_path}"')
    elif system == "Darwin":
        os.system(f'open -R "{file_path}"')
    elif system == "Linux":
        os.system(f'xdg-open "{folder}"')


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
    """Convert seconds to HH:MM:SS.mmm format."""
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


# ──────────────────────────────────────────────
# SAVE REPORT (JSON + CSV)
# ──────────────────────────────────────────────
def save_report(report: dict, output_audio_path: str):
    """Save removal report as both JSON and CSV next to the output audio file."""
    base = os.path.splitext(output_audio_path)[0]

    # ── JSON ──────────────────────────────────
    json_path = base + "_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  📄 JSON report : {json_path}")

    # ── CSV ───────────────────────────────────
    csv_path = base + "_report.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header block
        writer.writerow(["=== Dead Air Removal Report ==="])
        writer.writerow(["Generated",          report["generated_at"]])
        writer.writerow(["Source File",         report["source_file"]])
        writer.writerow(["Output File",         report["output_file"]])
        writer.writerow(["Original Duration",   report["original_duration"]])
        writer.writerow(["Cleaned Duration",    report["cleaned_duration"]])
        writer.writerow(["Total Removed",       report["total_removed"]])
        writer.writerow(["Removed %",           report["removed_percent"]])
        writer.writerow(["Segments Removed",    report["segments_removed"]])
        writer.writerow([])

        # Removed segments table
        writer.writerow(["#", "Start Timestamp", "End Timestamp", "Start (s)", "End (s)", "Duration (s)"])
        for seg in report["removed_segments"]:
            writer.writerow([
                seg["index"],
                seg["start_timestamp"],
                seg["end_timestamp"],
                f"{seg['start_sec']:.3f}",
                f"{seg['end_sec']:.3f}",
                f"{seg['duration_sec']:.3f}",
            ])

    print(f"  📊 CSV report  : {csv_path}")
    return json_path, csv_path


# ──────────────────────────────────────────────
# DEAD AIR REMOVAL
# ──────────────────────────────────────────────
def remove_dead_air(
    file_path: str,
    silence_thresh: float = 0.01,
    min_silence_ms: int   = 700,
    padding_ms: int       = 150,
) -> str:
    import numpy as np
    import soundfile as sf

    print(f"\n{'='*55}")
    print(f"  Loading : {os.path.basename(file_path)}")

    audio, sample_rate = sf.read(file_path, dtype="float32")

    if audio.ndim == 2:
        mono = audio.mean(axis=1)
    else:
        mono = audio

    original_duration_s = len(mono) / sample_rate
    print(f"  Sample rate        : {sample_rate} Hz")
    print(f"  Original duration  : {format_duration(original_duration_s)}")
    print(f"  Silence threshold  : {silence_thresh} RMS")
    print(f"  Min silence to cut : {min_silence_ms} ms")
    print(f"  Scanning for speech chunks...")

    frame_ms   = 10
    frame_size = int(sample_rate * frame_ms / 1000)
    num_frames = len(mono) // frame_size

    is_speech = np.array([
        np.sqrt(np.mean(mono[i * frame_size:(i + 1) * frame_size] ** 2)) > silence_thresh
        for i in range(num_frames)
    ])

    min_silence_frames = max(1, min_silence_ms // frame_ms)
    padding_frames     = max(1, padding_ms // frame_ms)

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
        print("\n  WARNING: No speech detected.")
        print("  Try lowering silence_thresh (e.g. 0.005).")
        print("  Keeping original file unchanged.")
        return file_path

    # ── Build removed segments (gaps BETWEEN speech chunks) ──
    removed_segments = []
    seg_index = 1

    # Gap before first speech chunk
    if speech_chunks[0][0] > 0:
        start_s = 0.0
        end_s   = (speech_chunks[0][0] * frame_size) / sample_rate
        if end_s - start_s > 0.05:
            removed_segments.append({
                "index":           seg_index,
                "start_sec":       round(start_s, 3),
                "end_sec":         round(end_s, 3),
                "duration_sec":    round(end_s - start_s, 3),
                "start_timestamp": seconds_to_timestamp(start_s),
                "end_timestamp":   seconds_to_timestamp(end_s),
            })
            seg_index += 1

    # Gaps between consecutive speech chunks
    for i in range(len(speech_chunks) - 1):
        gap_start_frame = speech_chunks[i][1]
        gap_end_frame   = speech_chunks[i + 1][0]
        start_s = (gap_start_frame * frame_size) / sample_rate
        end_s   = (gap_end_frame   * frame_size) / sample_rate
        if end_s - start_s > 0.05:
            removed_segments.append({
                "index":           seg_index,
                "start_sec":       round(start_s, 3),
                "end_sec":         round(end_s, 3),
                "duration_sec":    round(end_s - start_s, 3),
                "start_timestamp": seconds_to_timestamp(start_s),
                "end_timestamp":   seconds_to_timestamp(end_s),
            })
            seg_index += 1

    # Gap after last speech chunk
    if speech_chunks[-1][1] < num_frames:
        start_s = (speech_chunks[-1][1] * frame_size) / sample_rate
        end_s   = original_duration_s
        if end_s - start_s > 0.05:
            removed_segments.append({
                "index":           seg_index,
                "start_sec":       round(start_s, 3),
                "end_sec":         round(end_s, 3),
                "duration_sec":    round(end_s - start_s, 3),
                "start_timestamp": seconds_to_timestamp(start_s),
                "end_timestamp":   seconds_to_timestamp(end_s),
            })

    # ── Stitch speech chunks ──────────────────
    parts = []
    for (fs, fe) in speech_chunks:
        parts.append(audio[fs * frame_size : fe * frame_size])

    cleaned = np.concatenate(parts, axis=0)

    cleaned_duration_s = len(cleaned) / sample_rate
    removed_s          = original_duration_s - cleaned_duration_s
    pct                = (removed_s / original_duration_s) * 100

    print(f"\n  Speech chunks found : {len(speech_chunks)}")
    print(f"  Dead air removed    : {format_duration(removed_s)}  ({pct:.1f}%)")
    print(f"  New duration        : {format_duration(cleaned_duration_s)}")

    # ── Print removed segments table ─────────
    if removed_segments:
        print(f"\n  {'#':<4} {'Start':<14} {'End':<14} {'Duration':>10}")
        print(f"  {'-'*46}")
        for seg in removed_segments:
            print(f"  {seg['index']:<4} {seg['start_timestamp']:<14} {seg['end_timestamp']:<14} {seg['duration_sec']:>8.2f}s")

    # ── Save As dialog ────────────────────────
    default_name = os.path.splitext(os.path.basename(file_path))[0] + "_cleaned.wav"
    initial_dir  = os.path.dirname(os.path.abspath(file_path))

    print(f"\n  Opening save dialog...")
    output_path = save_file_dialog(default_name, initial_dir)

    if not output_path:
        output_path = os.path.join(initial_dir, default_name)
        print(f"  Save cancelled — using default location.")

    sf.write(output_path, cleaned, sample_rate)
    print(f"\n  ✅ Audio saved : {output_path}")

    # ── Build and save report ─────────────────
    report = {
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file":       os.path.abspath(file_path),
        "output_file":       os.path.abspath(output_path),
        "sample_rate_hz":    sample_rate,
        "silence_threshold": silence_thresh,
        "min_silence_ms":    min_silence_ms,
        "padding_ms":        padding_ms,
        "original_duration": seconds_to_timestamp(original_duration_s),
        "cleaned_duration":  seconds_to_timestamp(cleaned_duration_s),
        "total_removed":     seconds_to_timestamp(removed_s),
        "removed_percent":   f"{pct:.1f}%",
        "segments_removed":  len(removed_segments),
        "removed_segments":  removed_segments,
    }

    print()
    save_report(report, output_path)
    print(f"{'='*55}\n")

    open_folder(output_path)

    return output_path


# ──────────────────────────────────────────────
# PLAYBACK
# ──────────────────────────────────────────────
def play_audio(file_path: str):
    print(f"Playing: {os.path.basename(file_path)}")
    print("Press Ctrl+C to stop.\n")

    import platform
    system = platform.system()

    if system == "Windows":
        import winsound
        winsound.PlaySound(file_path, winsound.SND_FILENAME)
    elif system == "Darwin":
        os.system(f'afplay "{file_path}"')
    elif system == "Linux":
        if os.system("which aplay > /dev/null 2>&1") == 0:
            os.system(f'aplay "{file_path}"')
        else:
            print(f"Install aplay to play audio. File at:\n  {file_path}")
    else:
        print(f"File saved at:\n  {file_path}")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("\n🎵 WAV Dead Air Remover")
    print("─" * 30)

    check_dependencies()

    if len(sys.argv) >= 2:
        file_path = sys.argv[1]
    else:
        print("\n  Opening file picker...")
        file_path = select_file()

    if not file_path:
        print("No file selected. Exiting.")
        sys.exit(0)

    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    if not file_path.lower().endswith(".wav"):
        print("Error: Only WAV files are supported.")
        sys.exit(1)

    cleaned_path = remove_dead_air(file_path)

    answer = input("Play the cleaned audio now? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        try:
            play_audio(cleaned_path)
            print("\nPlayback finished.")
        except KeyboardInterrupt:
            print("\nPlayback stopped by user.")
    else:
        print(f"\nDone. File saved at:\n  {cleaned_path}")


if __name__ == "__main__":
    main()
