# Feature Ideas & Architecture Improvements

## Implemented Features

### 1. Universal Audio Downloader & Synology NAS Integration
- **Sub-App Package**: [`apps/audio_downloader/`](../apps/audio_downloader/) (Aliased also as `apps.audiodownloader`)
- **Implementation Status**: Completed ✅
- **Capabilities**:
  - **Telegram Bot Ingestion ([`apps/audio_downloader/backend/bot.py`](../apps/audio_downloader/backend/bot.py))**:
    - Listens for music URLs (YouTube, Spotify, Apple Music) and optional trim ranges (`01:00 01:30`).
    - Downloads audio using `yt-dlp` (with Cobalt fallback), smart matches metadata, and embeds 1000×1000 high-res cover art.
    - Saves downloaded tracks directly to Synology NAS (`Z:\Downloads` / `\\Girish_NAS\music\Downloads`).
    - Responds in Telegram with the clean-titled MP3 and confirmation caption showing NAS archive location.
    - Automatically cleans up local temporary staging files while keeping the NAS copy intact.
  - **Web Application Ingestion ([`apps/audio_downloader/backend/app.py`](../apps/audio_downloader/backend/app.py) & [`apps/audio_downloader/frontend/`](../apps/audio_downloader/frontend/))**:
    - Serves mobile/desktop web portal on port 8000 (accessible on local network via `http://192.168.86.27:8000`).
    - Streams MP3 download to phone/client immediately while simultaneously archiving a copy to Synology NAS `Downloads/` via non-blocking `BackgroundTasks`.
  - **Docker & NAS Container Hosting ([`Dockerfile`](../Dockerfile) & [`docker-compose.yml`](../docker-compose.yml))**:
    - Containerized with embedded `ffmpeg` and volume mount directly into `/volume1/music/Downloads`.
    - Auto-restarts on NAS reboot via Synology Container Manager.
  - **Dedicated Sub-App & SDLC Logging Architecture**:
    - Created dedicated sub-app logger ([`apps/audio_downloader/backend/logger.py`](../apps/audio_downloader/backend/logger.py)) that feeds real-time formatted stdout to console/terminal, writes to dedicated application logs (`logs/backend.log`, `logs/frontend.log`), and propagates to the centralized repository logger ([`utils/logger.py`](../utils/logger.py): `info.log`, `error.log`, `detail.log`, `audit.jsonl`).
  - **Configuration Integration**:
    - Registered `downloader` section and `download_folder` in [`config.json`](../config.json).

---

## Active Ideas & Considerations

### 1. API Rate Limiting Mitigation
- **Question / Issue**: How to handle and reduce API rate-limiting so external providers (e.g. Apple iTunes, JioSaavn, LRCLIB) don't block requests with HTTP 403 / 429?
- **Considerations**:
  - Request throttling / adaptive delay between queries (configurable in `config.json`).
  - Exponential backoff with jitter on 403/429 responses.
  - Caching query responses locally to avoid redundant round-trips.
  - Intelligent batching and preemptive provider switching.

### 2. Audio Storage & Library Deduplication Cache
- **Question / Goal**: Before initiating a full download, check if the song already exists in local storage / NAS music library and return the cached track instead of re-downloading.
- **Design & Considerations**:
  - **URL / Video ID Cache**: Maintain an SQLite or JSON lookup index mapping `youtube_video_id` / `spotify_id` to existing archived file paths on the NAS.
  - **Fuzzy Metadata Matching**: When smart metadata extracts `Title` and `Artist`, scan `music/` and `music/Downloads/` for existing MP3 files with matching ID3 tags.
  - **Instant Delivery**: Telegram bot and Web API can deliver the existing file in milliseconds with caption: `⚡ Retrieved from NAS library (already exists)`.
  - **Storage & Bandwidth Savings**: Prevents duplicate tracks (`Song (1).mp3`), avoids repeated YouTube bandwidth usage, and eliminates external rate-limiting triggers.

---

## Logged Ideas
- [2026-10-29 23:28] Web App since.. iphone can't have a free app..
- [2026-10-29 23:47] Merge download code and keep add it here.. so that agent can download and save to the location which nas has access to (Implemented 2026-10-31)
- [2026-10-31 17:52] Add download cache to check if song already exists in NAS storage / library and return existing file instead of re-downloading
