#!/usr/bin/env python3
"""
Audio Player Script
- Run with no arguments: opens a file picker window
- Run with a path:       python play_audio.py song.mp3
Supports: MP3, WAV, OGG, FLAC, AAC, M4A, and more
"""

import sys
import os


def select_file() -> str:
    """Open a native file picker dialog and return the selected file path."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()                    # Hide the blank tkinter window
    root.attributes("-topmost", True)  # Bring dialog to front

    file_path = filedialog.askopenfilename(
        title="Select an Audio File",
        filetypes=[
            ("Audio Files", "*.mp3 *.wav *.ogg *.flac *.aac *.m4a *.wma"),
            ("MP3 Files",   "*.mp3"),
            ("WAV Files",   "*.wav"),
            ("OGG Files",   "*.ogg"),
            ("FLAC Files",  "*.flac"),
            ("All Files",   "*.*"),
        ]
    )
    root.destroy()
    return file_path


def play_audio(file_path: str):
    """Play an audio file using available libraries."""

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lower()
    print(f"\nPlaying: {os.path.basename(file_path)}")
    print("Press Ctrl+C to stop.\n")

    # --- Try playsound (simple, works on Python 3.14) ---
    try:
        from playsound import playsound
        playsound(file_path)
        return
    except ImportError:
        pass

    # --- Try pydub (supports FLAC, OGG, MP3 via ffmpeg) ---
    try:
        from pydub import AudioSegment
        from pydub.playback import play
        audio = AudioSegment.from_file(file_path)
        play(audio)
        return
    except ImportError:
        pass

    # --- Fallback: platform-specific system commands ---
    import platform
    system = platform.system()

    if system == "Darwin":       # macOS
        os.system(f'afplay "{file_path}"')
    elif system == "Linux":
        if os.system("which aplay > /dev/null 2>&1") == 0 and ext == ".wav":
            os.system(f'aplay "{file_path}"')
        elif os.system("which mpg123 > /dev/null 2>&1") == 0:
            os.system(f'mpg123 "{file_path}"')
        elif os.system("which ffplay > /dev/null 2>&1") == 0:
            os.system(f'ffplay -nodisp -autoexit "{file_path}"')
        else:
            print("No audio player found. Install playsound or pydub.")
            sys.exit(1)
    elif system == "Windows":
        if ext == ".wav":
            import winsound
            winsound.PlaySound(file_path, winsound.SND_FILENAME)
        else:
            os.startfile(file_path)  # Opens with default media player
    else:
        print(f"Unsupported platform: {system}")
        sys.exit(1)


def main():
    # If a file path is passed as argument, use it; otherwise open file picker
    if len(sys.argv) >= 2:
        file_path = sys.argv[1]
    else:
        print("Opening file picker...")
        file_path = select_file()

    if not file_path:
        print("No file selected. Exiting.")
        sys.exit(0)

    try:
        play_audio(file_path)
        print("Playback finished.")
    except KeyboardInterrupt:
        print("\nPlayback stopped by user.")


if __name__ == "__main__":
    main()
