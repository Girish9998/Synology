#!/usr/bin/env python3
"""
audio_metadata.py — Audio file metadata read/write CLI with rich terminal output.

Supported formats: MP3, FLAC, OGG, M4A/AAC, WAV

Usage:
    python scripts/audio_metadata.py <command> [options]

Commands:
    read        Read all tags from an audio file
    write       Write/update one or more tags on an audio file
    copy-tags   Copy all tags from one audio file to another
    clear       Clear specific or all tags from a file
    batch-read  Read metadata from all audio files in a directory
    batch-write Apply the same tag(s) to multiple audio files
    export      Export metadata to JSON or CSV
    import      Import metadata from JSON or CSV and apply to files
    artwork     Extract or embed cover art
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
import difflib
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests
import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ---------------------------------------------------------------------------
# Mutagen imports
# ---------------------------------------------------------------------------
try:
    import mutagen
    from mutagen import File as MutagenFile
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import (
        APIC, COMM, ID3, ID3NoHeaderError, TALB, TBPM, TCOM, TCON,
        TDRC, TIT2, TPE1, TPE2, TPOS, TRCK, USLT,
    )
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.oggvorbis import OggVorbis
    from mutagen.wave import WAVE
except ImportError:
    print("ERROR: mutagen is not installed. Run: pip install mutagen")
    sys.exit(1)

console = Console()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wav"}

# Mapping of friendly field names to format-specific handlers
FIELD_NAMES = [
    "title", "artist", "album", "albumartist", "tracknumber", "totaltracks",
    "discnumber", "totaldiscs", "year", "genre", "comment", "composer",
    "lyrics", "bpm",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def err(message: str) -> None:
    console.print(f"[bold red]✖ Error:[/bold red] {message}")


def ok(message: str) -> None:
    console.print(f"[bold green]✔[/bold green] {message}")


def warn(message: str) -> None:
    console.print(f"[bold yellow]⚠ Warning:[/bold yellow] {message}")


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def collect_audio_files(directory: Path, recursive: bool, ext_filter: Optional[str] = None) -> List[Path]:
    """Return all audio files in directory (optionally recursive)."""
    glob_fn = directory.rglob if recursive else directory.glob
    files = []
    for p in sorted(glob_fn("*")):
        if p.is_file() and is_audio_file(p):
            if ext_filter:
                if p.suffix.lstrip(".").lower() != ext_filter.lstrip(".").lower():
                    continue
            files.append(p)
    return files


# ---------------------------------------------------------------------------
# Tag Reader/Writer (format-agnostic interface)
# ---------------------------------------------------------------------------

class AudioFile:
    """
    Unified interface for reading and writing metadata across audio formats.
    Supports: MP3 (ID3), FLAC (Vorbis), OGG (Vorbis), M4A/AAC (MP4), WAV (ID3).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.ext = path.suffix.lower()
        self._audio = MutagenFile(path, easy=False)
        if self._audio is None:
            raise ValueError(f"Unsupported or unreadable format: {path}")

    @property
    def duration(self) -> Optional[float]:
        """Return length of audio in seconds."""
        if hasattr(self._audio, "info") and hasattr(self._audio.info, "length"):
            return float(self._audio.info.length)
        return None

    # ------------------------------------------------------------------
    # Internal: format-specific get/set
    # ------------------------------------------------------------------

    def _is_id3(self) -> bool:
        return self.ext in {".mp3", ".wav"}

    def _is_vorbis(self) -> bool:
        return self.ext in {".flac", ".ogg"}

    def _is_mp4(self) -> bool:
        return self.ext in {".m4a", ".aac"}

    # --- ID3 tag maps ---
    _ID3_GET: Dict[str, str] = {
        "title": "TIT2", "artist": "TPE1", "album": "TALB",
        "albumartist": "TPE2", "tracknumber": "TRCK", "discnumber": "TPOS",
        "year": "TDRC", "genre": "TCON", "composer": "TCOM", "bpm": "TBPM",
    }

    # --- MP4 tag maps ---
    _MP4_GET: Dict[str, str] = {
        "title": "\xa9nam", "artist": "\xa9ART", "album": "\xa9alb",
        "albumartist": "aART", "tracknumber": "trkn", "discnumber": "disk",
        "year": "\xa9day", "genre": "\xa9gen", "composer": "\xa9wrt",
        "bpm": "tmpo", "comment": "\xa9cmt", "lyrics": "\xa9lyr",
    }

    def _get_id3(self, field: str) -> Optional[str]:
        """Read a field from ID3 tags."""
        tag_id = self._ID3_GET.get(field)
        if tag_id and tag_id in self._audio:
            return str(self._audio[tag_id].text[0]) if hasattr(self._audio[tag_id], "text") else str(self._audio[tag_id])
        if field == "comment":
            for key in self._audio.keys():
                if key.startswith("COMM"):
                    return str(self._audio[key].text[0])
        if field == "lyrics":
            for key in self._audio.keys():
                if key.startswith("USLT"):
                    return str(self._audio[key].text)
        if field == "totaltracks":
            trck = self._audio.get("TRCK")
            if trck:
                parts = str(trck.text[0]).split("/")
                return parts[1] if len(parts) > 1 else None
        if field == "totaldiscs":
            tpos = self._audio.get("TPOS")
            if tpos:
                parts = str(tpos.text[0]).split("/")
                return parts[1] if len(parts) > 1 else None
        return None

    def _get_vorbis(self, field: str) -> Optional[str]:
        """Read a field from Vorbis Comment tags."""
        vorbis_map = {
            "title": "title", "artist": "artist", "album": "album",
            "albumartist": "albumartist", "tracknumber": "tracknumber",
            "totaltracks": "totaltracks", "discnumber": "discnumber",
            "totaldiscs": "totaldiscs", "year": "date", "genre": "genre",
            "comment": "comment", "composer": "composer", "lyrics": "lyrics",
            "bpm": "bpm",
        }
        key = vorbis_map.get(field)
        if key:
            vals = self._audio.get(key) or self._audio.get(key.upper())
            if vals:
                return vals[0]
        return None

    def _get_mp4(self, field: str) -> Optional[str]:
        """Read a field from MP4/iTunes tags."""
        tag_id = self._MP4_GET.get(field)
        if tag_id and tag_id in self._audio:
            val = self._audio[tag_id]
            if field in {"tracknumber", "discnumber"}:
                return str(val[0][0]) if val else None
            if field == "totaltracks":
                val2 = self._audio.get("\xa9nam")  # reuse trkn
                trkn = self._audio.get("trkn")
                return str(trkn[0][1]) if trkn and trkn[0][1] else None
            if field == "totaldiscs":
                disk = self._audio.get("disk")
                return str(disk[0][1]) if disk and disk[0][1] else None
            if isinstance(val, list):
                return str(val[0]) if val else None
            return str(val)
        if field == "totaltracks":
            trkn = self._audio.get("trkn")
            return str(trkn[0][1]) if trkn and len(trkn[0]) > 1 and trkn[0][1] else None
        if field == "totaldiscs":
            disk = self._audio.get("disk")
            return str(disk[0][1]) if disk and len(disk[0]) > 1 and disk[0][1] else None
        return None

    def get(self, field: str) -> Optional[str]:
        """Read a named tag field. Returns None if not present."""
        if self._is_id3():
            return self._get_id3(field)
        elif self._is_vorbis():
            return self._get_vorbis(field)
        elif self._is_mp4():
            return self._get_mp4(field)
        return None

    def get_all(self) -> Dict[str, Optional[str]]:
        """Return all supported tag fields as a dict."""
        return {field: self.get(field) for field in FIELD_NAMES}

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def _set_id3(self, field: str, value: str) -> None:
        """Write a field to ID3 tags."""
        if not hasattr(self._audio, "tags") or self._audio.tags is None:
            self._audio.add_tags()

        tag_map_cls = {
            "title": TIT2, "artist": TPE1, "album": TALB,
            "albumartist": TPE2, "year": TDRC, "genre": TCON,
            "composer": TCOM, "bpm": TBPM,
        }

        if field in tag_map_cls:
            cls = tag_map_cls[field]
            self._audio.tags[self._ID3_GET[field]] = cls(encoding=3, text=value)
        elif field == "tracknumber":
            total = self.get("totaltracks")
            trck_val = f"{value}/{total}" if total else str(value)
            self._audio.tags["TRCK"] = TRCK(encoding=3, text=trck_val)
        elif field == "totaltracks":
            num = self.get("tracknumber") or "0"
            self._audio.tags["TRCK"] = TRCK(encoding=3, text=f"{num}/{value}")
        elif field == "discnumber":
            total = self.get("totaldiscs")
            tpos_val = f"{value}/{total}" if total else str(value)
            self._audio.tags["TPOS"] = TPOS(encoding=3, text=tpos_val)
        elif field == "totaldiscs":
            num = self.get("discnumber") or "0"
            self._audio.tags["TPOS"] = TPOS(encoding=3, text=f"{num}/{value}")
        elif field == "comment":
            self._audio.tags["COMM::eng"] = COMM(encoding=3, lang="eng", desc="", text=value)
        elif field == "lyrics":
            self._audio.tags["USLT::eng"] = USLT(encoding=3, lang="eng", desc="", text=value)

    def _set_vorbis(self, field: str, value: str) -> None:
        """Write a field to Vorbis Comment tags."""
        vorbis_map = {
            "title": "title", "artist": "artist", "album": "album",
            "albumartist": "albumartist", "tracknumber": "tracknumber",
            "totaltracks": "totaltracks", "discnumber": "discnumber",
            "totaldiscs": "totaldiscs", "year": "date", "genre": "genre",
            "comment": "comment", "composer": "composer", "lyrics": "lyrics",
            "bpm": "bpm",
        }
        key = vorbis_map.get(field)
        if key:
            self._audio[key] = [value]

    def _set_mp4(self, field: str, value: str) -> None:
        """Write a field to MP4/iTunes tags."""
        if field == "tracknumber":
            total = int(self.get("totaltracks") or 0)
            self._audio["trkn"] = [(int(value), total)]
        elif field == "totaltracks":
            num = int(self.get("tracknumber") or 0)
            self._audio["trkn"] = [(num, int(value))]
        elif field == "discnumber":
            total = int(self.get("totaldiscs") or 0)
            self._audio["disk"] = [(int(value), total)]
        elif field == "totaldiscs":
            num = int(self.get("discnumber") or 0)
            self._audio["disk"] = [(num, int(value))]
        elif field == "bpm":
            self._audio["tmpo"] = [int(value)]
        else:
            tag_id = self._MP4_GET.get(field)
            if tag_id:
                self._audio[tag_id] = [value]

    def set(self, field: str, value: str) -> None:
        """Set a named tag field."""
        if self._is_id3():
            self._set_id3(field, value)
        elif self._is_vorbis():
            self._set_vorbis(field, value)
        elif self._is_mp4():
            self._set_mp4(field, value)

    def save(self) -> None:
        """Save changes to disk."""
        self._audio.save()

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def clear_field(self, field: str) -> None:
        """Remove a specific tag field."""
        if self._is_id3():
            tag_id = self._ID3_GET.get(field)
            if tag_id and tag_id in self._audio.tags:
                del self._audio.tags[tag_id]
            if field == "comment":
                for key in list(self._audio.tags.keys()):
                    if key.startswith("COMM"):
                        del self._audio.tags[key]
            if field == "lyrics":
                for key in list(self._audio.tags.keys()):
                    if key.startswith("USLT"):
                        del self._audio.tags[key]
        elif self._is_vorbis():
            vorbis_map = {
                "title": "title", "artist": "artist", "album": "album",
                "albumartist": "albumartist", "tracknumber": "tracknumber",
                "totaltracks": "totaltracks", "discnumber": "discnumber",
                "totaldiscs": "totaldiscs", "year": "date", "genre": "genre",
                "comment": "comment", "composer": "composer", "lyrics": "lyrics",
                "bpm": "bpm",
            }
            key = vorbis_map.get(field)
            if key and key in self._audio:
                del self._audio[key]
        elif self._is_mp4():
            tag_id = self._MP4_GET.get(field)
            if tag_id and tag_id in self._audio:
                del self._audio[tag_id]

    def clear_all(self) -> None:
        """Remove ALL tags from the file."""
        if self._is_id3():
            if self._audio.tags:
                self._audio.tags.clear()
        elif self._is_vorbis():
            for key in list(self._audio.keys()):
                if not key.startswith("METADATA_BLOCK_PICTURE"):
                    del self._audio[key]
        elif self._is_mp4():
            for key in list(self._audio.keys()):
                del self._audio[key]

    # ------------------------------------------------------------------
    # Cover Art
    # ------------------------------------------------------------------

    def get_cover(self) -> Optional[bytes]:
        """Return cover art bytes or None."""
        if self._is_id3():
            for key in self._audio.tags.keys() if self._audio.tags else []:
                if key.startswith("APIC"):
                    return self._audio.tags[key].data
        elif self.ext == ".flac":
            pics = self._audio.pictures
            if pics:
                return pics[0].data
        elif self._is_vorbis():
            import base64
            from mutagen.flac import Picture
            for b64 in self._audio.get("metadata_block_picture", []):
                try:
                    pic = Picture(base64.b64decode(b64))
                    return pic.data
                except Exception:
                    pass
        elif self._is_mp4():
            covers = self._audio.get("covr")
            if covers:
                return bytes(covers[0])
        return None

    def set_cover(self, image_bytes: bytes, mime: str = "image/jpeg") -> None:
        """Embed cover art."""
        if self._is_id3():
            if self._audio.tags is None:
                self._audio.add_tags()
            self._audio.tags["APIC"] = APIC(
                encoding=3, mime=mime, type=3, desc="Cover", data=image_bytes
            )
        elif self.ext == ".flac":
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.data = image_bytes
            self._audio.clear_pictures()
            self._audio.add_picture(pic)
        elif self._is_vorbis():
            import base64
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.data = image_bytes
            self._audio["metadata_block_picture"] = [
                base64.b64encode(pic.write()).decode("ascii")
            ]
        elif self._is_mp4():
            fmt = MP4Cover.FORMAT_JPEG if "jpeg" in mime or "jpg" in mime else MP4Cover.FORMAT_PNG
            self._audio["covr"] = [MP4Cover(image_bytes, imageformat=fmt)]


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """
    \b
    ╔══════════════════════════════════════╗
    ║   Audio Metadata Manager  🎵         ║
    ╚══════════════════════════════════════╝

    Read and write metadata tags for MP3, FLAC, OGG, M4A, AAC, and WAV files.
    """


