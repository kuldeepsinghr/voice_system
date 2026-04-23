#!/usr/bin/env python3
"""
ElevenLabs Voice Changer — Step 2 & 3 of the pipeline
Python 3.14+

Pipeline position:
  play_audio.py  →  [voice_clone.py]  →  restore_audio.py

What this script does:
  1. Takes the cleaned WAV (output of play_audio.py)
  2. Lists your ElevenLabs voice library so you can pick a voice
  3. Sends the audio to ElevenLabs Speech-to-Speech API
  4. Saves the voice-changed MP3 next to the input file

Dependencies:
  pip install requests python-dotenv
"""

import sys
import os
import json
import requests


# ──────────────────────────────────────────────
# DEPENDENCIES
# ──────────────────────────────────────────────
def check_dependencies():
    missing = []
    for pkg in ("requests",):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"ERROR: Missing: {', '.join(missing)}")
        print(f"Run:  pip install {' '.join(missing)}")
        sys.exit(1)
    print("  ✅ requests ready")


# ──────────────────────────────────────────────
# LOAD API KEY
# ──────────────────────────────────────────────
def load_api_key() -> str:
    """
    Load API key from:
      1. .env file in same folder as this script
      2. Environment variable ELEVENLABS_API_KEY
      3. User prompt (typed in terminal)
    """
    # Try .env file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("ELEVENLABS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        print("  ✅ API key loaded from .env")
                        return key

    # Try environment variable
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if key:
        print("  ✅ API key loaded from environment")
        return key

    # Ask user
    print("\n  No API key found in .env or environment.")
    print("  Get your key from: https://elevenlabs.io/app/settings/api-keys")
    key = input("  Paste your ElevenLabs API key: ").strip()
    if not key:
        print("  No key entered. Exiting.")
        sys.exit(1)

    # Offer to save it
    save = input("  Save to .env for future use? [Y/n]: ").strip().lower()
    if save in ("", "y", "yes"):
        with open(env_path, "a") as f:
            f.write(f"\nELEVENLABS_API_KEY={key}\n")
        print(f"  Saved to {env_path}")

    return key


# ──────────────────────────────────────────────
# FILE PICKERS
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

def pick_folder(title: str, initial_dir: str) -> str:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title=title, initialdir=initial_dir)
    root.destroy()
    return folder

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
# ELEVENLABS — LIST VOICES
# ──────────────────────────────────────────────
def list_voices(api_key: str) -> list:
    """Fetch all voices in the user's ElevenLabs voice library."""
    url  = "https://api.elevenlabs.io/v1/voices"
    resp = requests.get(url, headers={"xi-api-key": api_key}, timeout=30)

    if resp.status_code != 200:
        print(f"  ERROR fetching voices: {resp.status_code} — {resp.text}")
        sys.exit(1)

    voices = resp.json().get("voices", [])
    return voices


