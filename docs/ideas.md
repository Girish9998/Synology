# Feature Ideas & Architecture Improvements

## Active Ideas & Considerations

### 1. Logger Placement & Skill File Architecture
- **Question / Issue**: Should the logger live directly inside the skill folders (e.g. `audio_logger.py`, `nas_logger.py`), or should it be a shared/central utility at the repository level?
- **Considerations**:
  - Skill modularity vs. code duplication.
  - Making skills portable/self-contained vs. repo-wide standardized logging framework.
  - Review if logger modules inside skill folders are the ideal pattern or if a shared common package is preferable.

### 2. API Rate Limiting Mitigation
- **Question / Issue**: How to handle and reduce API rate-limiting so external providers (e.g. Apple iTunes, JioSaavn, LRCLIB) don't block requests with HTTP 403 / 429?
- **Considerations**:
  - Request throttling / adaptive delay between queries (configurable in `config.json`).
  - Exponential backoff with jitter on 403/429 responses.
  - Caching query responses locally to avoid redundant round-trips.
  - Intelligent batching and preemptive provider switching.

---

## Logged Ideas

