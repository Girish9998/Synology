# Audio Tag Fields Reference

This document outlines the metadata fields supported by `audio_metadata.py` across different audio container formats.

## Standard Field Mapping

The CLI provides a unified, cross-format interface for common metadata fields:

| Field CLI Option | Description | MP3 (ID3v2) | FLAC/OGG (Vorbis) | M4A/MP4 (iTunes) |
| :--- | :--- | :--- | :--- | :--- |
| `--title` | Song or track title | `TIT2` | `TITLE` | `\xa9nam` |
| `--artist` | Lead performer or artist | `TPE1` | `ARTIST` | `\xa9ART` |
| `--album` | Album or release title | `TALB` | `ALBUM` | `\xa9alb` |
| `--albumartist` | Primary album artist | `TPE2` | `ALBUMARTIST` | `aART` |
| `--tracknumber` | Track index on media | `TRCK` (number) | `TRACKNUMBER` | `trkn[0]` |
| `--totaltracks` | Total tracks on media | `TRCK` (total) | `TRACKTOTAL` | `trkn[1]` |
| `--discnumber` | Disc index | `TPOS` (number) | `DISCNUMBER` | `disk[0]` |
| `--totaldiscs` | Total discs | `TPOS` (total) | `DISCTOTAL` | `disk[1]` |
| `--year` / `--date` | Year or release date | `TDRC` / `TYER` | `DATE` | `\xa9day` |
| `--genre` | Musical genre | `TCON` | `GENRE` | `\xa9gen` |
| `--composer` | Music composer | `TCOM` | `COMPOSER` | `\xa9wrt` |
| `--comment` | Free-text comment | `COMM` | `COMMENT` | `\xa9cmt` |
| `--bpm` | Beats per minute | `TBPM` | `BPM` | `tmpo` |
| `--lyrics` | Unsynchronized lyrics | `USLT` | `LYRICS` | `\xa9lyr` |

## Cover Artwork (`artwork` subcommand)

Cover art is managed using the `artwork` command:
- **Embedding**: Writes the binary image into the container's designated picture chunk/frame:
  - MP3: `APIC` frame with picture type 3 (Front Cover).
  - FLAC/OGG: `Picture` block (`METADATA_BLOCK_PICTURE`).
  - M4A: `covr` atom (Format 13 for JPEG, 14 for PNG).
- **Extracting**: Reads the front cover image bytes and saves to disk as a `.jpg` or `.png`.

## Batch Tag Operations

When performing batch tag edits with `batch-write`:
- Flags applied (e.g. `--artist "Various" --album "Collection"`) will be updated on all matched files.
- Empty or omitted flags will not overwrite existing tags on files.
- Numbering tags (`--tracknumber`) are typically excluded from bulk writes unless explicitly passed.
