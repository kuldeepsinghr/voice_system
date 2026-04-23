#!/usr/bin/env python3
"""
ElevenLabs Voice Changer — Step 2 & 3 of the pipeline
Python 3.14+

Pipeline position:
  play_audio.py  →  [voice_clone.py]  →  restore_audio.py

- Output filename is IDENTICAL to input filename
  (so restore_audio.py can auto-find the JSON report)
- Default settings match ElevenLabs UI defaults
- Voice search by name
"""

import sys
import os
import json
import requests

# ── Default settings (matching ElevenLabs UI screenshot) ──────────────
DEFAULT_MODEL       = "eleven_multilingual_sts_v2"
DEFAULT_STABILITY   = 0.65
DEFAULT_SIMILARITY  = 0.75
DEFAULT_STYLE       = 0.10
DEFAULT_BG_NOISE    = False


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

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if key:
        print("  ✅ API key loaded from environment")
        return key

    print("\n  No API key found in .env or environment.")
    print("  Get your key: https://elevenlabs.io/app/settings/api-keys")
    key = input("  Paste your ElevenLabs API key: ").strip()
    if not key:
        print("  No key entered. Exiting.")
        sys.exit(1)

    save = input("  Save to .env for future use? [Y/n]: ").strip().lower()
    if save in ("", "y", "yes"):
        with open(env_path, "a") as f:
            f.write(f"\nELEVENLABS_API_KEY={key}\n")
        print(f"  Saved to {env_path}")

    return key


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
    url  = "https://api.elevenlabs.io/v1/voices"
    resp = requests.get(url, headers={"xi-api-key": api_key}, timeout=30)
    if resp.status_code != 200:
        print(f"  ERROR fetching voices: {resp.status_code} — {resp.text}")
        sys.exit(1)
    return resp.json().get("voices", [])


