---
name: file-audio-manager
description: >-
  Use this skill when the user wants to manage files (CRUD operations: create,
  read, update, delete, copy, move, rename, search, list), read/write audio tags
  (MP3, FLAC, AAC, M4A, OGG, WAV), or organize music libraries following standard
  patterns (unified compilation albums, 1000x1000 individual movie/single covers,
  clean filenames, clearing track numbers on loose tracks for alphabetical sorting,
  and subfolder soundtrack tagging).
---

# File & Audio Manager Skill

This skill provides two production-quality Python CLIs:

1. **`file_manager.py`** — General-purpose file CRUD operations with rich terminal output
2. **`audio_metadata.py`** — Full audio tag read/write/batch/export operations for all common formats

---

## Setup

Before using, install dependencies:

```bash
pip install -r requirements.txt
```

Or from the project root:

```bash
pip install mutagen rich click
```

---

## 1. File Manager CLI (`scripts/file_manager.py`)

Run any command with:
```bash
python scripts/file_manager.py <command> [options]
```

### Commands

| Command  | Description                                         |
|----------|-----------------------------------------------------|
| `list`   | List files/directories in a path                    |
| `create` | Create a file or directory                          |
| `read`   | Read and display file content                       |
| `copy`   | Copy a file or directory                            |
| `move`   | Move a file or directory                            |
| `delete` | Delete a file or directory                          |
| `rename` | Rename a file or directory                          |
| `info`   | Show detailed file metadata                         |
| `search` | Search for files by name, extension, content        |

### Agent Instructions

1. **Listing files**: Use `list` with `--ext` to filter by extension, `--pattern` for glob patterns, `--recursive` to descend into subdirectories. Output is a rich table with size, type, and modification time.

2. **Creating files/dirs**: Use `create <path>` with `--dir` flag to create a directory instead of a file. Use `--content` to pre-populate the file with text.

3. **Reading files**: Use `read <path>` to display file content in a rich panel. Use `--lines` to limit output to N lines, `--encoding` to set encoding.

4. **Copying**: Use `copy <src> <dst>`. For directories, pass `--recursive` to copy the whole tree.

5. **Moving**: Use `move <src> <dst>`. Works for files and directories. Renames in-place if same parent.

6. **Deleting**: Use `delete <path>` with `--force` to skip confirmation. Without `--force`, the CLI will prompt for confirmation.

7. **Renaming**: Use `rename <old_path> <new_name>` where `new_name` is just the filename (not a full path).

8. **File info**: Use `info <path>` to display size, permissions, modification time, creation time, and MIME type in a rich panel.

9. **Searching**: Use `search <directory>` with `--name`, `--ext`, `--content` flags. `--content` does a text grep inside files.

**Error handling**: All commands handle `FileNotFoundError`, `PermissionError`, and `IsADirectoryError` with colored, informative messages. Always check if paths exist before operating.

---

## 2. Audio Metadata CLI (`scripts/audio_metadata.py`)

Run any command with:
```bash
python scripts/audio_metadata.py <command> [options]
```

### Supported Formats

| Format | Extensions       | Tag Standard    |
|--------|------------------|-----------------|
| MP3    | `.mp3`           | ID3v2           |
| FLAC   | `.flac`          | Vorbis Comments |
| OGG    | `.ogg`           | Vorbis Comments |
| M4A/AAC| `.m4a`, `.aac`  | iTunes/MP4 Tags |
| WAV    | `.wav`           | ID3v2           |

### Supported Tag Fields

| Field        | Description                        |
|--------------|------------------------------------|
| title        | Track title                        |
| artist       | Primary artist                     |
| album        | Album name                         |
| albumartist  | Album artist / compilation artist  |
| tracknumber  | Track number (e.g. "1" or "1/12") |
| totaltracks  | Total tracks on album              |
| discnumber   | Disc number                        |
| totaldiscs   | Total discs                        |
| year         | Release year                       |
| genre        | Genre string                       |
| comment      | Free-form comment                  |
| composer     | Composer name                      |
| lyrics       | Full lyrics text                   |
| bpm          | Beats per minute                   |
| cover        | Cover art (binary, handled via artwork command) |

### Commands

| Command       | Description                                                   |
|---------------|---------------------------------------------------------------|
| `read`        | Read all tags from a file                                     |
| `write`       | Write/update one or more tags on a file                       |
| `copy-tags`   | Copy all tags from one file to another                        |
| `clear`       | Clear specific or all tags from a file                        |
| `batch-read`  | Read metadata from all audio files in a directory            |
| `batch-write` | Apply the same tag(s) to multiple files                       |
| `export`      | Export metadata to JSON or CSV                                |
| `import`      | Import metadata from JSON or CSV and apply to files           |
| `artwork`     | Extract or embed cover art (`--extract` / `--embed`)          |
| `auto-tag`    | Look up & apply official iTunes metadata & 1000x1000 artwork  |
| `fetch-art`   | Fetch & embed 1000x1000 iTunes cover art (preserves text tags)|

