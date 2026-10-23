#!/usr/bin/env python3
"""
file_manager.py — General-purpose file CRUD CLI with rich terminal output.

Usage:
    python scripts/file_manager.py <command> [options]

Commands:
    list    List files/directories in a path
    create  Create a file or directory
    read    Read and display file content
    copy    Copy a file or directory
    move    Move a file or directory
    delete  Delete a file or directory
    rename  Rename a file or directory
    info    Show detailed file metadata
    search  Search for files by name, extension, or content
"""

from __future__ import annotations

import fnmatch
import mimetypes
import os
import re
import shutil
import stat
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_size(size_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


def format_timestamp(ts: float) -> str:
    """Format a POSIX timestamp as a readable datetime string."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def format_permissions(mode: int) -> str:
    """Return a Unix-style permission string like 'rwxr-xr-x'."""
    perms = ""
    for who in (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
                stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
                stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH):
        perms += "rwxrwxrwx"[list((stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
                                    stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
                                    stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH)).index(who)] \
            if mode & who else "-"
    return perms


def err(message: str) -> None:
    """Print a styled error message and exit."""
    console.print(f"[bold red]✖ Error:[/bold red] {message}")


def ok(message: str) -> None:
    """Print a styled success message."""
    console.print(f"[bold green]✔[/bold green] {message}")


def warn(message: str) -> None:
    """Print a styled warning message."""
    console.print(f"[bold yellow]⚠ Warning:[/bold yellow] {message}")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """
    \b
    ╔══════════════════════════════════╗
    ║      File Manager CLI  📁        ║
    ╚══════════════════════════════════╝

    A rich terminal file management tool supporting CRUD operations,
    search, metadata inspection, and more.
    """


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@cli.command("list")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--ext", "-e", default=None, help="Filter by file extension (e.g. mp3).")
@click.option("--pattern", "-p", default=None, help="Glob pattern filter (e.g. '*.log').")
@click.option("--recursive", "-r", is_flag=True, default=False, help="List recursively.")
@click.option("--dirs-only", is_flag=True, default=False, help="Show only directories.")
@click.option("--files-only", is_flag=True, default=False, help="Show only files.")
def cmd_list(
    path: str,
    ext: Optional[str],
    pattern: Optional[str],
    recursive: bool,
    dirs_only: bool,
    files_only: bool,
) -> None:
    """List files and directories in PATH."""
    root = Path(path).resolve()

    glob_fn = root.rglob if recursive else root.glob
    glob_pattern = pattern or "*"
    entries = sorted(glob_fn(glob_pattern), key=lambda p: (p.is_file(), p.name.lower()))

    table = Table(
        title=f"[bold cyan]📂 {root}[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Name", style="bold white", no_wrap=True)
    table.add_column("Type", style="cyan", width=6)
    table.add_column("Size", justify="right", style="yellow")
    table.add_column("Modified", style="dim")
    table.add_column("Permissions", style="dim")

    count = 0
    for entry in entries:
        if dirs_only and entry.is_file():
            continue
        if files_only and entry.is_dir():
            continue
        if ext and entry.is_file() and entry.suffix.lstrip(".").lower() != ext.lstrip(".").lower():
            continue

        try:
            st = entry.stat()
        except (PermissionError, OSError):
            continue

        kind = "DIR" if entry.is_dir() else "FILE"
        size_str = "-" if entry.is_dir() else format_size(st.st_size)
        mod = format_timestamp(st.st_mtime)
        perms = format_permissions(st.st_mode)
        rel = entry.relative_to(root) if recursive else entry.name

        icon = "📁" if entry.is_dir() else "📄"
        name_style = "bold blue" if entry.is_dir() else "white"
        table.add_row(
            Text(f"{icon} {rel}", style=name_style),
            kind,
            size_str,
            mod,
            perms,
        )
        count += 1

    console.print(table)
    console.print(f"\n[dim]{count} item(s) found.[/dim]")


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

@cli.command("create")
@click.argument("path", type=click.Path())
@click.option("--dir", "is_dir", is_flag=True, default=False, help="Create a directory instead of a file.")
@click.option("--content", "-c", default="", help="Initial text content for the file.")
@click.option("--parents", is_flag=True, default=True, help="Create parent directories as needed.")
def cmd_create(path: str, is_dir: bool, content: str, parents: bool) -> None:
    """Create a FILE or DIRECTORY at PATH."""
    target = Path(path).resolve()
    try:
        if is_dir:
            target.mkdir(parents=parents, exist_ok=False)
            ok(f"Directory created: [bold]{target}[/bold]")
        else:
            if parents:
                target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                err(f"File already exists: {target}")
                sys.exit(1)
            target.write_text(content, encoding="utf-8")
            ok(f"File created: [bold]{target}[/bold] ({format_size(len(content.encode()))})")
    except FileExistsError:
        err(f"Path already exists: {target}")
        sys.exit(1)
    except PermissionError:
        err(f"Permission denied: {target}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------

@cli.command("read")
@click.argument("path", type=click.Path(exists=True))
@click.option("--lines", "-n", default=0, type=int, help="Limit output to N lines (0 = all).")
@click.option("--encoding", default="utf-8", show_default=True, help="File encoding.")
def cmd_read(path: str, lines: int, encoding: str) -> None:
    """Read and display the content of FILE at PATH."""
    target = Path(path).resolve()
    if target.is_dir():
        err(f"{target} is a directory, not a file.")
        sys.exit(1)
    try:
        text = target.read_text(encoding=encoding, errors="replace")
    except PermissionError:
        err(f"Permission denied: {target}")
        sys.exit(1)

    content_lines = text.splitlines()
    if lines > 0:
        content_lines = content_lines[:lines]
        text = "\n".join(content_lines)

    total_lines = len(content_lines)
    title = f"[bold cyan]📄 {target.name}[/bold cyan]  [dim]({total_lines} lines)[/dim]"
    console.print(Panel(text, title=title, border_style="blue", expand=False))


# ---------------------------------------------------------------------------
# copy
# ---------------------------------------------------------------------------

@cli.command("copy")
@click.argument("src", type=click.Path(exists=True))
@click.argument("dst", type=click.Path())
@click.option("--recursive", "-r", is_flag=True, default=False,
              help="Copy a directory tree recursively.")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite destination if it exists.")
def cmd_copy(src: str, dst: str, recursive: bool, overwrite: bool) -> None:
    """Copy SRC to DST (file or directory)."""
    source = Path(src).resolve()
    destination = Path(dst).resolve()

    try:
        if source.is_dir():
            if not recursive:
                err("Source is a directory. Use --recursive to copy directories.")
                sys.exit(1)
            if destination.exists() and not overwrite:
                err(f"Destination already exists: {destination}. Use --overwrite to replace.")
                sys.exit(1)
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
            ok(f"Directory copied: [bold]{source}[/bold] → [bold]{destination}[/bold]")
        else:
            if destination.is_dir():
                destination = destination / source.name
            if destination.exists() and not overwrite:
                err(f"Destination already exists: {destination}. Use --overwrite to replace.")
                sys.exit(1)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            ok(f"File copied: [bold]{source}[/bold] → [bold]{destination}[/bold]")
    except PermissionError:
        err(f"Permission denied while copying.")
        sys.exit(1)
    except shutil.Error as exc:
        err(str(exc))
        sys.exit(1)


# ---------------------------------------------------------------------------
# move
# ---------------------------------------------------------------------------

@cli.command("move")
@click.argument("src", type=click.Path(exists=True))
@click.argument("dst", type=click.Path())
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite destination if it exists.")
def cmd_move(src: str, dst: str, overwrite: bool) -> None:
    """Move SRC to DST (file or directory)."""
    source = Path(src).resolve()
    destination = Path(dst).resolve()

    try:
        if destination.exists() and not overwrite:
            err(f"Destination already exists: {destination}. Use --overwrite to replace.")
            sys.exit(1)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        ok(f"Moved: [bold]{source}[/bold] → [bold]{destination}[/bold]")
    except PermissionError:
        err("Permission denied while moving.")
        sys.exit(1)
    except shutil.Error as exc:
        err(str(exc))
        sys.exit(1)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@cli.command("delete")
@click.argument("path", type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.option("--recursive", "-r", is_flag=True, default=False, help="Delete directory recursively.")
def cmd_delete(path: str, force: bool, recursive: bool) -> None:
    """Delete a FILE or DIRECTORY at PATH."""
    target = Path(path).resolve()

    if not force:
        kind = "directory" if target.is_dir() else "file"
        confirm = click.confirm(
            f"⚠ Delete {kind} [bold red]{target}[/bold red]?",
            default=False,
        )
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            return

    try:
        if target.is_dir():
            if not recursive:
                err("Target is a directory. Use --recursive to delete directories.")
                sys.exit(1)
            shutil.rmtree(target)
            ok(f"Directory deleted: [bold]{target}[/bold]")
        else:
            target.unlink()
            ok(f"File deleted: [bold]{target}[/bold]")
    except PermissionError:
        err(f"Permission denied: {target}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------

@cli.command("rename")
@click.argument("path", type=click.Path(exists=True))
@click.argument("new_name")
def cmd_rename(path: str, new_name: str) -> None:
    """Rename the file/directory at PATH to NEW_NAME (basename only)."""
    target = Path(path).resolve()
    destination = target.parent / new_name

    if destination.exists():
        err(f"A file/directory named '{new_name}' already exists in {target.parent}.")
        sys.exit(1)

    try:
        target.rename(destination)
        ok(f"Renamed: [bold]{target.name}[/bold] → [bold]{destination.name}[/bold]")
    except PermissionError:
        err(f"Permission denied: {target}")
        sys.exit(1)
    except OSError as exc:
        err(str(exc))
        sys.exit(1)


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------

@cli.command("info")
@click.argument("path", type=click.Path(exists=True))
def cmd_info(path: str) -> None:
    """Show detailed metadata for the file or directory at PATH."""
    target = Path(path).resolve()

    try:
        st = target.stat()
    except PermissionError:
        err(f"Permission denied: {target}")
        sys.exit(1)

    kind = "Directory" if target.is_dir() else "File"
    mime, _ = mimetypes.guess_type(str(target))
    mime_str = mime or "unknown"

    table = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 1))
    table.add_column("Key", style="bold cyan", width=22)
    table.add_column("Value", style="white")

    rows = [
        ("Name", target.name),
        ("Type", kind),
        ("Path", str(target)),
        ("MIME Type", mime_str),
        ("Size", format_size(st.st_size) if target.is_file() else "-"),
        ("Permissions", format_permissions(st.st_mode)),
        ("Created", format_timestamp(st.st_ctime)),
        ("Modified", format_timestamp(st.st_mtime)),
        ("Accessed", format_timestamp(st.st_atime)),
        ("Inode", str(st.st_ino)),
        ("Hard Links", str(st.st_nlink)),
    ]

    for key, value in rows:
        table.add_row(key, value)

    icon = "📁" if target.is_dir() else "📄"
    console.print(Panel(table, title=f"[bold cyan]{icon} {target.name}[/bold cyan]", border_style="cyan"))


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@cli.command("search")
@click.argument("directory", default=".", type=click.Path(exists=True))
@click.option("--name", "-n", default=None, help="Filename pattern (e.g. '*.mp3' or 'song').")
@click.option("--ext", "-e", default=None, help="Filter by file extension (e.g. py).")
@click.option("--content", "-c", default=None, help="Search for a text pattern inside files.")
@click.option("--recursive", "-r", is_flag=True, default=True, help="Search recursively (default: on).")
@click.option("--ignore-case", "-i", is_flag=True, default=False, help="Case-insensitive search.")
@click.option("--max-results", default=200, show_default=True, help="Maximum number of results to show.")
def cmd_search(
    directory: str,
    name: Optional[str],
    ext: Optional[str],
    content: Optional[str],
    recursive: bool,
    ignore_case: bool,
    max_results: int,
) -> None:
    """Search for files in DIRECTORY matching the given criteria."""
    root = Path(directory).resolve()
    glob_fn = root.rglob if recursive else root.glob
    all_entries = glob_fn("*")

    table = Table(
        title=f"[bold cyan]🔍 Search Results in {root}[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("Match", style="bold white", no_wrap=True)
    table.add_column("Size", justify="right", style="yellow")
    table.add_column("Modified", style="dim")
    if content:
        table.add_column("Line", style="cyan", justify="right")
        table.add_column("Preview", style="dim")

    flags = re.IGNORECASE if ignore_case else 0
    content_re = re.compile(re.escape(content), flags) if content else None
    count = 0

    for entry in all_entries:
        if count >= max_results:
            break
        if not entry.is_file():
            continue
        if ext and entry.suffix.lstrip(".").lower() != ext.lstrip(".").lower():
            continue
        if name:
            pattern = name if "*" in name or "?" in name else f"*{name}*"
            if ignore_case:
                if not fnmatch.fnmatch(entry.name.lower(), pattern.lower()):
                    continue
            else:
                if not fnmatch.fnmatch(entry.name, pattern):
                    continue

        try:
            st = entry.stat()
        except (PermissionError, OSError):
            continue

        if content_re:
            # Search inside file content
            try:
                text = entry.read_text(encoding="utf-8", errors="replace")
            except (PermissionError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if content_re.search(line):
                    preview = line.strip()[:60]
                    table.add_row(
                        str(entry.relative_to(root)),
                        format_size(st.st_size),
                        format_timestamp(st.st_mtime),
                        str(lineno),
                        preview,
                    )
                    count += 1
                    if count >= max_results:
                        break
        else:
            table.add_row(
                str(entry.relative_to(root)),
                format_size(st.st_size),
                format_timestamp(st.st_mtime),
            )
            count += 1

    console.print(table)
    console.print(f"\n[dim]{count} result(s) found.[/dim]")
    if count >= max_results:
        warn(f"Result limit of {max_results} reached. Use --max-results to increase.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
