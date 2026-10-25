# Feature Ideas & Architecture Improvements

## Active Ideas & Considerations

### 1. API Rate Limiting Mitigation
- **Question / Issue**: How to handle and reduce API rate-limiting so external providers (e.g. Apple iTunes, JioSaavn, LRCLIB) don't block requests with HTTP 403 / 429?
- **Considerations**:
  - Request throttling / adaptive delay between queries (configurable in `config.json`).
  - Exponential backoff with jitter on 403/429 responses.
  - Caching query responses locally to avoid redundant round-trips.
  - Intelligent batching and preemptive provider switching.

---

## Logged Ideas