# ──────────────────────────────────────────────
# VOICE SEARCH + SELECTION
# ──────────────────────────────────────────────
def select_voice(voices: list) -> dict:
    """
    Show full voice list. Let user search by name or pick by number.
    Returns the selected voice dict.
    """
    def display(voice_list, label=""):
        if label:
            print(f"\n  {label}")
        print(f"\n  {'#':<4} {'Name':<32} {'Category':<16} {'Voice ID'}")
        print(f"  {'─'*76}")
        for i, v in enumerate(voice_list, 1):
            print(f"  {i:<4} {v['name']:<32} {v.get('category',''):<16} {v['voice_id']}")

    display(voices, f"Your voice library — {len(voices)} voice(s)")

    while True:
        print()
        query = input(
            "  Type a name to search, a number to select, or press Enter to see all: "
        ).strip()

        # Empty → show all again
        if query == "":
            display(voices)
            continue

        # Number → direct pick from full list
        if query.isdigit():
            idx = int(query)
            if 1 <= idx <= len(voices):
                return voices[idx - 1]
            print(f"  Please enter a number between 1 and {len(voices)}.")
            continue

        # Text → search by name (case-insensitive)
        matches = [v for v in voices if query.lower() in v["name"].lower()]
        if not matches:
            print(f"  No voices found matching '{query}'. Try again.")
            continue

        if len(matches) == 1:
            print(f"  Found: {matches[0]['name']}  ({matches[0]['voice_id']})")
            confirm = input("  Use this voice? [Y/n]: ").strip().lower()
            if confirm in ("", "y", "yes"):
                return matches[0]
            continue

        display(matches, f"{len(matches)} result(s) for '{query}'")
        pick = input("  Enter number from results above (or press Enter to search again): ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(matches):
            return matches[int(pick) - 1]


# ──────────────────────────────────────────────
# ELEVENLABS — SPEECH-TO-SPEECH
# ──────────────────────────────────────────────
def voice_change(
    api_key: str,
    audio_path: str,
    voice_id: str,
    output_path: str,
    model_id: str        = DEFAULT_MODEL,
    stability: float     = DEFAULT_STABILITY,
    similarity: float    = DEFAULT_SIMILARITY,
    style: float         = DEFAULT_STYLE,
    remove_bg: bool      = DEFAULT_BG_NOISE,
):
    url = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}"

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  Uploading  : {os.path.basename(audio_path)}  ({file_size_mb:.1f} MB)")
    print(f"  Model      : {model_id}")
    print(f"  Stability  : {stability}  |  Similarity: {similarity}  |  Style: {style}  |  BG noise: {remove_bg}")
    print(f"  Sending to ElevenLabs...")

    voice_settings = json.dumps({
        "stability":        stability,
        "similarity_boost": similarity,
        "style":            style,
        "use_speaker_boost": True,
    })

    with open(audio_path, "rb") as f:
        resp = requests.post(
            url,
            headers={"xi-api-key": api_key},
            files={"audio": (os.path.basename(audio_path), f, "audio/wav")},
            data={
                "model_id":              model_id,
                "voice_settings":        voice_settings,
                "remove_background_noise": str(remove_bg).lower(),
                "output_format":         "mp3_44100_128",
            },
            timeout=300,
        )

    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        print(f"\n  ERROR {resp.status_code}: {err}")
        return None

    with open(output_path, "wb") as out:
        out.write(resp.content)

    print(f"  ✅ Done  — {len(resp.content)//1024} KB received")
    return output_path


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def fmt_size(path: str) -> str:
    return f"{os.path.getsize(path)/1024/1024:.1f} MB"


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("\n🎙️  ElevenLabs Voice Changer")
    print("─" * 30)
    print("  Pipeline:  play_audio.py → [this] → restore_audio.py")
    print("─" * 30)

    check_dependencies()

    print()
    api_key = load_api_key()

    # ── Step 1: Select cleaned WAV files ──────
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

    # ── Step 2: Fetch voices + search/pick ────
    print("\n  Step 2 — Fetching your ElevenLabs voice library...")
    voices = list_voices(api_key)
    if not voices:
        print("  No voices found. Add voices at: https://elevenlabs.io/app/voice-library")
        sys.exit(1)

    selected_voice = select_voice(voices)
    voice_id   = selected_voice["voice_id"]
    voice_name = selected_voice["name"]
    print(f"\n  ✅ Voice selected: {voice_name}  ({voice_id})")

    # ── Step 3: Settings — defaults applied, user can override ────────
    print(f"\n  Step 3 — Voice settings")
    print(f"  (Defaults match ElevenLabs UI — press Enter to keep each default)\n")

    print(f"  Model options (speech-to-speech only):")
    print(f"    1. eleven_multilingual_sts_v2  (default — multilingual)")
    print(f"    2. eleven_english_sts_v2        (English only — faster)")
    model_pick = input(f"  Model [1]: ").strip()
    model_id = "eleven_english_sts_v2" if model_pick == "2" else DEFAULT_MODEL

    s = input(f"  Stability         [default {DEFAULT_STABILITY}]: ").strip()
    stability = float(s) if s else DEFAULT_STABILITY

    sim = input(f"  Similarity boost  [default {DEFAULT_SIMILARITY}]: ").strip()
    similarity = float(sim) if sim else DEFAULT_SIMILARITY

    sty = input(f"  Style exaggeration [default {DEFAULT_STYLE}]: ").strip()
    style = float(sty) if sty else DEFAULT_STYLE

    bg = input(f"  Remove background noise? [y/N]: ").strip().lower()
    remove_bg = bg in ("y", "yes")

    # ── Step 4: Output folder ─────────────────
    print("\n  Step 4 — Choose output folder:")
    default_dir = os.path.dirname(os.path.abspath(wav_files[0]))
    output_dir  = pick_folder("Choose folder to save voice-changed files", default_dir)
    if not output_dir:
        output_dir = default_dir
        print("  No folder chosen — saving next to source files.")

    # ── Step 5: Process ───────────────────────
    print(f"\n  Processing {len(wav_files)} file(s) with voice '{voice_name}'...\n")
    results = []

    for i, wav_path in enumerate(wav_files, 1):
        print(f"\n  [{i}/{len(wav_files)}] {os.path.basename(wav_path)}")
        print(f"  {'='*55}")

        # ── Output filename = same as input filename ──────────────────
        # This is CRITICAL so restore_audio.py can find the JSON report.
        # e.g.  interview_cleaned.wav  →  interview_cleaned.mp3
        stem        = os.path.splitext(os.path.basename(wav_path))[0]
        output_path = os.path.join(output_dir, stem + ".mp3")

        result = voice_change(
            api_key    = api_key,
            audio_path = wav_path,
            voice_id   = voice_id,
            output_path= output_path,
            model_id   = model_id,
            stability  = stability,
            similarity = similarity,
            style      = style,
            remove_bg  = remove_bg,
        )

        if result:
            results.append(("OK",    wav_path, output_path))
            print(f"  Saved  : {output_path}")
        else:
            results.append(("ERROR", wav_path, "API call failed"))

    # ── Summary ───────────────────────────────
    ok   = [r for r in results if r[0] == "OK"]
    errs = [r for r in results if r[0] == "ERROR"]

    print(f"\n\n{'='*55}")
    print(f"  SUMMARY — {len(wav_files)} file(s) processed")
    print(f"  {'─'*50}")
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
