# Bug Fixes & Immediate Tweaks

## Active Fixes Needed

### 1. Cover Art Fallback & Corrections
- **Question / Issue**: 3 album arts aren't correct.
- **Action items**:
  - Investigate provider matching confidence threshold and fallback resolution order.
  - Test iTunes vs JioSaavn vs Deezer results for the affected songs.

---

## Logged Fixes
- [2026-10-31] **Logger Placement & Architecture Resolved**: Centralized into `utils/logger.py` as an asynchronous, non-blocking production engine (`QueueHandler`/`QueueListener`, `ContextVar` request tracing, ANSI-colored terminal output, consolidated 2-file sink `logs/app.log` and `logs/error.log`). Removed redundant logger duplication from skills and sub-apps (`apps/audio_downloader`).
