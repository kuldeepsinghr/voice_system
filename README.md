# WAV Dead Air Tool

A Python-based audio processing pipeline that removes dead air (silence) from WAV recordings, applies ElevenLabs voice cloning, and restores the audio back to its original length and timing.

---

## What It Does

Voice recordings often contain long stretches of silence — pauses between sentences, dead air at the start or end, or gaps between takes. This tool removes all of that automatically, sends the compact audio through ElevenLabs' Speech-to-Speech voice changer, then re-inserts the silence back at its exact original timestamps — giving you a voice-cloned version that matches the original timing perfectly.

```
Original 20min WAV
       |
       v
  [Remove dead air]  -->  5min cleaned WAV  +  report.json
       |
       v
  [ElevenLabs Voice Clone]  -->  5min voiced MP3
       |
       v
  [Restore original length]  -->  20min restored WAV  (final output)
```

---

## Project Structure

```
voice_system/
├── run.bat               <-- double-click to launch (Windows)
├── pipeline.py           <-- full pipeline in one run (recommended)
├── play_audio.py         <-- step 1 only: remove dead air
├── voice_clone.py        <-- step 2 only: ElevenLabs voice change
├── restore_audio.py      <-- step 3 only: restore original length
├── requirements.txt      <-- Python dependencies
├── .env                  <-- your ElevenLabs API key (auto-created)
└── README.md             <-- this file
```

---

## Requirements

- Windows 10 / 11
- Python 3.10 or higher (tested on Python 3.14)
- ElevenLabs account with at least one voice in your library
- Internet connection (for ElevenLabs API calls)

---

## Setup

### 1. Install Python

Download from https://www.python.org/downloads/

> **Important:** During install, tick **"Add Python to PATH"**

### 2. Install dependencies

Open a terminal in the project folder and run:

```cmd
pip install -r requirements.txt
```

Or use option **5** in `run.bat` — it installs everything automatically.

### 3. Add your ElevenLabs API key

Get your key from: https://elevenlabs.io/app/settings/api-keys

Either create a `.env` file manually:

```
ELEVENLABS_API_KEY=your_key_here
```

Or just run the pipeline — it will ask you to paste the key and save it for you.

---

## How to Run

Double-click `run.bat` — a menu appears:

```
==========================================
 WAV Dead Air Tool
==========================================

 [*] 1.  Full pipeline  (recommended)
         Remove dead air + Voice clone + Restore
         All in one go - pick files once

 --- Run steps individually ---
 2.  Remove dead air only    (play_audio.py)
 3.  Voice clone only        (voice_clone.py)
 4.  Restore audio only      (restore_audio.py)
 ------------------------------
 5.  Check / install dependencies
 6.  Exit
```

**Option 1 is recommended** for most use cases — it runs all three steps with minimal interaction.

---

## Full Pipeline (Option 1)

Running `pipeline.py` walks you through these steps:

**Step 1 — Select your audio files**
A file picker opens. Select one or more WAV files. Hold `Ctrl` to select multiple files at once.

**Step 2 — Pick a voice**
Your ElevenLabs voice library is listed. Type a name to search or enter a number to select. You will also be asked for voice settings — just press `Enter` to use the defaults below.

| Setting | Default | Description |
|---|---|---|
| Model | eleven_multilingual_sts_v2 | Best quality, any language |
| Stability | 0.65 | Higher = more consistent delivery |
| Similarity boost | 0.75 | How closely to match the target voice |
| Style exaggeration | 0.10 | Adds expressiveness |
| Remove BG noise | Off | Strip background noise before cloning |

**Step 3 — Pipeline runs automatically**
For each file the tool will remove dead air, send it to ElevenLabs, restore the original length, then open a Save As dialog so you choose exactly where the final file lands.

---

## Individual Scripts

Use these when you need to re-run just one step — for example if the ElevenLabs API call failed and you want to retry without re-doing the dead air removal.

