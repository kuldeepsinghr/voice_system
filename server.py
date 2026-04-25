#!/usr/bin/env python3
"""
Local Flask server — bridges the UI (voice_cutter_ui.html) to the Python scripts.

Run:  python server.py
Then: opens http://localhost:5000 automatically in your browser

Endpoints:
  GET  /api/voices              → list ElevenLabs voices
  POST /api/run/deadair         → remove dead air from uploaded WAV
  POST /api/run/clone           → voice clone via ElevenLabs STS
  POST /api/run/restore         → restore original audio length
  POST /api/run/pipeline        → full pipeline (all 3 steps)
  GET  /api/status/<job_id>     → SSE stream of live log output
  GET  /download/<filename>     → download a processed file
"""

import os
import sys
import json
import uuid
import threading
import queue
import time
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# ── check flask ──────────────────────────────
try:
    from flask import Flask, request, jsonify, Response, send_file
    from flask_cors import CORS
except ImportError:
    print("\n[ERROR] Flask not installed.")
    print("Run:  pip install flask flask-cors")
    sys.exit(1)

try:
    import numpy as np
    import soundfile as sf
    import requests as req_lib
except ImportError as e:
    print(f"\n[ERROR] Missing dependency: {e}")
    print("Run:  pip install numpy soundfile requests")
    sys.exit(1)


# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════
BASE_DIR    = Path(__file__).parent
OUTPUT_DIR  = BASE_DIR / "output"
UPLOAD_DIR  = BASE_DIR / "uploads"
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

DEFAULT_MODEL      = "eleven_multilingual_sts_v2"
DEFAULT_STABILITY  = 0.65
DEFAULT_SIMILARITY = 0.75
DEFAULT_STYLE      = 0.10


# ══════════════════════════════════════════════
# API KEY
# ══════════════════════════════════════════════
def load_api_key() -> str:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    return os.environ.get("ELEVENLABS_API_KEY", "")


# ══════════════════════════════════════════════
# JOB MANAGER  (SSE log streaming)
# ══════════════════════════════════════════════
jobs: dict[str, dict] = {}

def new_job() -> str:
    jid = str(uuid.uuid4())[:8]
    jobs[jid] = {"queue": queue.Queue(), "done": False, "result": None}
    return jid

def job_log(jid, msg, level="info"):
    if jid in jobs:
        jobs[jid]["queue"].put({"msg": msg, "level": level, "ts": time.time()})

def job_done(jid, result=None):
    if jid in jobs:
        jobs[jid]["done"]   = True
        jobs[jid]["result"] = result
        jobs[jid]["queue"].put(None)  # sentinel


# ══════════════════════════════════════════════
# HELPERS (copied from pipeline.py)
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


