# Future Features & AI Roadmap: Speech-to-Text Lyrics via Whisper

## 1. Overview
While open web databases like [LRCLIB](https://lrclib.net/) cover millions of mainstream songs, many regional Indian cinema songs (Telugu, Tamil, Malayalam, Kannada), rare tracks, unreleased demos, and live bootlegs have no existing text or synced lyrics online.

This document outlines the architecture for integrating **AI Speech-to-Text transcription via Whisper** directly into `audio_metadata.py` as an offline, zero-dependency fallback for automatic `.lrc` and ID3 tag generation.

---

## 2. Whisper Speech-to-Text Engine

### 2.1 Proposed Technology Stack
- **Library**: [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) (CTranslate2 backend)
  - 4x faster than vanilla OpenAI Whisper.
  - Efficient on CPU (INT8 quantization) and fast on NVIDIA CUDA GPUs.
- **Model Sizes**:
  - `base` (~140MB): Ultra-fast, ideal for English and standard pop lyrics.
  - `small` (~460MB): Recommended sweet spot for Indian regional languages (Telugu, Tamil, Hindi) with high phonetic accuracy.
  - `medium` (~1.5GB): Maximum accuracy for complex multi-lingual acoustic mixes.

### 2.2 Synchronized LRC Generation Flow
```mermaid
flowchart TD
    A[Audio File: MP3/FLAC/M4A] --> B[Whisper Preprocessing: 16kHz mono audio stream]
    B --> C[Speech-to-Text Transcription + Language Auto-Detection]
    C --> D[Segment Extractor: Text + Start/End Timestamps]
    D --> E[Format into LRC: [mm:ss.xx] Line]
    E --> F[Write companion .lrc file]
    E --> G[Strip timestamps & embed clean text into ID3 USLT frame]
```

### 2.3 Proposed CLI Syntax
```bash
# Generate synced lyrics via local Whisper AI model
python scripts/audio_metadata.py lyrics "track.mp3" --ai

# Explicitly specify audio language (e.g. te = Telugu, ta = Tamil, hi = Hindi, en = English)
python scripts/audio_metadata.py lyrics "track.mp3" --ai --lang te

# Choose Whisper model size (tiny, base, small, medium)
python scripts/audio_metadata.py lyrics "track.mp3" --ai --model small

# Batch transcribe an entire album or folder of unlisted tracks
python scripts/audio_metadata.py lyrics "C:/music/RegionalAlbum" --ai --recursive
```

---

## 3. Supplementary Fallback Features

### 3.1 Multi-Provider Database Cascade
Before invoking local AI compute, cascade through lightweight web APIs:
1. **LRCLIB** (`https://lrclib.net/api/get`) — Current primary provider (plain + synced).
2. **Genius API** (`https://api.genius.com/`) — Crowd-sourced database for indie, rap, and regional Indian tracks (plain text).
3. **NetEase Cloud Music** — Huge Asian cinema synced `.lrc` archive.
4. **Local Whisper AI** — Activated automatically if all web providers return 404.

### 3.2 Instrumental & BGM Recognition
For background score albums (e.g. *Hans Zimmer*, *Mani Ratnam BGM*, *Background Scores*):
- Detect non-vocal audio via Whisper voice-activity detection (VAD) or `--instrumental` flag.
- Tag standard ID3 / LRC marker:
  ```lrc
  [00:00.00] ♪ Instrumental ♪
  ```
- Prevents media players (Apple Music, Plex, Navidrome) from spinning or reporting errors.

### 3.3 Manual File Ingestion
Allow embedding lyrics from external text or LRC files:
```bash
# Embed lyrics from local file
python scripts/audio_metadata.py write "track.mp3" --lyrics-file "lyrics.txt"
```

---

## 4. Implementation Checklist (For Future Activation)
- [ ] Add `faster-whisper` to `requirements.txt` (as optional/extra dependency `[ai]`).
- [ ] Implement `transcribe_with_whisper(audio_path, model_size="small", language=None)` helper in `audio_metadata.py`.
- [ ] Format Whisper segment list into standard `[mm:ss.xx] text\n` strings.
- [ ] Add `--ai`, `--model`, and `--lang` CLI flags to `audio_metadata.py lyrics`.
- [ ] Add `--lyrics-file` flag to `audio_metadata.py write`.
- [ ] Add `--instrumental` flag to tag non-vocal songs.