# ──────────────────────────────────────────────
# ELEVENLABS — VOICE CHANGER (Speech-to-Speech)
# ──────────────────────────────────────────────
def voice_change(
    api_key: str,
    audio_path: str,
    voice_id: str,
    output_path: str,
    model_id: str = "eleven_english_sts_v2",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    remove_bg_noise: bool = False,
):
    """
    Send a WAV file to ElevenLabs Speech-to-Speech and save the result.
    Max file size: 50 MB. Max duration: ~5 minutes (ElevenLabs limit).
    """
    url = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}"

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  Uploading        : {os.path.basename(audio_path)}  ({file_size_mb:.1f} MB)")
    print(f"  Voice ID         : {voice_id}")
    print(f"  Model            : {model_id}")
    print(f"  Stability        : {stability}")
    print(f"  Similarity boost : {similarity_boost}")
    print(f"  Remove BG noise  : {remove_bg_noise}")
    print(f"  Sending to ElevenLabs...")

    voice_settings = json.dumps({
        "stability":        stability,
        "similarity_boost": similarity_boost,
    })

    with open(audio_path, "rb") as f:
        files = {"audio": (os.path.basename(audio_path), f, "audio/wav")}
        data  = {
            "model_id":             model_id,
            "voice_settings":       voice_settings,
            "remove_background_noise": str(remove_bg_noise).lower(),
            "output_format":        "mp3_44100_128",
        }
        headers = {"xi-api-key": api_key}

        resp = requests.post(url, headers=headers, files=files, data=data, timeout=300)

    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        print(f"\n  ERROR {resp.status_code}: {err}")
        return None

    # Save the returned MP3
    with open(output_path, "wb") as out:
        out.write(resp.content)

    size_kb = len(resp.content) / 1024
    print(f"  ✅ Done  — received {size_kb:.0f} KB")
    return output_path


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def fmt_size(path: str) -> str:
    mb = os.path.getsize(path) / (1024 * 1024)
    return f"{mb:.1f} MB"


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("\n🎙️  ElevenLabs Voice Changer")
    print("─" * 30)
    print("  Pipeline:  play_audio.py → [this] → restore_audio.py")
    print("─" * 30)

    check_dependencies()

    # ── API key ───────────────────────────────
    print()
    api_key = load_api_key()

    # ── Step 1: Select cleaned audio files ────
    print("\n  Step 1 — Select CLEANED WAV file(s)  [hold Ctrl for multiple]:")
    audio_files = pick_files(
        "Select Cleaned WAV file(s)",
        [("WAV Files", "*.wav"), ("All Files", "*.*")]
    )
    if not audio_files:
        print("  No files selected. Exiting.")
        sys.exit(0)

    wav_files = [f for f in audio_files if f.lower().endswith(".wav")]
    if not wav_files:
        print("  No valid WAV files selected. Exiting.")
        sys.exit(0)

    print(f"\n  {len(wav_files)} file(s) selected:")
    for f in wav_files:
        print(f"    • {os.path.basename(f)}  ({fmt_size(f)})")

    # ── Step 2: Fetch + pick voice ────────────
    print("\n  Step 2 — Fetching your ElevenLabs voice library...")
    voices = list_voices(api_key)

    if not voices:
        print("  No voices found in your library.")
        print("  Add voices at: https://elevenlabs.io/app/voice-library")
        sys.exit(1)

    print(f"\n  Found {len(voices)} voice(s):\n")
    print(f"  {'#':<4} {'Name':<30} {'Category':<16} {'Voice ID'}")
    print(f"  {'─'*75}")
    for i, v in enumerate(voices, 1):
        print(f"  {i:<4} {v['name']:<30} {v.get('category',''):<16} {v['voice_id']}")

    print()
    while True:
        choice = input("  Enter voice number to use: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(voices):
            selected_voice = voices[int(choice) - 1]
            break
        print(f"  Please enter a number between 1 and {len(voices)}.")

    voice_id   = selected_voice["voice_id"]
    voice_name = selected_voice["name"]
    print(f"\n  Selected: {voice_name}  ({voice_id})")

    # ── Step 3: Settings ──────────────────────
    print("\n  Step 3 — Voice settings  (press Enter to use defaults)")

    stab_input = input("  Stability [0.0–1.0, default 0.5]: ").strip()
    stability  = float(stab_input) if stab_input else 0.5

    sim_input        = input("  Similarity boost [0.0–1.0, default 0.75]: ").strip()
    similarity_boost = float(sim_input) if sim_input else 0.75

    bg_input        = input("  Remove background noise? [y/N]: ").strip().lower()
    remove_bg_noise = bg_input in ("y", "yes")

    # ── Step 4: Output folder ─────────────────
    print("\n  Step 4 — Choose output folder:")
    default_dir = os.path.dirname(os.path.abspath(wav_files[0]))
    output_dir  = pick_folder("Choose folder to save voice-changed files", default_dir)
    if not output_dir:
        output_dir = default_dir
        print(f"  No folder chosen — saving next to source files.")

    # ── Step 5: Process each file ─────────────
    print(f"\n  Processing {len(wav_files)} file(s) with voice '{voice_name}'...\n")
    results = []

    for i, wav_path in enumerate(wav_files, 1):
        print(f"\n  [{i}/{len(wav_files)}] {os.path.basename(wav_path)}")
        print(f"  {'='*55}")

        stem        = os.path.splitext(os.path.basename(wav_path))[0]
        out_name    = f"{stem}_voiced_{voice_name.replace(' ', '_')}.mp3"
        output_path = os.path.join(output_dir, out_name)

        result = voice_change(
            api_key      = api_key,
            audio_path   = wav_path,
            voice_id     = voice_id,
            output_path  = output_path,
            stability    = stability,
            similarity_boost = similarity_boost,
            remove_bg_noise  = remove_bg_noise,
        )

        if result:
            results.append(("OK",    wav_path, output_path))
            print(f"  Saved to : {output_path}")
        else:
            results.append(("ERROR", wav_path, "API call failed"))

    # ── Summary ───────────────────────────────
    print(f"\n\n{'='*55}")
    print(f"  SUMMARY — {len(wav_files)} file(s) processed")
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

    print(f"\n  Done : {len(ok)} voiced  |  {len(errs)} errors")
    print(f"\n  Next step → run restore_audio.py with the MP3 output(s)")
    print(f"{'='*55}\n")

    if ok:
        open_folder(ok[0][2])

    input("  Press Enter to exit...")


if __name__ == "__main__":
    main()