# ══════════════════════════════════════════════
# STEP 1 — REMOVE DEAD AIR
# ══════════════════════════════════════════════
def run_deadair(wav_path: str, out_path: str, jid: str,
                min_silence_ms=700, padding_ms=200):
    job_log(jid, f"Loading: {Path(wav_path).name}")

    audio, sr = sf.read(wav_path, dtype="float32")
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    orig_dur = len(mono) / sr

    job_log(jid, f"Duration: {fmt(orig_dur)}  |  Sample rate: {sr} Hz")

    frame_ms   = 10
    frame_size = int(sr * frame_ms / 1000)
    num_frames = len(mono) // frame_size
    rms = np.array([
        np.sqrt(np.mean(mono[i*frame_size:(i+1)*frame_size]**2))
        for i in range(num_frames)
    ])
    noise_floor = float(np.percentile(rms, 10))
    threshold   = noise_floor * 8.0
    job_log(jid, f"Noise floor: {noise_floor:.6f}  |  Threshold: {threshold:.6f}")

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
        job_log(jid, "WARNING: No speech detected.", "warn")
        return None, None

    removed = []; idx = 1
    def add(sf2, ef):
        nonlocal idx
        ss=(sf2*frame_size)/sr; es=(ef*frame_size)/sr; d=es-ss
        if d>0.1:
            removed.append({"index":idx,"start_sec":round(ss,3),"end_sec":round(es,3),
                            "duration_sec":round(d,3),"start_timestamp":to_ts(ss),"end_timestamp":to_ts(es)})
            idx+=1

    if speech_chunks[0][0] > 0:            add(0, speech_chunks[0][0])
    for i in range(len(speech_chunks)-1):  add(speech_chunks[i][1], speech_chunks[i+1][0])
    if speech_chunks[-1][1] < num_frames:  add(speech_chunks[-1][1], num_frames)

    sample_chunks = []; last = 0
    for fs, fe in speech_chunks:
        s2=max(int(fs*frame_size),last); e2=int(fe*frame_size)
        if e2>s2: sample_chunks.append((s2,e2)); last=e2

    fade = int(sr*8/1000)
    out  = audio[sample_chunks[0][0]:sample_chunks[0][1]].copy()
    for s2, e2 in sample_chunks[1:]:
        seg = audio[s2:e2]
        if len(out)>fade and len(seg)>fade:
            fo=np.linspace(1,0,fade); fi=np.linspace(0,1,fade)
            out[-fade:]=out[-fade:]*fo+seg[:fade]*fi
            out=np.concatenate([out,seg[fade:]],axis=0)
        else:
            out=np.concatenate([out,seg],axis=0)

    cleaned_dur = len(out)/sr
    removed_s   = orig_dur-cleaned_dur
    job_log(jid, f"Removed: {fmt(removed_s)} ({removed_s/orig_dur*100:.1f}%)  |  New duration: {fmt(cleaned_dur)}", "ok")

    sf.write(out_path, out, sr)

    json_path = out_path.replace("_cleaned.wav","_cleaned_report.json")
    report = {
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file":       str(wav_path),
        "output_file":       str(out_path),
        "sample_rate_hz":    sr,
        "original_duration": to_ts(orig_dur),
        "cleaned_duration":  to_ts(cleaned_dur),
        "total_removed":     to_ts(removed_s),
        "removed_percent":   f"{removed_s/orig_dur*100:.1f}%",
        "segments_removed":  len(removed),
        "removed_segments":  removed,
    }
    with open(json_path,"w") as f: json.dump(report, f, indent=2)
    job_log(jid, f"Saved: {Path(out_path).name}  +  report.json", "ok")
    return out_path, json_path


# ══════════════════════════════════════════════
# STEP 2 — VOICE CLONE
# ══════════════════════════════════════════════
def run_clone(wav_path, voice_id, out_path, jid,
              model_id=DEFAULT_MODEL, stability=DEFAULT_STABILITY,
              similarity=DEFAULT_SIMILARITY, style=DEFAULT_STYLE,
              remove_bg=False):
    api_key = load_api_key()
    if not api_key:
        job_log(jid, "ERROR: No API key found in .env", "err")
        return None

    mb = os.path.getsize(wav_path)/1024/1024
    job_log(jid, f"Uploading {Path(wav_path).name} ({mb:.1f} MB) to ElevenLabs...")

    url = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}"
    with open(wav_path,"rb") as f:
        r = req_lib.post(url,
            headers={"xi-api-key": api_key},
            files={"audio":(Path(wav_path).name, f, "audio/wav")},
            data={
                "model_id":     model_id,
                "voice_settings": json.dumps({
                    "stability":stability,"similarity_boost":similarity,
                    "style":style,"use_speaker_boost":True
                }),
                "remove_background_noise": str(remove_bg).lower(),
                "output_format": "mp3_44100_128",
            },
            timeout=300,
        )

    if r.status_code != 200:
        try:    err = r.json()
        except: err = r.text
        job_log(jid, f"ERROR {r.status_code}: {err}", "err")
        return None

    with open(out_path,"wb") as f: f.write(r.content)

    # Parse credits from response headers
    credits_used = r.headers.get("xi-credits-used","?")
    credits_rem  = r.headers.get("xi-credits-remaining","?")
    job_log(jid, f"Saved: {Path(out_path).name}  ({len(r.content)//1024} KB)", "ok")
    job_log(jid, f"Credits used: {credits_used}  |  Remaining: {credits_rem}", "warn")
    return out_path, credits_used, credits_rem


