# File Operations — Usage Examples

This document provides working example commands for `file_manager.py`.

---

## List Files

```bash
# List everything in the current directory
python scripts/file_manager.py list .

# List only MP3 files recursively
python scripts/file_manager.py list /music --ext mp3 --recursive

# List files matching a pattern
python scripts/file_manager.py list /music --pattern "*.flac" --recursive

# List only directories
python scripts/file_manager.py list /music --dirs-only

# List only files (no subdirectories shown)
python scripts/file_manager.py list /music --files-only
```

---

## Create Files and Directories

```bash
# Create an empty file
python scripts/file_manager.py create notes.txt

# Create a file with initial content
python scripts/file_manager.py create notes.txt --content "My initial note"

# Create a directory
python scripts/file_manager.py create /music/MyAlbum --dir

# Create a nested directory (parent dirs created automatically)
python scripts/file_manager.py create /music/Artist/Album/Disc1 --dir
```

---

## Read Files

```bash
# Display a file's content
python scripts/file_manager.py read notes.txt

# Limit to first 50 lines
python scripts/file_manager.py read bigfile.log --lines 50

# Read with a specific encoding
python scripts/file_manager.py read latin1_file.txt --encoding latin-1
```

---

## Copy

```bash
# Copy a file to a new location
python scripts/file_manager.py copy song.mp3 /backup/song.mp3

# Copy a file into a directory
python scripts/file_manager.py copy song.mp3 /backup/

# Copy a directory recursively
python scripts/file_manager.py copy /music/Album /backup/Album --recursive

# Overwrite if destination exists
python scripts/file_manager.py copy song.mp3 /backup/song.mp3 --overwrite
```

---

## Move

```bash
# Move a file
python scripts/file_manager.py move song.mp3 /music/Rock/song.mp3

# Move a directory
python scripts/file_manager.py move /unsorted/Album /music/Artist/Album

# Overwrite destination
python scripts/file_manager.py move song.mp3 /backup/song.mp3 --overwrite
```

---

## Delete

```bash
# Delete a file (with confirmation prompt)
python scripts/file_manager.py delete old_file.txt

# Delete without confirmation
python scripts/file_manager.py delete old_file.txt --force

# Delete a directory recursively
python scripts/file_manager.py delete /music/trash --recursive --force
```

---

## Rename

```bash
# Rename a file
python scripts/file_manager.py rename track01.mp3 "01 - Song Title.mp3"

# Rename a directory
python scripts/file_manager.py rename "Old Album Name" "New Album Name"
```

---

## File Info

```bash
# Show metadata for a file
python scripts/file_manager.py info song.mp3

# Show metadata for a directory
python scripts/file_manager.py info /music/Album
```

Expected output (rich panel):
```
╭─────────────── 📄 song.mp3 ───────────────╮
│ Name         song.mp3                      │
│ Type         File                          │
│ Path         /music/Rock/song.mp3          │
│ MIME Type    audio/mpeg                    │
│ Size         8.3 MB                        │
│ Permissions  rw-r--r--                     │
│ Created      2024-01-15 10:30:00           │
│ Modified     2024-03-20 14:22:10           │
│ Accessed     2024-06-01 09:00:00           │
╰───────────────────────────────────────────╯
```

---

## Search

```bash
# Find all files named "cover.jpg" recursively
python scripts/file_manager.py search /music --name "cover.jpg"

# Find all MP3 files
python scripts/file_manager.py search /music --ext mp3

# Find files containing specific text
python scripts/file_manager.py search /music --content "TODO"

# Case-insensitive search
python scripts/file_manager.py search /music --name "beatles*" --ignore-case

# Limit results
python scripts/file_manager.py search / --ext mp3 --max-results 50
```