### Agent Instructions

1. **Reading tags**: Use `read <file>` to display all tags as a rich table. Use `--field` to display a single field value only.

2. **Writing tags**: Use `write <file> --title "My Title" --artist "Artist Name"`. Multiple tags can be set in one call.

3. **Copy tags**: Use `copy-tags <src> <dst>` to clone all supported tags from one file to another.

4. **Clearing tags**: Use `clear <file>` to remove ALL tags, or `clear <file> --fields title artist` to remove only specific fields.

5. **Batch reading**: Use `batch-read <directory>` to scan all supported audio files. Use `--recursive` to descend into subdirectories. Output is a rich table.

6. **Batch writing**: Use `batch-write <directory> --artist "VA" --album "Compilation"` to apply tags to all matched audio files. Use `--ext mp3` to filter by format.

7. **Exporting**: Use `export <file_or_dir> --format json --output tags.json` or `--format csv`. For a directory, exports metadata for all audio files found.

8. **Importing**: Use `import <tags.json>` or `import <tags.csv>` — the file path column in the CSV/JSON is used to locate target audio files and apply the tags.

9. **Artwork**: 
   - Extract: `artwork <file> --extract --output cover.jpg`
   - Embed: `artwork <file> --embed cover.jpg`

10. **Auto-tagging & High-Res Cover Art**:
   - `auto-tag <file_or_dir>`: Queries iTunes API, cleans noise, verifies duration within ±2-3 seconds, and updates tags + embeds 1000x1000 artwork.
   - `fetch-art <file_or_dir>`: Same precision duration matching, but only downloads and embeds 1000x1000 cover art without altering existing text tags. Use `--dry-run` to preview matches first.

**Error handling**: Unsupported formats produce a clear error with the list of supported extensions. Missing files and permission errors are handled gracefully. When writing tags, original file is preserved if an error occurs.

---

## Common Workflows

### Workflow: Organize a Music Library

```bash
# 1. List all MP3 files
python scripts/file_manager.py list /music --ext mp3 --recursive

# 2. Read metadata from all found files
python scripts/audio_metadata.py batch-read /music --recursive --format table

# 3. Export to CSV for bulk editing
python scripts/audio_metadata.py export /music --format csv --output metadata.csv --recursive

# 4. (Edit metadata.csv in a spreadsheet)

# 5. Re-import the edited CSV
python scripts/audio_metadata.py import metadata.csv

# 6. Embed cover art for an album
python scripts/audio_metadata.py artwork /music/AlbumFolder --embed cover.jpg --recursive
```

### Workflow: Backup and Reorganize

```bash
# Copy a directory
python scripts/file_manager.py copy /music/old_folder /backup/music --recursive

# Rename files
python scripts/file_manager.py rename /music/track01.mp3 "01 - Opening Theme.mp3"

# Move organized files
python scripts/file_manager.py move /music/unsorted/song.mp3 /music/Artist/Album/
```

---

### Workflow: Universal Music Library Organization Standards

Always follow this exact workflow when organizing any artist or compilation music folder:

1. **Subfolders (Dedicated Soundtracks/Albums)**:
   - Rename folder to Album Name only (e.g. `Boys`, `Delhi 6`, `Roja` — no years or "(OST)").
   - Set `Album` tag to clean album name.
   - Set `AlbumArtist` tag to primary artist/composer (e.g. `A.R. Rahman`).
   - Preserve soundtrack track numbering (`1/N, 2/N...`).
   - Embed 1000×1000 album master artwork.
   - Rename files to clean `{Title}.mp3`.

2. **Loose Tracks (Root Artist/Compilation Folder)**:
   - Set `Album` = `"<Root Folder/Artist Name>"` (e.g. `A.R. Rahman`).
   - Set `AlbumArtist` = `"<Root Folder/Artist Name>"`.
   - *Reason*: Guarantees all media players and servers (Apple Music, iTunes, Plex, Jellyfin, Navidrome, etc.) unify them into **1 cohesive album**.
   - **Remove track numbers** (`TRCK = None`) so media players cleanly sort all songs alphabetically from A to Z without conflicting soundtrack numbers.
   - Fetch and embed **1000×1000 individual movie/single artwork** for each song.
   - Write movie/release info to comment: `Movie: <CollectionName> | Released: <Date> | Genre: <Genre> | Composer: <Artist>`.
   - Rename files to clean `{Title}.mp3` (or `{Title} ({Movie}).mp3`).

---

## References

- [Supported Formats](references/supported_formats.md)
- [Tag Fields Reference](references/tag_fields.md)
- [File Operations Examples](examples/file_operations.md)
- [Audio Metadata Examples](examples/audio_metadata.md)