# ---------------------------------------------------------------------------
# Tag field options (shared across commands)
# ---------------------------------------------------------------------------

def tag_options(fn):
    """Decorator to attach all tag field options to a command."""
    for field in reversed(FIELD_NAMES):
        fn = click.option(f"--{field}", default=None, help=f"Set the {field} tag.")(fn)
    return fn


def collect_tags(**kwargs) -> Dict[str, str]:
    """Extract non-None tag values from kwargs."""
    return {k: v for k, v in kwargs.items() if k in FIELD_NAMES and v is not None}


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------

@cli.command("read")
@click.argument("file", type=click.Path(exists=True))
@click.option("--field", "-f", default=None, help="Read only a specific field (e.g. title).")
def cmd_read(file: str, field: Optional[str]) -> None:
    """Read metadata tags from an audio FILE."""
    path = Path(file).resolve()
    if not is_audio_file(path):
        err(f"Unsupported format '{path.suffix}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        sys.exit(1)

    try:
        af = AudioFile(path)
    except Exception as exc:
        err(str(exc))
        sys.exit(1)

    if field:
        val = af.get(field)
        if val is None:
            warn(f"Field '{field}' is not set.")
        else:
            console.print(f"[bold cyan]{field}[/bold cyan]: {val}")
        return

    tags = af.get_all()
    has_cover = af.get_cover() is not None

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Field", style="bold cyan", width=16)
    table.add_column("Value", style="white")

    for f_name, value in tags.items():
        display = str(value) if value else "[dim](not set)[/dim]"
        table.add_row(f_name, display)

    table.add_row("cover", "[green]✔ embedded[/green]" if has_cover else "[dim](not set)[/dim]")

    console.print(Panel(
        table,
        title=f"[bold cyan]🎵 {path.name}[/bold cyan]  [dim]({path.suffix.upper()[1:]})[/dim]",
        border_style="cyan",
    ))


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------

@cli.command("write")
@click.argument("file", type=click.Path(exists=True))
@tag_options
def cmd_write(file: str, **kwargs) -> None:
    """Write/update tags on an audio FILE. Specify tags as options."""
    path = Path(file).resolve()
    if not is_audio_file(path):
        err(f"Unsupported format '{path.suffix}'.")
        sys.exit(1)

    tags_to_write = collect_tags(**kwargs)
    if not tags_to_write:
        warn("No tag fields specified. Use --title, --artist, etc.")
        return

    try:
        af = AudioFile(path)
        for field, value in tags_to_write.items():
            af.set(field, value)
        af.save()
    except Exception as exc:
        err(f"Failed to write tags: {exc}")
        sys.exit(1)

    ok(f"Updated [bold]{path.name}[/bold] — fields: {', '.join(tags_to_write.keys())}")


# ---------------------------------------------------------------------------
# copy-tags
# ---------------------------------------------------------------------------

@cli.command("copy-tags")
@click.argument("src", type=click.Path(exists=True))
@click.argument("dst", type=click.Path(exists=True))
@click.option("--skip-missing", is_flag=True, default=False,
              help="Skip fields that are not set in the source.")
def cmd_copy_tags(src: str, dst: str, skip_missing: bool) -> None:
    """Copy all tags from SRC audio file to DST audio file."""
    src_path = Path(src).resolve()
    dst_path = Path(dst).resolve()

    for p in (src_path, dst_path):
        if not is_audio_file(p):
            err(f"Unsupported format: {p.suffix}")
            sys.exit(1)

    try:
        src_af = AudioFile(src_path)
        dst_af = AudioFile(dst_path)
    except Exception as exc:
        err(str(exc))
        sys.exit(1)

    tags = src_af.get_all()
    copied = []
    for field, value in tags.items():
        if value is None:
            if not skip_missing:
                dst_af.clear_field(field)
            continue
        dst_af.set(field, value)
        copied.append(field)

    # Copy cover art
    cover = src_af.get_cover()
    if cover:
        dst_af.set_cover(cover)
        copied.append("cover")

    try:
        dst_af.save()
    except Exception as exc:
        err(f"Failed to save: {exc}")
        sys.exit(1)

    ok(f"Copied tags from [bold]{src_path.name}[/bold] → [bold]{dst_path.name}[/bold]")
    console.print(f"  Fields copied: [dim]{', '.join(copied)}[/dim]")


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

@cli.command("clear")
@click.argument("file", type=click.Path(exists=True))
@click.option("--fields", "-f", multiple=True, help="Specific field(s) to clear (repeatable).")
@click.option("--all", "clear_all", is_flag=True, default=False, help="Clear ALL tags.")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation.")
def cmd_clear(file: str, fields: tuple, clear_all: bool, force: bool) -> None:
    """Clear tags from an audio FILE."""
    path = Path(file).resolve()
    if not is_audio_file(path):
        err(f"Unsupported format: {path.suffix}")
        sys.exit(1)

    if not clear_all and not fields:
        err("Specify --fields <field> or --all.")
        sys.exit(1)

    action = "ALL tags" if clear_all else f"fields: {', '.join(fields)}"
    if not force:
        confirm = click.confirm(f"Clear {action} from {path.name}?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            return

    try:
        af = AudioFile(path)
        if clear_all:
            af.clear_all()
        else:
            for field in fields:
                af.clear_field(field)
        af.save()
    except Exception as exc:
        err(str(exc))
        sys.exit(1)

    ok(f"Cleared {action} from [bold]{path.name}[/bold]")


# ---------------------------------------------------------------------------
# batch-read
# ---------------------------------------------------------------------------

@cli.command("batch-read")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive", "-r", is_flag=True, default=False)
@click.option("--ext", "-e", default=None, help="Filter by extension (e.g. mp3).")
@click.option("--fields", "-f", multiple=True, default=None,
              help="Fields to display (default: title, artist, album).")
def cmd_batch_read(directory: str, recursive: bool, ext: Optional[str], fields: tuple) -> None:
    """Read metadata from all audio files in DIRECTORY."""
    root = Path(directory).resolve()
    files = collect_audio_files(root, recursive, ext)

    if not files:
        warn(f"No supported audio files found in {root}.")
        return

    display_fields = list(fields) if fields else ["title", "artist", "album", "year", "genre"]

    table = Table(
        title=f"[bold cyan]🎵 Batch Read — {root}[/bold cyan]  [dim]({len(files)} files)[/dim]",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("File", style="bold white", no_wrap=True, max_width=30)
    for f_name in display_fields:
        table.add_column(f_name.capitalize(), style="white")

    for file_path in files:
        try:
            af = AudioFile(file_path)
            row = [file_path.name]
            for f_name in display_fields:
                val = af.get(f_name)
                row.append(val or "[dim]-[/dim]")
            table.add_row(*row)
        except Exception:
            table.add_row(file_path.name, *["[red]ERR[/red]"] * len(display_fields))

    console.print(table)


# ---------------------------------------------------------------------------
# batch-write
# ---------------------------------------------------------------------------

@cli.command("batch-write")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--recursive", "-r", is_flag=True, default=False)
@click.option("--ext", "-e", default=None, help="Filter by extension.")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation.")
@tag_options
def cmd_batch_write(directory: str, recursive: bool, ext: Optional[str], force: bool, **kwargs) -> None:
    """Apply the same tag(s) to all audio files in DIRECTORY."""
    root = Path(directory).resolve()
    tags_to_write = collect_tags(**kwargs)

    if not tags_to_write:
        warn("No tag fields specified.")
        return

    files = collect_audio_files(root, recursive, ext)
    if not files:
        warn("No supported audio files found.")
        return

    if not force:
        confirm = click.confirm(
            f"Apply {list(tags_to_write.keys())} to {len(files)} file(s)?",
            default=False,
        )
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            return

    success = 0
    for file_path in files:
        try:
            af = AudioFile(file_path)
            for field, value in tags_to_write.items():
                af.set(field, value)
            af.save()
            success += 1
        except Exception as exc:
            warn(f"Skipped {file_path.name}: {exc}")

    ok(f"Updated {success}/{len(files)} file(s) with: {', '.join(tags_to_write.keys())}")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

@cli.command("export")
@click.argument("source", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["json", "csv"]), default="json", show_default=True)
@click.option("--output", "-o", default=None, help="Output file path (default: stdout).")
@click.option("--recursive", "-r", is_flag=True, default=False)
def cmd_export(source: str, fmt: str, output: Optional[str], recursive: bool) -> None:
    """Export audio metadata to JSON or CSV."""
    path = Path(source).resolve()

    if path.is_file():
        if not is_audio_file(path):
            err(f"Unsupported format: {path.suffix}")
            sys.exit(1)
        files = [path]
    else:
        files = collect_audio_files(path, recursive)

    if not files:
        warn("No audio files found.")
        return

    records = []
    for file_path in files:
        try:
            af = AudioFile(file_path)
            record = {"file": str(file_path)}
            record.update({k: v for k, v in af.get_all().items()})
            records.append(record)
        except Exception as exc:
            warn(f"Skipped {file_path.name}: {exc}")

    if fmt == "json":
        content = json.dumps(records, indent=2, ensure_ascii=False)
    else:
        buf = io.StringIO()
        fieldnames = ["file"] + FIELD_NAMES
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
        content = buf.getvalue()

    if output:
        out_path = Path(output)
        out_path.write_text(content, encoding="utf-8")
        ok(f"Exported {len(records)} record(s) to [bold]{out_path}[/bold]")
    else:
        console.print(content)


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

@cli.command("import")
@click.argument("metadata_file", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, default=False, help="Preview changes without saving.")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation.")
def cmd_import(metadata_file: str, dry_run: bool, force: bool) -> None:
    """Import metadata from a JSON or CSV file and apply to audio files."""
    meta_path = Path(metadata_file).resolve()
    content = meta_path.read_text(encoding="utf-8")

    if meta_path.suffix.lower() == ".json":
        records = json.loads(content)
    elif meta_path.suffix.lower() == ".csv":
        reader = csv.DictReader(io.StringIO(content))
        records = list(reader)
    else:
        err("Unsupported metadata file format. Use .json or .csv")
        sys.exit(1)

    if not records:
        warn("No records found in metadata file.")
        return

    if not force and not dry_run:
        confirm = click.confirm(f"Apply metadata to {len(records)} file(s)?", default=False)
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            return

    success = 0
    for record in records:
        file_path = Path(record.get("file", ""))
        if not file_path.exists():
            warn(f"File not found: {file_path}")
            continue
        if not is_audio_file(file_path):
            warn(f"Unsupported format: {file_path}")
            continue

        tags = {k: v for k, v in record.items() if k in FIELD_NAMES and v}

        if dry_run:
            console.print(f"[dim]DRY RUN:[/dim] Would update [bold]{file_path.name}[/bold]: {tags}")
            success += 1
            continue

        try:
            af = AudioFile(file_path)
            for field, value in tags.items():
                af.set(field, value)
            af.save()
            success += 1
        except Exception as exc:
            warn(f"Failed {file_path.name}: {exc}")

    action = "Would update" if dry_run else "Updated"
    ok(f"{action} {success}/{len(records)} file(s).")


# ---------------------------------------------------------------------------
# artwork
# ---------------------------------------------------------------------------

@cli.command("artwork")
@click.argument("file", type=click.Path(exists=True))
@click.option("--extract", is_flag=True, default=False, help="Extract cover art from file.")
@click.option("--embed", type=click.Path(exists=True), default=None,
              help="Embed an image file as cover art.")
@click.option("--output", "-o", default=None, help="Output path for extracted cover art.")
def cmd_artwork(file: str, extract: bool, embed: Optional[str], output: Optional[str]) -> None:
    """Extract or embed cover art for an audio FILE."""
    path = Path(file).resolve()
    if not is_audio_file(path):
        err(f"Unsupported format: {path.suffix}")
        sys.exit(1)

    try:
        af = AudioFile(path)
    except Exception as exc:
        err(str(exc))
        sys.exit(1)

    if extract:
        cover_data = af.get_cover()
        if not cover_data:
            warn(f"No cover art found in {path.name}.")
            return
        out_path = Path(output) if output else path.with_suffix(".jpg")
        out_path.write_bytes(cover_data)
        ok(f"Cover art extracted: [bold]{out_path}[/bold] ({len(cover_data):,} bytes)")

    elif embed:
        img_path = Path(embed).resolve()
        suffix = img_path.suffix.lower()
        mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        image_bytes = img_path.read_bytes()
        try:
            af.set_cover(image_bytes, mime=mime)
            af.save()
        except Exception as exc:
            err(f"Failed to embed cover art: {exc}")
            sys.exit(1)
        ok(f"Cover art embedded into [bold]{path.name}[/bold] from [bold]{img_path.name}[/bold]")

    else:
        err("Specify --extract or --embed <image_path>.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# iTunes Search & Matching Engine
# ---------------------------------------------------------------------------

def clean_filename_for_search(name: str) -> str:
    """Strip website tags, rip groups, bitrates, track numbers, and noise from filename."""
    stem = Path(name).stem
    s = re.sub(r'\(webmusic\.in\)_?', '', stem, flags=re.IGNORECASE)
    s = re.sub(r'\[(DoReGaMa|DRGM|Songs\.PK|Tamildownloads|HindiMp3|HP|XXX|Mp3~320kbps)\]', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\((webmusic|HindiMp3|DoReGaMa|DRGM)\.[^)]+\)', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\[.*?\]|\(.*?\)', '', s)
    s = re.sub(r'(?i)\b(128kbps|320kbps|kbps|vbr|dregama|drgm|songspk|tamildownloads\.net|hindimp3\.mobi)\b', '', s)
    s = re.sub(r'(?i)\b(official|video|lyrics|lyric|audio|visualizer|full song|hd|4k|remaster|remastered)\b', '', s)
    s = re.sub(r'^\s*\d{1,3}\s*[-_.]*\s*', '', s)
    s = s.replace('_', ' ').replace('-', ' ').replace('.', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def string_similarity(a: str, b: str) -> float:
    """Calculate normalized string similarity ratio."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def score_candidate(
    track: Dict[str, Any],
    query: str,
    local_title: str,
    local_artist: str,
    local_duration_sec: Optional[float]
) -> float:
    """Compute confidence match score (0 - 100) between local file and iTunes track."""
    itunes_title = track.get("trackName", "")
    t_sim = max(
        string_similarity(itunes_title, local_title),
        string_similarity(itunes_title, query)
    )
    title_score = t_sim * 40.0

    itunes_artist = track.get("artistName", "")
    if local_artist:
        a_sim = max(
            string_similarity(itunes_artist, local_artist),
            0.8 if local_artist.lower() in itunes_artist.lower() or itunes_artist.lower() in local_artist.lower() else 0.0
        )
    else:
        a_sim = 0.6 if itunes_artist.lower() in query.lower() else 0.2
    artist_score = a_sim * 30.0

    duration_score = 0.0
    if local_duration_sec and track.get("trackTimeMillis"):
        itunes_sec = track["trackTimeMillis"] / 1000.0
        delta = abs(local_duration_sec - itunes_sec)
        if delta <= 2.5:
            duration_score = 30.0
        elif delta <= 5.0:
            duration_score = 25.0
        elif delta <= 10.0:
            duration_score = 15.0
        elif delta <= 20.0:
            duration_score = 5.0
        else:
            duration_score = 0.0
    else:
        duration_score = 15.0

    return round(min(100.0, title_score + artist_score + duration_score), 1)


def search_itunes_candidates(
    queries: List[str],
    local_title: str,
    local_artist: str,
    local_duration_sec: Optional[float],
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Search iTunes API using multiple fallback queries and rank by confidence score."""
    seen_track_ids = set()
    ranked_candidates = []

    for q in queries:
        if not q or len(q.strip()) < 2:
            continue
        try:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(q.strip())}&entity=song&limit={limit}"
            resp = requests.get(url, timeout=7)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for item in data.get("results", []):
                t_id = item.get("trackId")
                if t_id and t_id in seen_track_ids:
                    continue
                seen_track_ids.add(t_id)

                score = score_candidate(item, q, local_title, local_artist, local_duration_sec)
                itunes_sec = item.get("trackTimeMillis", 0) / 1000.0
                dur_diff = abs(local_duration_sec - itunes_sec) if local_duration_sec else None

                art_100 = item.get("artworkUrl100", "")
                art_1000 = art_100.replace("100x100bb", "1000x1000bb") if art_100 else None

                ranked_candidates.append({
                    "track_id": t_id,
                    "title": item.get("trackName", ""),
                    "artist": item.get("artistName", ""),
                    "album": item.get("collectionName", ""),
                    "albumartist": item.get("collectionArtistName") or item.get("artistName", ""),
                    "year": item.get("releaseDate", "")[:4] if item.get("releaseDate") else "",
                    "genre": item.get("primaryGenreName", ""),
                    "track_number": str(item.get("trackNumber", "")),
                    "total_tracks": str(item.get("trackCount", "")),
                    "duration_sec": itunes_sec,
                    "duration_diff": dur_diff,
                    "artwork_url_1000": art_1000,
                    "confidence": score,
                    "raw": item
                })
        except Exception:
            continue

        if ranked_candidates and max(c["confidence"] for c in ranked_candidates) >= 85.0:
            break

    ranked_candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return ranked_candidates


def fetch_image_bytes(url: str) -> Optional[bytes]:
    """Download image bytes from URL."""
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
            return resp.content
    except Exception:
        pass
    return None


def get_file_queries(path: Path, af: AudioFile, custom_query: Optional[str]) -> Tuple[List[str], str, str]:
    """Build prioritized search queries based on existing tags, filename, and folder context."""
    if custom_query:
        return [custom_query], "", ""

    existing_title = af.get("title") or ""
    existing_artist = af.get("artist") or ""
    cleaned_filename = clean_filename_for_search(path.name)

    queries = []
    # 1. Existing title + artist if present
    if existing_title and existing_artist:
        queries.append(f"{existing_title} {existing_artist}")
    elif existing_title:
        queries.append(existing_title)

    # 2. Cleaned filename with parent folder context (movie/album hint)
    parent_name = path.parent.name
    if parent_name and parent_name.lower() not in {"music", "downloads", "desktop", "temp"}:
        cleaned_parent = clean_filename_for_search(parent_name)
        queries.append(f"{cleaned_filename} {cleaned_parent}")

    # 3. Cleaned filename alone
    queries.append(cleaned_filename)

    return queries, existing_title, existing_artist


# ---------------------------------------------------------------------------
# auto-tag & fetch-art commands
# ---------------------------------------------------------------------------

@cli.command("auto-tag")
@click.argument("target", type=click.Path(exists=True))
@click.option("--query", "-q", default=None, help="Custom search term override.")
@click.option("--min-confidence", type=float, default=60.0, help="Minimum confidence score (0-100) to accept a match.")
@click.option("--recursive", "-r", is_flag=True, default=False, help="Process directory recursively.")
@click.option("--interactive", "-i", is_flag=True, default=False, help="Prompt to select from top matches.")
@click.option("--dry-run", is_flag=True, default=False, help="Show matches without saving changes.")
@click.option("--albumartist", default=None, help="Force a specific album artist (e.g. 'A.R. Rahman').")
@click.option("--force", "-f", is_flag=True, default=False, help="Skip confirmation prompt.")
def cmd_auto_tag(target: str, query: Optional[str], min_confidence: float, recursive: bool, interactive: bool, dry_run: bool, albumartist: Optional[str], force: bool) -> None:
    """Automatically look up and apply official iTunes metadata & 1000x1000 artwork."""
    target_path = Path(target).resolve()
    files = [target_path] if target_path.is_file() else collect_audio_files(target_path, recursive)

    if not files:
        warn("No supported audio files found.")
        return

    console.print(f"[bold cyan]🔍 Auto-tagging {len(files)} file(s) via iTunes...[/bold cyan]")

    updated_count = 0
    for file_path in files:
        try:
            af = AudioFile(file_path)
        except Exception as exc:
            warn(f"Skipping {file_path.name}: {exc}")
            continue

        queries, local_title, local_artist = get_file_queries(file_path, af, query)
        local_dur = af.duration

        candidates = search_itunes_candidates(queries, local_title, local_artist, local_dur)
        if not candidates:
            console.print(f"[yellow]▲ No matches found for:[/yellow] {file_path.name}")
            continue

        chosen = None
        top = candidates[0]

        if interactive and len(candidates) > 1:
            table = Table(title=f"Candidates for: {file_path.name}")
            table.add_column("#", justify="center")
            table.add_column("Title", style="bold cyan")
            table.add_column("Artist", style="yellow")
            table.add_column("Album", style="white")
            table.add_column("Duration Diff", justify="right")
            table.add_column("Confidence", justify="right", style="green")

            for idx, c in enumerate(candidates[:3], start=1):
                diff_str = f"{c['duration_diff']:.1f}s" if c['duration_diff'] is not None else "N/A"
                table.add_row(str(idx), c["title"], c["artist"], c["album"], diff_str, f"{c['confidence']}%")
            console.print(table)

            choice = click.prompt("Select candidate [1-3, or 0 to skip]", default=1, type=int)
            if 1 <= choice <= min(3, len(candidates)):
                chosen = candidates[choice - 1]
            else:
                continue
        else:
            if top["confidence"] >= min_confidence:
                chosen = top
            else:
                console.print(f"[yellow]▲ Low confidence ({top['confidence']}%) for:[/yellow] {file_path.name} -> Best: '{top['title']}' by {top['artist']}")
                continue

        diff_disp = f"(Duration diff: {chosen['duration_diff']:.1f}s)" if chosen['duration_diff'] is not None else ""
        console.print(f"[bold green]✔ Match ({chosen['confidence']}%):[/bold green] [bold]{chosen['title']}[/bold] by [cyan]{chosen['artist']}[/cyan] — [dim]{chosen['album']} {diff_disp}[/dim]")

        if dry_run:
            continue

        # Apply metadata
        af.set("title", chosen["title"])
        af.set("artist", chosen["artist"])
        af.set("album", chosen["album"])
        if albumartist:
            af.set("albumartist", albumartist)
        elif chosen.get("albumartist"):
            af.set("albumartist", chosen["albumartist"])
        if chosen.get("year"):
            af.set("year", chosen["year"])
        if chosen.get("genre"):
            af.set("genre", chosen["genre"])
        if chosen.get("track_number"):
            af.set("tracknumber", chosen["track_number"])
        if chosen.get("total_tracks"):
            af.set("totaltracks", chosen["total_tracks"])

        # Fetch and embed high-res 1000x1000 artwork
        if chosen.get("artwork_url_1000"):
            art_bytes = fetch_image_bytes(chosen["artwork_url_1000"])
            if art_bytes:
                af.set_cover(art_bytes, mime="image/jpeg")

        try:
            af.save()
            updated_count += 1
        except Exception as exc:
            err(f"Failed to save {file_path.name}: {exc}")

    if not dry_run:
        ok(f"Successfully auto-tagged {updated_count}/{len(files)} file(s) with iTunes metadata and 1000x1000 artwork!")


@cli.command("fetch-art")
@click.argument("target", type=click.Path(exists=True))
@click.option("--query", "-q", default=None, help="Custom search term override.")
@click.option("--min-confidence", type=float, default=60.0, help="Minimum confidence score (0-100) to accept a match.")
@click.option("--recursive", "-r", is_flag=True, default=False, help="Process directory recursively.")
@click.option("--dry-run", is_flag=True, default=False, help="Preview artwork match without embedding.")
def cmd_fetch_art(target: str, query: Optional[str], min_confidence: float, recursive: bool, dry_run: bool) -> None:
    """Fetch and embed 1000x1000 cover art from iTunes while preserving all existing text tags."""
    target_path = Path(target).resolve()
    files = [target_path] if target_path.is_file() else collect_audio_files(target_path, recursive)

    if not files:
        warn("No supported audio files found.")
        return

    console.print(f"[bold cyan]🎨 Fetching high-res 1000x1000 cover art for {len(files)} file(s)...[/bold cyan]")

    updated_count = 0
    for file_path in files:
        try:
            af = AudioFile(file_path)
        except Exception as exc:
            warn(f"Skipping {file_path.name}: {exc}")
            continue

        queries, local_title, local_artist = get_file_queries(file_path, af, query)
        local_dur = af.duration

        candidates = search_itunes_candidates(queries, local_title, local_artist, local_dur)
        if not candidates or candidates[0]["confidence"] < min_confidence:
            console.print(f"[yellow]▲ No high-confidence artwork match for:[/yellow] {file_path.name}")
            continue

        chosen = candidates[0]
        if not chosen.get("artwork_url_1000"):
            continue

        diff_disp = f"(Duration diff: {chosen['duration_diff']:.1f}s)" if chosen['duration_diff'] is not None else ""
        console.print(f"[green]✔ Matched Art ({chosen['confidence']}%):[/green] [bold]{chosen['title']}[/bold] by [cyan]{chosen['artist']}[/cyan] {diff_disp}")

        if dry_run:
            continue

        art_bytes = fetch_image_bytes(chosen["artwork_url_1000"])
        if art_bytes:
            af.set_cover(art_bytes, mime="image/jpeg")
            try:
                af.save()
                updated_count += 1
            except Exception as exc:
                err(f"Failed to save {file_path.name}: {exc}")

    if not dry_run:
        ok(f"Successfully embedded 1000x1000 artwork into {updated_count}/{len(files)} file(s)!")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