# ══════════════════════════════════════════════
# STEP 3 — RESTORE
# ══════════════════════════════════════════════
def run_restore(mp3_path, json_path, out_path, jid):
    import subprocess

    # Convert MP3 → temp WAV
    tmp_wav = tempfile.mktemp(suffix=".wav")
    converted = False
    if shutil.which("ffmpeg"):
        r = subprocess.run(["ffmpeg","-y","-i",mp3_path,tmp_wav],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        converted = r.returncode == 0
    if not converted:
        try:
            import static_ffmpeg; static_ffmpeg.add_paths()
            if shutil.which("ffmpeg"):
                r = subprocess.run(["ffmpeg","-y","-i",mp3_path,tmp_wav],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                converted = r.returncode == 0
        except ImportError:
            pass
    if not converted:
        job_log(jid,"ERROR: ffmpeg not found. Run: pip install static-ffmpeg","err")
        return None

    with open(json_path) as f: report = json.load(f)
    sr             = report["sample_rate_hz"]
    original_dur_s = ts_to_sec(report["original_duration"])
    segments       = sorted(report["removed_segments"], key=lambda x: x["start_sec"])

    cleaned, file_sr = sf.read(tmp_wav, dtype="float32")
    os.remove(tmp_wav)
    if file_sr != sr: sr = file_sr

    is_stereo    = cleaned.ndim == 2
    output_parts = []
    cleaned_pos  = 0
    timeline_pos = 0.0

    for seg in segments:
        speech_dur = seg["start_sec"] - timeline_pos
        if speech_dur > 0.001:
            n=int(round(speech_dur*sr)); end=min(cleaned_pos+n,len(cleaned))
            output_parts.append(cleaned[cleaned_pos:end]); cleaned_pos=end
        sil_n=int(round((seg["end_sec"]-seg["start_sec"])*sr))
        if sil_n>0:
            shape=(sil_n,cleaned.shape[1]) if is_stereo else (sil_n,)
            output_parts.append(np.zeros(shape,dtype="float32"))
        timeline_pos=seg["end_sec"]

    remaining=original_dur_s-timeline_pos
    if remaining>0.001 and cleaned_pos<len(cleaned):
        end=min(cleaned_pos+int(round(remaining*sr)),len(cleaned))
        output_parts.append(cleaned[cleaned_pos:end])

    restored=np.concatenate(output_parts,axis=0)
    restored_dur=len(restored)/sr
    diff_ms=abs(restored_dur-original_dur_s)*1000
    job_log(jid,f"Restored: {fmt(restored_dur)}  |  Expected: {fmt(original_dur_s)}  |  Diff: {diff_ms:.1f} ms","ok" if diff_ms<100 else "warn")

    sf.write(out_path,restored,sr)
    job_log(jid,f"Saved: {Path(out_path).name}","ok")
    return out_path


# ══════════════════════════════════════════════
# FLASK APP
# ══════════════════════════════════════════════
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app)

@app.route("/")
def index():
    return send_file(BASE_DIR / "voice_cutter_ui.html")


@app.route("/api/key-status")
def key_status():
    key = load_api_key()
    return jsonify({"has_key": bool(key), "key_preview": key[:8]+"..." if key else ""})


@app.route("/api/voices")
def get_voices():
    api_key = load_api_key()
    if not api_key:
        return jsonify({"error": "No API key"}), 401
    r = req_lib.get("https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": api_key}, timeout=30)
    if r.status_code != 200:
        return jsonify({"error": r.text}), r.status_code
    return jsonify(r.json())


