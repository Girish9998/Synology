# Supported Audio Formats Reference

The `file-audio-manager` CLI leverages [Mutagen](https://mutagen.readthedocs.io/) to support a comprehensive range of audio file formats and tag containers.

## Supported Formats

| Format | Extension(s) | Tagging Format | Capabilities | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **MP3** | `.mp3` | ID3v2.3 / ID3v2.4, ID3v1 | Read, Write, Artwork, Clear | Most common format. Automatically manages ID3 frames (`TIT2`, `TPE1`, `TALB`, etc.). |
| **FLAC** | `.flac` | Vorbis Comment | Read, Write, Artwork, Clear | Lossless. High fidelity metadata support with embedded picture blocks (`Picture`). |
| **Ogg Vorbis** | `.ogg`, `.oga` | Vorbis Comment | Read, Write, Artwork, Clear | Open-source lossy format. Supports METADATA_BLOCK_PICTURE. |
| **M4A / AAC** | `.m4a`, `.aac`, `.mp4` | MP4 iTunes tags | Read, Write, Artwork, Clear | Apple MPEG-4 container. Tags use 4-character codes (e.g., `\xa9nam`, `\xa9ART`, `covr`). |
| **WAV** | `.wav` | ID3 chunk / RIFF INFO | Read, Write, Clear | Uncompressed PCM. Reads and writes ID3 chunks embedded in WAV headers. |
| **Opus** | `.opus` | Vorbis Comment | Read, Write, Artwork, Clear | Modern lossy speech and music format. |
| **AIFF** | `.aiff`, `.aif` | ID3 chunk | Read, Write, Artwork, Clear | Uncompressed Apple format. |

## Feature Matrix

| Operation | MP3 | FLAC | M4A | OGG | WAV |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Basic Tags (Title, Artist, Album) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Track / Disc Numbers | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cover Art (Embed / Extract) | ✅ | ✅ | ✅ | ✅ | ⚠️ (limited) |
| Lyrics / Unsynced Lyrics | ✅ | ✅ | ✅ | ✅ | ❌ |
| Batch Metadata Editing | ✅ | ✅ | ✅ | ✅ | ✅ |
| Export to JSON / CSV | ✅ | ✅ | ✅ | ✅ | ✅ |
| Import from JSON / CSV | ✅ | ✅ | ✅ | ✅ | ✅ |

## Implementation Details

- **Atomic Saves**: Mutagen writes metadata directly to the header and padding chunks without re-encoding audio samples.
- **Character Encoding**: All metadata strings are encoded as UTF-8 by default for universal compatibility across modern media players.
- **Artwork Types**: Cover images are accepted as JPEG (`.jpg`, `.jpeg`) or PNG (`.png`).
