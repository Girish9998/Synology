# Synology & File/Audio Management Toolkit

An Antigravity-ready project providing two CLI skills:
1. **`file-audio-manager`**: Standard file CRUD operations and audio metadata tagging (MP3, FLAC, M4A, OGG, WAV).
2. **`synology-nas-manager`**: Secure, multi-protocol Synology NAS authentication, network drive mounting (SMB), SFTP sync, and DSM REST API client.

---

## 📁 Project Architecture

```text
Synology/
├── .agents/
│   └── skills/
│       ├── file-audio-manager/           # Local File & Audio Tagging Skill
│       │   ├── SKILL.md                  # Skill descriptor & agent runbook
│       │   ├── scripts/
│       │   │   ├── file_manager.py       # File CRUD CLI
│       │   │   └── audio_metadata.py     # Audio Tagging CLI (Mutagen)
│       │   ├── examples/                 # Detailed usage walkthroughs
│       │   └── references/               # Audio formats & ID3 tag field specs
│       │
│       └── synology-nas-manager/         # Synology NAS Connection & Sync Skill
│           ├── SKILL.md                  # Skill descriptor & agent runbook
│           ├── scripts/
│           │   ├── nas_cli.py            # Main NAS CLI entrypoint
│           │   ├── nas_client.py         # SMB, SFTP, DSM REST API, WebDAV client
│           │   └── nas_crypto.py         # Encrypted profile vault (~/.nas_credentials)
│           ├── examples/                 # NAS workflow examples
│           └── references/               # Protocol benchmarks & guide
│
├── requirements.txt                      # Dependencies
└── README.md                             # Project documentation
```

---

## ⚡ Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🎵 Skill 1: File & Audio Manager (`file-audio-manager`)

### File CRUD Commands
```bash
# List files with details
python .agents/skills/file-audio-manager/scripts/file_manager.py list ./music

# Copy or move
python .agents/skills/file-audio-manager/scripts/file_manager.py copy ./track01.mp3 ./backup/
python .agents/skills/file-audio-manager/scripts/file_manager.py move ./temp.mp3 ./music/

# Inspect file properties
python .agents/skills/file-audio-manager/scripts/file_manager.py info ./track01.mp3

# Search by extension or name
python .agents/skills/file-audio-manager/scripts/file_manager.py search ./music --ext .flac
```

### Audio Metadata Commands
```bash
# Read all tags from an audio file (MP3, FLAC, M4A, OGG, WAV)
python .agents/skills/file-audio-manager/scripts/audio_metadata.py read song.mp3

# Write or update tags
python .agents/skills/file-audio-manager/scripts/audio_metadata.py write song.mp3 \
  --title "Hotel California" \
  --artist "Eagles" \
  --album "Hotel California" \
  --year 1976 \
  --genre "Classic Rock"

# Batch-tag entire folders
python .agents/skills/file-audio-manager/scripts/audio_metadata.py batch-write ./music \
  --artist "Eagles" \
  --album "Greatest Hits"

# Embed or extract artwork
python .agents/skills/file-audio-manager/scripts/audio_metadata.py artwork song.mp3 --embed cover.jpg
python .agents/skills/file-audio-manager/scripts/audio_metadata.py artwork song.mp3 --extract --out extracted_cover.jpg

# Automated iTunes Metadata & 1000x1000 Master Artwork (No API key needed)
# Auto-tag with duration matching (±2-3s verification):
python .agents/skills/file-audio-manager/scripts/audio_metadata.py auto-tag ./music --dry-run
python .agents/skills/file-audio-manager/scripts/audio_metadata.py auto-tag ./song.mp3

# Fetch & embed 1000x1000 artwork only (keeps your existing text tags untouched):
python .agents/skills/file-audio-manager/scripts/audio_metadata.py fetch-art ./music --dry-run
python .agents/skills/file-audio-manager/scripts/audio_metadata.py fetch-art ./song.mp3

# Export / Import metadata (JSON or CSV)
python .agents/skills/file-audio-manager/scripts/audio_metadata.py export ./music --format json --out tags.json
python .agents/skills/file-audio-manager/scripts/audio_metadata.py import ./music --format json --file tags.json
```

---

## 🖧 Skill 2: Synology NAS Manager (`synology-nas-manager`)

### 1. Profile Setup (Encrypted Credentials)
```bash
# Add a NAS profile (password prompt is masked)
python .agents/skills/synology-nas-manager/scripts/nas_cli.py profile add home-nas \
  --host 192.168.1.100 \
  --username admin \
  --share music \
  --default

# List saved profiles
python .agents/skills/synology-nas-manager/scripts/nas_cli.py profile list

# Test connection across DSM API, SFTP, SMB, WebDAV
python .agents/skills/synology-nas-manager/scripts/nas_cli.py test -p home-nas
```

### 2. Native Windows Drive Mounting (Recommended)
Mount your Synology share to a Windows drive letter (e.g., `Z:`):
```bash
# Mount
python .agents/skills/synology-nas-manager/scripts/nas_cli.py mount --share music --drive Z:

# Once mounted, both file_manager and audio_metadata work directly on Z:\ at full speed!
python .agents/skills/file-audio-manager/scripts/audio_metadata.py read Z:\Albums\track01.mp3

# List mounts or disconnect
python .agents/skills/synology-nas-manager/scripts/nas_cli.py mounts
python .agents/skills/synology-nas-manager/scripts/nas_cli.py unmount Z:
```

### 3. Remote File Transfer & Sync
```bash
# List files remotely
python .agents/skills/synology-nas-manager/scripts/nas_cli.py ls /volume1/music --protocol sftp

# Upload / Download
python .agents/skills/synology-nas-manager/scripts/nas_cli.py upload ./album /volume1/music/album
python .agents/skills/synology-nas-manager/scripts/nas_cli.py download /volume1/music/track.flac ./track.flac

# Directory mirror sync (with dry-run option)
python .agents/skills/synology-nas-manager/scripts/nas_cli.py sync ./data /volume1/data --dry-run
python .agents/skills/synology-nas-manager/scripts/nas_cli.py sync ./data /volume1/data --direction up
```

---

## 🤖 Reusable Antigravity Agent Integration

Because these skills are placed in `.agents/skills/`:
- Antigravity automatically detects both `file-audio-manager` and `synology-nas-manager`.
- Whenever you talk to the agent in this workspace (or share with your team via git), the agent can autonomously mount your NAS, organize your music files, read/write audio tags, or run batch syncs on demand.