@app.route("/api/run/pipeline", methods=["POST"])
def api_pipeline():
    files     = request.files.getlist("files")
    voice_id  = request.form.get("voice_id")
    model_id  = request.form.get("model_id",  DEFAULT_MODEL)
    stability = float(request.form.get("stability",  DEFAULT_STABILITY))
    similarity= float(request.form.get("similarity", DEFAULT_SIMILARITY))
    style     = float(request.form.get("style",      DEFAULT_STYLE))
    remove_bg = request.form.get("remove_bg","false").lower()=="true"

    if not files or not voice_id:
        return jsonify({"error":"files and voice_id required"}),400

    # Save all uploaded files to disk NOW while the request is still open
    # (Flask closes file streams after the request ends — threads run after)
    saved_files = []
    for f in files:
        stem   = Path(f.filename).stem
        wav_in = str(UPLOAD_DIR / f.filename)
        f.save(wav_in)
        saved_files.append((f.filename, stem, wav_in))

    jid = new_job()

    def run():
        results = []
        for filename, stem, wav_in in saved_files:
            cleaned  = str(OUTPUT_DIR / f"{stem}_cleaned.wav")
            json_rpt = str(OUTPUT_DIR / f"{stem}_cleaned_report.json")
            voiced   = str(OUTPUT_DIR / f"{stem}_cleaned.mp3")
            restored = str(OUTPUT_DIR / f"{stem}_restored.wav")

            job_log(jid, f"\n── [{saved_files.index((filename,stem,wav_in))+1}/{len(saved_files)}] {filename}", "info")

            # Step 1
            job_log(jid, "> Step 1 — Removing dead air")
            r1 = run_deadair(wav_in, cleaned, jid)
            if not r1[0]:
                results.append({"file":filename,"status":"skip","reason":"No speech detected"})
                continue

            # Step 2
            job_log(jid, f"> Step 2 — Voice cloning")
            r2 = run_clone(cleaned, voice_id, voiced, jid,
                           model_id=model_id, stability=stability,
                           similarity=similarity, style=style, remove_bg=remove_bg)
            if not r2:
                results.append({"file":filename,"status":"error","reason":"API failed"})
                continue

            # Step 3
            job_log(jid, "> Step 3 — Restoring original length")
            r3 = run_restore(voiced, json_rpt, restored, jid)
            if not r3:
                results.append({"file":filename,"status":"error","reason":"Restore failed"})
                continue

            results.append({
                "file":       filename,
                "status":     "ok",
                "restored":   Path(restored).name,
                "credits":    r2[1] if len(r2)>1 else "?",
                "remaining":  r2[2] if len(r2)>2 else "?",
            })

        job_log(jid, f"\nPipeline complete — {len(results)} file(s)", "ok")
        job_done(jid, results)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": jid})


@app.route("/api/status/<jid>")
def stream_status(jid):
    """Server-Sent Events — streams log lines to the UI in real time."""
    if jid not in jobs:
        return jsonify({"error":"job not found"}),404

    def generate():
        q = jobs[jid]["queue"]
        while True:
            item = q.get()
            if item is None:  # done sentinel
                result = jobs[jid]["result"]
                yield f"data: {json.dumps({'done':True,'result':result})}\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})


@app.route("/download/<filename>")
def download(filename):
    path = OUTPUT_DIR / filename
    if not path.exists():
        return jsonify({"error":"file not found"}),404
    return send_file(str(path), as_attachment=True)


# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════
if __name__ == "__main__":
    import webbrowser

    api_key = load_api_key()
    print("\n  VoiceCutter Local Server")
    print("  " + "─"*30)
    print(f"  API key : {'found ✓' if api_key else 'NOT FOUND — check .env'}")
    print(f"  Output  : {OUTPUT_DIR}")
    print(f"  URL     : http://localhost:5000")
    print("  " + "─"*30)
    print("  Press Ctrl+C to stop\n")

    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
