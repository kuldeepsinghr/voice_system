#!/usr/bin/env python3
"""
Full Pipeline — Dead Air Remove → Voice Clone → Restore
Python 3.14+

User does:
  1. Pick original WAV file(s)         — once
  2. Pick a voice from library         — once
  3. Press Enter through settings      — once

Script does automatically:
  - Remove dead air  → saves  filename_cleaned.wav + filename_cleaned_report.json
  - Voice clone      → saves  filename_cleaned.mp3  (same folder, same stem)
  - Restore          → saves  filename_restored.wav (same folder)
  - Opens output folder at the end
"""

import sys
import os
import json
import requests
from datetime import datetime


# ══════════════════════════════════════════════
# DEFAULTS
# ══════════════════════════════════════════════
DEFAULT_MODEL      = "eleven_multilingual_sts_v2"
DEFAULT_STABILITY  = 0.65
DEFAULT_SIMILARITY = 0.75
DEFAULT_STYLE      = 0.10
DEFAULT_BG_NOISE   = False


# ══════════════════════════════════════════════
# DEPENDENCIES
# ══════════════════════════════════════════════
def check_dependencies():
    missing = []
    for pkg in ("numpy", "soundfile", "requests"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"ERROR: Missing packages: {', '.join(missing)}")
        print(f"Run:  pip install {' '.join(missing)}")
        sys.exit(1)
    print("  ✅ numpy, soundfile, requests — all ready")


