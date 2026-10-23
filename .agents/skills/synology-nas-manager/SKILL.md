---
name: synology-nas-manager
description: >-
  Use this skill when the user wants to authenticate, connect to, mount, browse,
  or perform CRUD file operations or directory sync on a Synology NAS. Supports
  multi-protocol connections (SMB/CIFS network share, SFTP/SSH, Synology DSM REST API,
  WebDAV) and encrypted credential profiles.
---

# Synology NAS Manager Skill

This skill provides multi-protocol connectivity, encrypted credential management, and remote file operations for Synology DiskStation (DSM) NAS devices.

## When to Use

Activate this skill when:
- Authenticating with a Synology NAS (saving or testing credentials).
- Mounting or unmounting a Synology network share to a Windows drive letter (e.g. `Z:`).
- Transferring, uploading, or downloading files between local machine and Synology NAS.
- Mirroring/syncing local folders with a NAS share.

> [!NOTE]
> Audio tagging and file metadata modifications are handled separately by the `file-audio-manager` skill. To edit audio tags on the NAS, mount the share as a Windows drive (`mount`) and run `file-audio-manager` directly on that drive.

---

## Architecture & Protocols

| Protocol | Best For | Typical Port | Command Flag |
| :--- | :--- | :--- | :--- |
| **SMB / CIFS** | **Windows native drive mounting** (`Z:`). Once mounted, any local tool (`file_manager.py`, `audio_metadata.py`, Explorer) operates transparently. | 445 | `--protocol smb` |
| **SFTP / SSH** | **High-speed transfers & directory sync** without needing drive mounting. Direct SSH credentials. | 22 | `--protocol sftp` |
| **DSM REST API** | Official Synology FileStation Web API. Operates over standard HTTP/HTTPS. Ideal when SSH is disabled. | 5000 / 5001 | `--protocol dsm` |
| **WebDAV** | Standard HTTP file storage alternative. | 5005 / 5006 | `--protocol webdav` |

Credentials are stored in a locally encrypted vault at `~/.nas_credentials` using Fernet symmetric encryption (`~/.nas_key`).

---

## Quick Reference Workflows

### 1. Profile Setup & Management
Profiles store encrypted host, username, password, and default share preferences.

```bash
# Add a profile interactively (password prompt is hidden)
python .agents/skills/synology-nas-manager/scripts/nas_cli.py profile add home-nas

# List all configured profiles
python .agents/skills/synology-nas-manager/scripts/nas_cli.py profile list

# Test connection across all protocols (DSM API, SFTP, SMB, WebDAV)
python .agents/skills/synology-nas-manager/scripts/nas_cli.py test -p home-nas
```

### 2. Mounting as a Windows Network Drive (Recommended for Transparent Access)
Mounting a Synology share to a Windows drive letter allows all standard local tools (and `file-audio-manager`) to work seamlessly:

```bash
# Mount 'music' share to next available drive letter or specific letter (e.g. Z:)
python .agents/skills/synology-nas-manager/scripts/nas_cli.py mount --share music --drive Z:

# List active network drive mappings
python .agents/skills/synology-nas-manager/scripts/nas_cli.py mounts

# Unmount when done
python .agents/skills/synology-nas-manager/scripts/nas_cli.py unmount Z:
```

### 3. Remote File Operations (SFTP / DSM API)
```bash
# List directory contents on the NAS
python .agents/skills/synology-nas-manager/scripts/nas_cli.py ls /volume1/music --protocol sftp

# Upload a file or folder
python .agents/skills/synology-nas-manager/scripts/nas_cli.py upload ./my_album /volume1/music/my_album

# Download a file from NAS
python .agents/skills/synology-nas-manager/scripts/nas_cli.py download /volume1/music/track01.flac ./track01.flac

# Create directory on NAS
python .agents/skills/synology-nas-manager/scripts/nas_cli.py mkdir /volume1/music/new_artist

# Delete file or directory
python .agents/skills/synology-nas-manager/scripts/nas_cli.py delete /volume1/music/old_track.mp3
```

### 4. Folder Sync (Local <-> NAS)
```bash
# Preview what would be uploaded (Dry Run)
python .agents/skills/synology-nas-manager/scripts/nas_cli.py sync ./data /volume1/data --dry-run

# Live upload sync
python .agents/skills/synology-nas-manager/scripts/nas_cli.py sync ./data /volume1/data --direction up
```

---

## Detailed References

- [Usage Examples & Guides](./examples/nas_usage.md)
- [Protocols & Networking Guide](./references/protocols_guide.md)
