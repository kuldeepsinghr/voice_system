# 🎵 Audio Player - Setup Guide

## Requirements
- Python 3.7+
- pip

---

## 1. Create a Virtual Environment

### macOS / Linux
```bash
python3 -m venv audio_env
source audio_env/bin/activate
```

### Windows
```bash
python -m venv audio_env
audio_env\Scripts\activate
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note (Linux only):** You may need system-level audio libs:
> ```bash
> sudo apt-get install python3-dev libasound2-dev ffmpeg
> ```

> **Note (macOS only):** If using pydub, install ffmpeg:
> ```bash
> brew install ffmpeg
> ```

---

## 3. Run the Script

```bash
python play_audio.py <your_audio_file>
```

### Examples
```bash
python play_audio.py song.mp3
python play_audio.py audio/podcast.wav
python play_audio.py music/track.flac
```

---

## 4. Deactivate Environment (when done)

```bash
deactivate
```

---

## Supported Formats
| Format | pygame | playsound | pydub |
|--------|--------|-----------|-------|
| MP3    | ✅     | ✅        | ✅    |
| WAV    | ✅     | ✅        | ✅    |
| OGG    | ✅     | ❌        | ✅    |
| FLAC   | ❌     | ❌        | ✅    |

---

## Project Structure
```
audio-player/
├── play_audio.py       # Main script
├── requirements.txt    # Python dependencies
└── README.md           # This file
```