# ══════════════════════════════════════════════
# API KEY
# ══════════════════════════════════════════════
def load_api_key() -> str:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("ELEVENLABS_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    print("  ✅ API key loaded from .env")
                    return key
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if key:
        print("  ✅ API key from environment")
        return key
    print("\n  No API key found.")
    print("  Get yours: https://elevenlabs.io/app/settings/api-keys")
    key = input("  Paste API key: ").strip()
    if not key:
        sys.exit(1)
    save = input("  Save to .env? [Y/n]: ").strip().lower()
    if save in ("", "y", "yes"):
        with open(env_path, "a") as f:
            f.write(f"\nELEVENLABS_API_KEY={key}\n")
        print(f"  Saved to .env")
    return key


# ══════════════════════════════════════════════
# FILE / FOLDER PICKERS
# ══════════════════════════════════════════════
def pick_files(title, filetypes):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    paths = filedialog.askopenfilenames(title=title, filetypes=filetypes)
    root.destroy()
    return list(paths)

def open_folder(path):
    import platform
    s = platform.system()
    if s == "Windows":  os.system(f'explorer /select,"{path}"')
    elif s == "Darwin": os.system(f'open -R "{path}"')
    else:               os.system(f'xdg-open "{os.path.dirname(os.path.abspath(path))}"')



# ══════════════════════════════════════════════
# SAVE DIALOG
# ══════════════════════════════════════════════
def save_dialog(default_name, initial_dir):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    path = filedialog.asksaveasfilename(
        title="Save Restored Audio As",
        initialdir=initial_dir,
        initialfile=default_name,
        defaultextension=".wav",
        filetypes=[("WAV Files", "*.wav"), ("All Files", "*.*")],
    )
    root.destroy()
    return path

# ══════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════
def fmt(s):
    m, s = divmod(int(s), 60); h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")

def to_ts(s):
    h=int(s//3600); m=int((s%3600)//60); sec=int(s%60); ms=int((s%1)*1000)
    return f"{h:02d}:{m:02d}:{sec:02d}.{ms:03d}"

def ts_to_sec(ts):
    h,m,rest=ts.split(":"); s,ms=rest.split(".")
    return int(h)*3600+int(m)*60+int(s)+int(ms)/1000

def banner(title, i=None, total=None):
    prefix = f"[{i}/{total}] " if i is not None else ""
    print(f"\n{'─'*55}")
    print(f"  {prefix}{title}")
    print(f"{'─'*55}")


# ══════════════════════════════════════════════
# STEP 1 — REMOVE DEAD AIR
# ══════════════════════════════════════════════
def remove_dead_air(file_path, min_silence_ms=700, padding_ms=200):
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(file_path, dtype="float32")
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    orig_dur = len(mono) / sr

    # Adaptive threshold
    frame_ms   = 10
    frame_size = int(sr * frame_ms / 1000)
    num_frames = len(mono) // frame_size
    rms = np.array([
        np.sqrt(np.mean(mono[i*frame_size:(i+1)*frame_size]**2))
        for i in range(num_frames)
    ])
    noise_floor = float(np.percentile(rms, 10))
    threshold   = noise_floor * 8.0

    print(f"  Duration       : {fmt(orig_dur)}")
    print(f"  Noise floor    : {noise_floor:.6f}  threshold: {threshold:.6f}")

    is_speech          = rms > threshold
    min_sil_frames     = max(1, min_silence_ms // frame_ms)
    pad_frames         = max(1, padding_ms     // frame_ms)
    speech_chunks      = []
    in_speech = start = silence_count = 0

    for i, sp in enumerate(is_speech):
        if sp:
            if not in_speech:
                start = max(0, i - pad_frames); in_speech = True
            silence_count = 0
        else:
            if in_speech:
                silence_count += 1
                if silence_count >= min_sil_frames:
                    speech_chunks.append((start, min(num_frames, i + pad_frames)))
                    in_speech = silence_count = 0
    if in_speech:
        speech_chunks.append((start, num_frames))

    if not speech_chunks:
        print("  WARNING: No speech detected — skipping file.")
        return None, None

    # Build removed segments
    removed = []; idx = 1

    def add(sf2, ef):
        nonlocal idx
        ss = (sf2*frame_size)/sr; es = (ef*frame_size)/sr; d = es-ss
        if d > 0.1:
            removed.append({"index":idx,"start_sec":round(ss,3),"end_sec":round(es,3),
                            "duration_sec":round(d,3),"start_timestamp":to_ts(ss),"end_timestamp":to_ts(es)})
            idx += 1

    if speech_chunks[0][0] > 0:            add(0, speech_chunks[0][0])
    for i in range(len(speech_chunks)-1):  add(speech_chunks[i][1], speech_chunks[i+1][0])
    if speech_chunks[-1][1] < num_frames:  add(speech_chunks[-1][1], num_frames)

    # Crossfade stitch
    sample_chunks = []; last = 0
    for fs, fe in speech_chunks:
        s2 = max(int(fs*frame_size), last); e2 = int(fe*frame_size)
        if e2 > s2: sample_chunks.append((s2, e2)); last = e2

    fade = int(sr * 8 / 1000)
    out  = audio[sample_chunks[0][0]:sample_chunks[0][1]].copy()
    for s2, e2 in sample_chunks[1:]:
        seg = audio[s2:e2]
        if len(out) > fade and len(seg) > fade:
            fo = np.linspace(1,0,fade); fi = np.linspace(0,1,fade)
            out[-fade:] = out[-fade:]*fo + seg[:fade]*fi
            out = np.concatenate([out, seg[fade:]], axis=0)
        else:
            out = np.concatenate([out, seg], axis=0)

    cleaned_dur = len(out) / sr
    removed_s   = orig_dur - cleaned_dur
    print(f"  Removed        : {fmt(removed_s)}  ({removed_s/orig_dur*100:.1f}%)")
    print(f"  Cleaned dur    : {fmt(cleaned_dur)}")

    # Save cleaned WAV + JSON — in same folder as source
    base         = os.path.splitext(file_path)[0]
    cleaned_path = base + "_cleaned.wav"
    json_path    = base + "_cleaned_report.json"

    sf.write(cleaned_path, out, sr)

    report = {
        "generated_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file":        os.path.abspath(file_path),
        "output_file":        os.path.abspath(cleaned_path),
        "sample_rate_hz":     sr,
        "noise_floor_rms":    f"{noise_floor:.8f}",
        "auto_threshold_rms": f"{threshold:.8f}",
        "min_silence_ms":     min_silence_ms,
        "padding_ms":         padding_ms,
        "original_duration":  to_ts(orig_dur),
        "cleaned_duration":   to_ts(cleaned_dur),
        "total_removed":      to_ts(removed_s),
        "removed_percent":    f"{removed_s/orig_dur*100:.1f}%",
        "segments_removed":   len(removed),
        "removed_segments":   removed,
    }
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"  ✅ Cleaned WAV : {os.path.basename(cleaned_path)}")
    print(f"  ✅ JSON report : {os.path.basename(json_path)}")
    return cleaned_path, json_path


# ══════════════════════════════════════════════
# STEP 2 — ELEVENLABS VOICE CHANGE
# ══════════════════════════════════════════════
def list_voices(api_key):
    r = requests.get("https://api.elevenlabs.io/v1/voices",
                     headers={"xi-api-key": api_key}, timeout=30)
    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text}"); sys.exit(1)
    return r.json().get("voices", [])

def select_voice(voices):
    print(f"\n  {'#':<4} {'Name':<32} {'Category':<16} {'Voice ID'}")
    print(f"  {'─'*76}")
    for i, v in enumerate(voices, 1):
        print(f"  {i:<4} {v['name']:<32} {v.get('category',''):<16} {v['voice_id']}")

    while True:
        q = input("\n  Search by name or enter number: ").strip()
        if q.isdigit() and 1 <= int(q) <= len(voices):
            return voices[int(q)-1]
        matches = [v for v in voices if q.lower() in v["name"].lower()]
        if len(matches) == 1:
            print(f"  Found: {matches[0]['name']}")
            if input("  Use this? [Y/n]: ").strip().lower() in ("","y","yes"):
                return matches[0]
        elif len(matches) > 1:
            for i,v in enumerate(matches,1):
                print(f"  {i}. {v['name']}  ({v['voice_id']})")
            p = input("  Pick number: ").strip()
            if p.isdigit() and 1 <= int(p) <= len(matches):
                return matches[int(p)-1]
        else:
            print(f"  No match for '{q}'. Try again.")

def voice_change_api(api_key, audio_path, voice_id, output_path,
                     model_id, stability, similarity, style, remove_bg):
    url = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}"
    mb  = os.path.getsize(audio_path)/1024/1024
    print(f"  Uploading      : {os.path.basename(audio_path)}  ({mb:.1f} MB)")
    print(f"  Sending to ElevenLabs...")

    with open(audio_path, "rb") as f:
        r = requests.post(url,
            headers={"xi-api-key": api_key},
            files={"audio": (os.path.basename(audio_path), f, "audio/wav")},
            data={
                "model_id":              model_id,
                "voice_settings":        json.dumps({
                    "stability": stability, "similarity_boost": similarity,
                    "style": style, "use_speaker_boost": True,
                }),
                "remove_background_noise": str(remove_bg).lower(),
                "output_format":         "mp3_44100_128",
            },
            timeout=300,
        )

    if r.status_code != 200:
        try:    err = r.json()
        except: err = r.text
        print(f"  ERROR {r.status_code}: {err}")
        return None, 0

    with open(output_path, "wb") as f:
        f.write(r.content)

    # ElevenLabs returns credit info in response headers
    used      = int(r.headers.get("xi-credits-used",      r.headers.get("character-cost", 0)))
    remaining = r.headers.get("xi-credits-remaining", r.headers.get("character-quota-remaining", None))

    print(f"  ✅ Voice clone : {os.path.basename(output_path)}  ({len(r.content)//1024} KB)")
    print(f"  💳 Credits used: {used:,}" + (f"  |  remaining: {int(remaining):,}" if remaining else ""))

    return output_path, used


# ══════════════════════════════════════════════
# STEP 3 — RESTORE ORIGINAL LENGTH
# ══════════════════════════════════════════════
def restore_audio(voiced_mp3, json_path, save_path=None):
    import numpy as np
    import soundfile as sf
    import tempfile, subprocess, shutil

    # Convert MP3 → temp WAV
    tmp_wav = tempfile.mktemp(suffix=".wav")
    converted = False

    if shutil.which("ffmpeg"):
        r = subprocess.run(["ffmpeg","-y","-i",voiced_mp3,tmp_wav],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        converted = r.returncode == 0
    if not converted:
        try:
            import static_ffmpeg; static_ffmpeg.add_paths()
            if shutil.which("ffmpeg"):
                r = subprocess.run(["ffmpeg","-y","-i",voiced_mp3,tmp_wav],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                converted = r.returncode == 0
        except ImportError:
            pass
    if not converted:
        print("  ERROR: ffmpeg not found. Run:  pip install static-ffmpeg")
        return None

    with open(json_path) as f:
        report = json.load(f)

    sr             = report["sample_rate_hz"]
    original_dur_s = ts_to_sec(report["original_duration"])
    segments       = sorted(report["removed_segments"], key=lambda x: x["start_sec"])

    cleaned, file_sr = sf.read(tmp_wav, dtype="float32")
    os.remove(tmp_wav)

    if file_sr != sr:
        sr = file_sr

    is_stereo    = cleaned.ndim == 2
    output_parts = []
    cleaned_pos  = 0
    timeline_pos = 0.0

    for seg in segments:
        speech_dur = seg["start_sec"] - timeline_pos
        if speech_dur > 0.001:
            n   = int(round(speech_dur * sr))
            end = min(cleaned_pos + n, len(cleaned))
            output_parts.append(cleaned[cleaned_pos:end])
            cleaned_pos = end
        sil_n = int(round((seg["end_sec"] - seg["start_sec"]) * sr))
        if sil_n > 0:
            shape = (sil_n, cleaned.shape[1]) if is_stereo else (sil_n,)
            output_parts.append(np.zeros(shape, dtype="float32"))
        timeline_pos = seg["end_sec"]

    remaining = original_dur_s - timeline_pos
    if remaining > 0.001 and cleaned_pos < len(cleaned):
        end = min(cleaned_pos + int(round(remaining * sr)), len(cleaned))
        output_parts.append(cleaned[cleaned_pos:end])

    restored     = np.concatenate(output_parts, axis=0)
    restored_dur = len(restored) / sr
    diff_ms      = abs(restored_dur - original_dur_s) * 1000

    print(f"  Restored dur   : {fmt(restored_dur)}")
    print(f"  Expected dur   : {fmt(original_dur_s)}")
    print(f"  Diff           : {diff_ms:.1f} ms  {'✅' if diff_ms < 100 else '⚠️'}")

    # Save to user-chosen path, or default next to source
    if not save_path:
        stem     = os.path.splitext(voiced_mp3)[0]
        save_path = stem.replace("_cleaned", "_restored") + ".wav"
    sf.write(save_path, restored, sr)
    print(f"  Restored saved: {os.path.basename(save_path)}")
    return save_path


# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════
def main():
    print("\n  Full Voice Pipeline")
    print("  Step 1: Pick files -> Step 2: Voice clone -> Step 3: Restore")
    print("-" * 55)

    check_dependencies()

    # ── API key ───────────────────────────────
    print()
    api_key = load_api_key()

    # ── STEP 1: Pick source WAV files ─────────
    print("\n  Step 1 — Select original WAV file(s)  [hold Ctrl for multiple]:")
    wav_files = pick_files(
        "Select original WAV file(s)",
        [("WAV Files", "*.wav"), ("All Files", "*.*")]
    )
    if not wav_files:
        print("  No files selected. Exiting.")
        sys.exit(0)

    wav_files = [f for f in wav_files if f.lower().endswith(".wav")]
    if not wav_files:
        print("  No valid WAV files. Exiting.")
        sys.exit(0)

    print(f"\n  {len(wav_files)} file(s) selected:")
    for f in wav_files:
        print(f"    - {os.path.basename(f)}")

    # ── STEP 2: Pick voice from ElevenLabs ────
    print("\n  Step 2 — Fetching your ElevenLabs voice library...")
    voices = list_voices(api_key)
    if not voices:
        print("  No voices found. Add voices at: https://elevenlabs.io/app/voice-library")
        sys.exit(1)
    selected   = select_voice(voices)
    voice_id   = selected["voice_id"]
    voice_name = selected["name"]
    print(f"\n  Voice selected: {voice_name}")

    # ── Voice settings ────────────────────────
    print(f"\n  Voice settings (press Enter to keep defaults):")
    print(f"    1. {DEFAULT_MODEL}  (default)")
    print(f"    2. eleven_english_sts_v2  (English only)")
    model_id   = "eleven_english_sts_v2" \
                 if input("  Model [1]: ").strip() == "2" else DEFAULT_MODEL
    s   = input(f"  Stability          [{DEFAULT_STABILITY}]: ").strip()
    sim = input(f"  Similarity boost   [{DEFAULT_SIMILARITY}]: ").strip()
    sty = input(f"  Style exaggeration [{DEFAULT_STYLE}]: ").strip()
    bg  = input(f"  Remove BG noise?   [y/N]: ").strip().lower()
    stability  = float(s)   if s   else DEFAULT_STABILITY
    similarity = float(sim) if sim else DEFAULT_SIMILARITY
    style      = float(sty) if sty else DEFAULT_STYLE
    remove_bg  = bg in ("y", "yes")

    # ── Run pipeline per file ──────────────────
    print(f"\n  Running pipeline on {len(wav_files)} file(s)...\n")
    results = []
    total_credits = 0

    for i, wav_path in enumerate(wav_files, 1):
        banner(os.path.basename(wav_path), i, len(wav_files))
        src_dir  = os.path.dirname(os.path.abspath(wav_path))
        src_stem = os.path.splitext(os.path.basename(wav_path))[0]

        try:
            # ── Step 1: Remove dead air ───────
            print(f"\n  > Step 1 — Removing dead air")
            cleaned_path, json_path = remove_dead_air(wav_path)
            if not cleaned_path:
                results.append(("SKIP", wav_path, None, "No speech detected", 0))
                continue

            # ── Step 2: Voice clone ───────────
            print(f"\n  > Step 2 — Voice cloning  [{voice_name}]")
            voiced_path = os.path.join(src_dir, src_stem + "_cleaned.mp3")
            result, credits_used = voice_change_api(
                api_key     = api_key,
                audio_path  = cleaned_path,
                voice_id    = voice_id,
                output_path = voiced_path,
                model_id    = model_id,
                stability   = stability,
                similarity  = similarity,
                style       = style,
                remove_bg   = remove_bg,
            )
            total_credits += credits_used
            if not result:
                results.append(("ERROR", wav_path, None, "ElevenLabs API failed", 0))
                continue

            # ── Step 3: Restore ───────────────
            print(f"\n  > Step 3 — Restoring original length")

            # Ask user where to save the restored file
            default_save_name = src_stem + "_restored.wav"
            print(f"  Opening save dialog for restored file...")
            save_path = save_dialog(default_save_name, src_dir)

            if not save_path:
                # No dialog choice — auto-save next to source
                save_path = os.path.join(src_dir, default_save_name)
                print(f"  No location chosen — saving to source folder.")

            restored_path = restore_audio(voiced_path, json_path, save_path)
            if not restored_path:
                results.append(("ERROR", wav_path, None, "Restore failed", credits_used))
                continue

            results.append(("OK", wav_path, restored_path, "", credits_used))

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append(("ERROR", wav_path, None, str(e), 0))

    # ── Summary ───────────────────────────────
    ok   = [r for r in results if r[0] == "OK"]
    errs = [r for r in results if r[0] != "OK"]

    print(f"\n\n" + "="*55)
    print(f"  PIPELINE COMPLETE — {len(wav_files)} file(s)")
    print(f"  " + "-"*50)
    for status, src, out, msg, credits in results:
        icon = "[OK]" if status == "OK" else ("[SKIP]" if status == "SKIP" else "[ERR]")
        print(f"\n  {icon} {os.path.basename(src)}")
        if status == "OK":
            stem = os.path.splitext(os.path.basename(src))[0]
            print(f"       {stem}_cleaned.wav         - dead air removed")
            print(f"       {stem}_cleaned_report.json - cut map")
            print(f"       {stem}_cleaned.mp3         - voice cloned")
            print(f"       {os.path.basename(out)}  <-- final restored output")
            print(f"       Saved to: {os.path.dirname(out)}")
            if credits:
                print(f"       💳 Credits used: {credits:,}")
        else:
            print(f"       {msg}")

    print(f"\n  Done: {len(ok)} complete  |  {len(errs)} failed")
    if total_credits:
        print(f"  💳 Total credits used this run: {total_credits:,}")
    print("="*55 + "\n")

    if ok:
        open_folder(ok[0][2])

    input("  Press Enter to exit...")


if __name__ == "__main__":
    main()