# Bug Fixes & Immediate Tweaks

## Active Fixes Needed

### 1. Logger Placement & Skill File Architecture
- **Question / Issue**: Should the logger live directly inside the skill folders (e.g. `audio_logger.py`, `nas_logger.py`), or should it be a shared/central utility at the repository level?
- **Considerations**:
  - Skill modularity vs. code duplication.
  - Making skills portable/self-contained vs. repo-wide standardized logging framework.
  - Review if logger modules inside skill folders are the ideal pattern or if a shared common package is preferable.

### 2. Cover Art Fallback & Corrections
- **Question / Issue**: 3 album arts aren't correct.
- **Action items**:
  - Investigate provider matching confidence threshold and fallback resolution order.
  - Test iTunes vs JioSaavn vs Deezer results for the affected songs.

---

## Logged Fixes
