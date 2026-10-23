# Synology NAS Manager Usage Examples

## Scenario 1: First-Time Setup & Testing

Add your NAS profile once. The password is encrypted and never stored in cleartext:

```bash
python .agents/skills/synology-nas-manager/scripts/nas_cli.py profile add ds920 \
  --host 192.168.1.100 \
  --username admin \
  --protocol smb \
  --share music \
  --default
```

Verify that all enabled protocols on your Synology are reachable:

```bash
python .agents/skills/synology-nas-manager/scripts/nas_cli.py test -p ds920
```

Sample output:
```text
╭────────────────── NAS Connection Test ──────────────────╮
│ Testing connectivity to ds920 (192.168.1.100) as admin  │
╰─────────────────────────────────────────────────────────╯
✔ DSM REST API: Connected successfully! Shares visible: music, video, photo
✔ SFTP / SSH (Port 22): Connected successfully! (12 items in home)
✔ SMB / CIFS: Successfully mounted \\192.168.1.100\music to Z:
▲ WebDAV: WebDAV service not responding or not enabled on NAS.
```

---

## Scenario 2: Native Drive Mounting (The Most Convenient Method)

Why mount? Mounting maps `\\192.168.1.100\music` to a local drive letter like `Z:`.
Once mounted, you don't need any special network commands—you can use `file-audio-manager` directly:

```bash
# 1. Mount the share
python .agents/skills/synology-nas-manager/scripts/nas_cli.py mount --share music --drive Z:

# 2. Use file_manager directly on Z:
python .agents/skills/file-audio-manager/scripts/file_manager.py list Z:\rock\

# 3. Read & write audio metadata directly without download/upload delays:
python .agents/skills/file-audio-manager/scripts/audio_metadata.py read Z:\rock\song.flac
python .agents/skills/file-audio-manager/scripts/audio_metadata.py write Z:\rock\song.flac --artist "Queen"

# 4. Unmount when done
python .agents/skills/synology-nas-manager/scripts/nas_cli.py unmount Z:
```

---

## Scenario 3: High-Speed Remote Sync over SFTP

If you keep music locally and want to mirror new tracks to your Synology:

```bash
# Test what files would sync
python .agents/skills/synology-nas-manager/scripts/nas_cli.py sync C:\Users\user\Data /volume1/data --dry-run

# Run the upload
python .agents/skills/synology-nas-manager/scripts/nas_cli.py sync C:\Users\user\Data /volume1/data --direction up
```