### play_audio.py — Remove Dead Air

Accepts multiple WAV files. Detects silence using adaptive thresholding (automatically measures the noise floor of each file so no manual tuning is needed). Saves:

- `filename_cleaned.wav` — compact audio with silence removed
- `filename_cleaned_report.json` — full cut map with timestamps of every removed segment

### voice_clone.py — ElevenLabs Voice Change

Takes the cleaned WAV, lets you pick a voice from your library, and sends the audio to the ElevenLabs Speech-to-Speech API. Saves the result as `filename_cleaned.mp3` in the same folder so `restore_audio.py` can find everything automatically.

### restore_audio.py — Restore Original Length

Takes the voiced MP3 and the JSON report, re-inserts silence at the exact original timestamps, and outputs a WAV that matches the original duration. Accepts WAV or MP3 as input. If the JSON report is in the same folder as the audio file it is detected automatically — no manual selection needed.

---

## Output Files

For an input file named `ALINA_01.wav`, the pipeline produces:

```
ALINA_01_cleaned.wav          <-- dead air removed (intermediate)
ALINA_01_cleaned_report.json  <-- cut map (keep this — needed for restore)
ALINA_01_cleaned.mp3          <-- voice cloned (intermediate)
ALINA_01_restored.wav         <-- FINAL OUTPUT
```

The intermediate files are kept so you can re-run any individual step if needed.

---

## The JSON Report

Every time dead air is removed, a JSON report is saved alongside the cleaned file. This report is the "memory" of the process — it records every silence segment that was cut, with exact timestamps.

Example:

```json
{
  "original_duration": "00:20:00.000",
  "cleaned_duration":  "00:05:12.340",
  "removed_percent":   "73.9%",
  "segments_removed":  47,
  "removed_segments": [
    {
      "index": 1,
      "start_timestamp": "00:00:00.000",
      "end_timestamp":   "00:00:08.320",
      "duration_sec":    8.32
    }
  ]
}
```

**Keep this file.** Without it, the restore step cannot work.

---

## ElevenLabs Limits

The Speech-to-Speech endpoint accepts a maximum of approximately 5 minutes of audio per request. The dead air removal step exists specifically to bring long recordings under this limit before sending them to ElevenLabs.

If your cleaned audio is still over 5 minutes after dead air removal, consider splitting it into segments and running each segment through the pipeline separately.

---

## Troubleshooting

**run.bat flashes and closes**
The file may have been saved with UTF-8 BOM encoding. Open it in Notepad, go to File > Save As, change the encoding to ANSI, and save.

**pydub import error / No module named pyaudioop**
pydub is not compatible with Python 3.13+. This tool uses numpy and soundfile instead — pydub is not required. Run option 5 in run.bat to install the correct dependencies.

**ERROR 400: unsupported_model**
Only `sts` models work with the Speech-to-Speech endpoint. The tool defaults to `eleven_multilingual_sts_v2` which is correct. If you see this error, make sure you are using the latest `voice_clone.py`.

**No speech detected**
The adaptive threshold may be set too high for very quiet recordings. This can happen if the recording has a high noise floor. The tool will skip the file and print a warning.

**ffmpeg not found (during restore)**
The restore step needs ffmpeg to convert the MP3 back to WAV. Install it with:
```cmd
pip install static-ffmpeg
```
Or download manually from https://www.gyan.dev/ffmpeg/builds/ and add to your system PATH.

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| numpy | >= 1.26 | Audio processing, silence detection |
| soundfile | >= 0.12 | Read and write WAV files |
| requests | >= 2.31 | ElevenLabs API calls |
| static-ffmpeg | >= 2.5 | MP3 decoding during restore |
| playsound | == 1.2.2 | Audio playback |

All installed via `pip install -r requirements.txt` or run.bat option 5.

---

## License

For personal and internal use. ElevenLabs API usage is subject to ElevenLabs' own terms of service at https://elevenlabs.io/terms