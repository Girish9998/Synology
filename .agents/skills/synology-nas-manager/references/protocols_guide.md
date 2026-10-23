# Synology Protocol Selection & Best Practices Guide

When managing files and audio tracks on a Synology NAS, different protocols offer unique trade-offs in speed, compatibility, and overhead.

## Protocol Comparison

| Dimension | SMB / CIFS | SFTP (SSH) | DSM REST API | WebDAV |
| :--- | :--- | :--- | :--- | :--- |
| **Best Used For** | Direct drive mount (`Z:`), seamless audio tagging | Bulk file transfer, directory sync, automated jobs | Administrative management, environments with only port 5000/5001 | Cross-platform cloud-like mounts |
| **Speed / Throughput** | High (native OS kernel caching) | Very High (direct SSH pipeline) | Moderate (HTTP multipart overhead) | Moderate (HTTP overhead) |
| **Random File Access** | Excellent (byte-range seeking for ID3 tags) | Requires full download or SFTP seek | Full download required | Partial range GET |
| **Network Port** | 445 | 22 (or custom) | 5000 (HTTP) / 5001 (HTTPS) | 5005 (HTTP) / 5006 (HTTPS) |
| **Prerequisites on Synology** | Control Panel > File Services > SMB enabled | Control Panel > Terminal & SNMP > Enable SSH | Always active with DSM | WebDAV Server package installed |

---

## Why SMB Drive Mounting is the Recommended Choice for Audio Tagging

Audio metadata formats (ID3v2, Vorbis Comments, MP4 atoms) are embedded directly within the audio file header or footer chunks:
- When a file is mounted over SMB (e.g. `Z:\music\track.mp3`), Mutagen can seek directly to the header, read/write 2 KB of tags, and flush changes **without transferring the entire 50MB-100MB audio file across the network**.
- Over DSM REST API or SFTP, changing a tag on an unmounted path usually requires transferring the full file down and re-uploading it.
- **Recommendation**:
  1. Mount the share using `nas_cli.py mount --share <folder>`.
  2. Use `audio_metadata.py` directly on the drive letter for instantaneous tag updates.
  3. Unmount when finished if desired.

---

## Security & Credential Storage

Credentials are protected using the standard Python `cryptography.fernet` symmetric encryption:
- Key location: `~/.nas_key`
- Encrypted profiles vault: `~/.nas_credentials`
- Passwords are never logged or exported in plain text via the CLI output.
