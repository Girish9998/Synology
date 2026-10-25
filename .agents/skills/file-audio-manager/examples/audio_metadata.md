# Audio Metadata — Usage Examples

This document provides working example commands for `audio_metadata.py`.

---

## Read Tags

```bash
# Read all tags from an MP3
python scripts/audio_metadata.py read song.mp3

# Read all tags from a FLAC file
python scripts/audio_metadata.py read album/track01.flac

# Read a single field
python scripts/audio_metadata.py read song.mp3 --field artist
```

Example output:
```
╭──────────────────── 🎵 song.mp3  (MP3) ────────────────────╮
│ Field        Value                                           │
│ title        Bohemian Rhapsody                               │
│ artist       Queen                                           │
│ album        A Night at the Opera                            │
│ albumartist  Queen                                           │
│ tracknumber  1                                               │
│ totaltracks  12                                              │
│ discnumber   1                                               │
│ year         1975                                            │
│ genre        Rock                                            │
│ comment      Remastered 2011                                 │
│ composer     Freddie Mercury                                 │
│ bpm          72                                              │
│ cover        ✔ embedded                                      │
╰─────────────────────────────────────────────────────────────╯
```

---

## Write Tags

```bash
# Set the title and artist
python scripts/audio_metadata.py write song.mp3 --title "My Song" --artist "My Artist"

# Set multiple tags at once
python scripts/audio_metadata.py write song.mp3 \
  --title "Bohemian Rhapsody" \
  --artist "Queen" \
  --album "A Night at the Opera" \
  --year "1975" \
  --genre "Rock" \
  --tracknumber "1" \
  --totaltracks "12"

# Set comment and composer on a FLAC file
python scripts/audio_metadata.py write track.flac \
  --comment "Remastered Edition" \
  --composer "Ludwig van Beethoven"

# Set BPM on an M4A
python scripts/audio_metadata.py write podcast.m4a --bpm "120"
```

---

## Copy Tags Between Files

```bash
# Copy all tags from one MP3 to another
python scripts/audio_metadata.py copy-tags source.mp3 destination.mp3

# Copy only tags that exist in the source (skip unset fields)
python scripts/audio_metadata.py copy-tags source.mp3 destination.mp3 --skip-missing

# Copy tags from MP3 to FLAC (cross-format)
python scripts/audio_metadata.py copy-tags song.mp3 song.flac
```

---

## Clear Tags

```bash
# Remove specific fields
python scripts/audio_metadata.py clear song.mp3 --fields comment lyrics

# Remove all tags (with confirmation)
python scripts/audio_metadata.py clear song.mp3 --all

# Remove all tags without confirmation prompt
python scripts/audio_metadata.py clear song.mp3 --all --force
```

---

## Batch Read

```bash
# Read tags from all audio files in a folder
python scripts/audio_metadata.py batch-read /music/Album

# Include subdirectories
python scripts/audio_metadata.py batch-read /music --recursive

# Only MP3 files
python scripts/audio_metadata.py batch-read /music --ext mp3 --recursive

# Show specific fields
python scripts/audio_metadata.py batch-read /music \
  --fields title --fields artist --fields year --fields bpm
```

---

## Batch Write

```bash
# Set album and year on all files in a folder
python scripts/audio_metadata.py batch-write /music/Album \
  --album "Greatest Hits" \
  --year "2024" \
  --force

# Apply to only FLAC files
python scripts/audio_metadata.py batch-write /music \
  --ext flac \
  --albumartist "Various Artists" \
  --recursive \
  --force
```

---

## Export Metadata

```bash
# Export single file to JSON (stdout)
python scripts/audio_metadata.py export song.mp3

# Export single file to JSON file
python scripts/audio_metadata.py export song.mp3 --format json --output song_tags.json

# Export all files in a directory to CSV
python scripts/audio_metadata.py export /music/Album --format csv --output album_tags.csv

# Export recursively to JSON
python scripts/audio_metadata.py export /music \
  --format json \
  --output all_music.json \
  --recursive
```

Example JSON output:
```json
[
  {
    "file": "/music/Album/01 - Song.mp3",
    "title": "Song Title",
    "artist": "Artist Name",
    "album": "Album Name",
    "year": "2024",
    "genre": "Pop",
    "tracknumber": "1",
    "totaltracks": "12"
  }
]
```

---

## Import Metadata

```bash
# Apply tags from a JSON file
python scripts/audio_metadata.py import tags.json

# Apply tags from a CSV file
python scripts/audio_metadata.py import tags.csv

# Preview without making changes
python scripts/audio_metadata.py import tags.json --dry-run

# Apply without confirmation
python scripts/audio_metadata.py import tags.json --force
```

CSV format example:
```csv
file,title,artist,album,year,genre,tracknumber
/music/01.mp3,Track One,My Band,My Album,2024,Rock,1
/music/02.mp3,Track Two,My Band,My Album,2024,Rock,2
```

---

## Cover Art (Artwork)

```bash
# Extract cover art from an MP3
python scripts/audio_metadata.py artwork song.mp3 --extract

# Extract to a specific output file
python scripts/audio_metadata.py artwork song.mp3 --extract --output cover.jpg

# Embed a cover art image into a file
python scripts/audio_metadata.py artwork song.mp3 --embed /images/cover.jpg

# Embed a PNG into a FLAC file
python scripts/audio_metadata.py artwork track.flac --embed /images/cover.png
```

---

## Fetch and Embed Lyrics (LRCLIB)

```bash
# Fetch and embed plain lyrics + save companion .lrc synchronized file
python scripts/audio_metadata.py lyrics "C:/music/Barso Re.mp3"

# Preview lyrics matches without writing to file (dry run)
python scripts/audio_metadata.py lyrics "C:/music/English/21 Guns.mp3" --dry-run

# Batch process an entire album/directory
python scripts/audio_metadata.py lyrics "C:/music/A.R. Rahman Hits" --recursive

# Force overwrite existing lyrics and .lrc companion files
python scripts/audio_metadata.py lyrics "C:/music/song.mp3" --force

# Explicitly override track title or artist for hard-to-find tracks
python scripts/audio_metadata.py lyrics "C:/music/track.mp3" --title "Chaiyya Chaiyya" --artist "Sukhwinder Singh"

# Embed plain lyrics only (skip creating companion .lrc file)
python scripts/audio_metadata.py lyrics "C:/music/track.mp3" --no-synced
```

---

## Common Workflow: Tag a New Album

```bash
# 1. Batch-write album/artist/year to all tracks
python scripts/audio_metadata.py batch-write /music/NewAlbum \
  --album "My New Album" \
  --albumartist "My Artist" \
  --year "2024" \
  --genre "Electronic" \
  --force

# 2. Set individual track numbers and titles
python scripts/audio_metadata.py write /music/NewAlbum/track01.mp3 \
  --tracknumber 1 --totaltracks 10 --title "Intro"

python scripts/audio_metadata.py write /music/NewAlbum/track02.mp3 \
  --tracknumber 2 --totaltracks 10 --title "Main Theme"

# 3. Embed cover art on all tracks
for file in /music/NewAlbum/*.mp3; do
  python scripts/audio_metadata.py artwork "$file" --embed /images/album_cover.jpg
done

# 4. Verify everything looks correct
python scripts/audio_metadata.py batch-read /music/NewAlbum

# 5. Export a metadata backup
python scripts/audio_metadata.py export /music/NewAlbum \
  --format json \
  --output NewAlbum_metadata_backup.json
```
