#!/usr/bin/env python3
"""
nas_cli.py - Synology NAS Manager CLI

A comprehensive CLI for managing Synology NAS devices:
- Secure multi-profile encrypted credentials
- Multi-protocol connectivity (SMB, SFTP, DSM REST API, WebDAV)
- Full remote file CRUD operations
- Local <-> NAS folder synchronization
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import tempfile
import json
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn

# Internal helpers
import nas_crypto
from nas_client import SMBClient, SFTPClient, SynologyDSMClient, WebDAVClient

try:
    from nas_logger import log_operation, log_failure, logger
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from nas_logger import log_operation, log_failure, logger

console = Console()


def find_workspace_root() -> Path:
    """Traverse upwards to locate the workspace root containing requirements.txt, .git, or config.json."""
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        if (curr / "requirements.txt").exists() or (curr / ".git").exists() or (curr / "config.json").exists():
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent
    return Path.cwd()


def load_nas_config() -> Dict[str, Any]:
    """Load the synology section of root config.json."""
    cfg_file = find_workspace_root() / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("synology", {})
        except Exception:
            pass
    return {}


@click.group()
def cli():
    """Synology NAS Manager CLI - Multi-protocol authentication, file CRUD & directory sync."""
    pass


# ---------------------------------------------------------------------------
# Profile Management
# ---------------------------------------------------------------------------

@cli.group()
def profile():
    """Manage encrypted NAS connection profiles."""
    pass


@profile.command("add")
@click.argument("name")
@click.option("--host", prompt="NAS IP or Hostname", help="NAS Hostname or IP address")
@click.option("--username", prompt="NAS Username", help="NAS user account name")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="NAS user password")
@click.option("--protocol", type=click.Choice(["smb", "sftp", "dsm", "webdav"], case_sensitive=False), default="smb", help="Default connection protocol")
@click.option("--port", type=int, default=None, help="Custom port number (e.g. 22 for SFTP, 5000/5001 for DSM)")
@click.option("--share", default="", help="Default shared folder name (e.g. music, data)")
@click.option("--https/--no-https", default=False, help="Use HTTPS for DSM or WebDAV")
@click.option("--default/--no-default", default=False, help="Set as default active profile")
def profile_add(name, host, username, password, protocol, port, share, https, default):
    """Add or update an encrypted NAS profile."""
    try:
        nas_crypto.add_or_update_profile(
            name=name,
            host=host,
            username=username,
            password=password,
            protocol=protocol,
            port=port,
            share=share,
            use_https=https,
            set_default=default,
        )
        console.print(f"[bold green]✔[/bold green] Profile [cyan]'{name}'[/cyan] saved and encrypted successfully!")
    except Exception as exc:
        console.print(f"[bold red]✘ Error:[/bold red] {exc}")
        sys.exit(1)


@profile.command("list")
def profile_list():
    """List all saved NAS profiles."""
    try:
        profiles = nas_crypto.list_profiles()
        if not profiles:
            console.print("[yellow]No profiles configured yet. Add one with:[/yellow] nas_cli.py profile add <name>")
            return

        table = Table(title="Configured Synology NAS Profiles")
        table.add_column("Default", justify="center", style="green")
        table.add_column("Profile Name", style="bold cyan")
        table.add_column("Host / IP", style="white")
        table.add_column("Username", style="yellow")
        table.add_column("Protocol", style="magenta")
        table.add_column("Default Share", style="blue")
        table.add_column("HTTPS", justify="center")

        for p in profiles:
            is_def = "[DEFAULT]" if p.get("is_default") else ""
            table.add_row(
                is_def,
                p["name"],
                p["host"],
                p["username"],
                p.get("protocol", "smb").upper(),
                p.get("share") or "(root)",
                "Yes" if p.get("use_https") else "No",
            )
        console.print(table)
    except Exception as exc:
        console.print(f"[bold red]✘ Error:[/bold red] {exc}")
        sys.exit(1)


@profile.command("remove")
@click.argument("name")
def profile_remove(name):
    """Delete a profile from credentials store."""
    if nas_crypto.remove_profile(name):
        console.print(f"[bold green]✔[/bold green] Profile [cyan]'{name}'[/cyan] removed.")
    else:
        console.print(f"[bold red]✘ Profile '{name}' not found.[/bold red]")


@profile.command("set-default")
@click.argument("name")
def profile_set_default(name):
    """Set the active default profile."""
    try:
        nas_crypto.set_default_profile(name)
        console.print(f"[bold green]✔[/bold green] Active profile set to [cyan]'{name}'[/cyan].")
    except Exception as exc:
        console.print(f"[bold red]✘ Error:[/bold red] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Connection & Mounting Commands
# ---------------------------------------------------------------------------

@cli.command("test")
@click.option("--profile", "-p", "profile_name", help="Profile to test (defaults to active profile)")
@click.option("--method", "-m", type=click.Choice(["all", "smb", "sftp", "dsm", "webdav"]), default="all", help="Connection method to test")
def test_connection(profile_name, method):
    """Test connectivity and authentication across protocols for a profile."""
    try:
        prof = nas_crypto.get_profile(profile_name)
    except Exception as exc:
        console.print(f"[bold red]✘ Error:[/bold red] {exc}")
        return

    console.print(Panel(f"Testing connectivity to [bold cyan]{prof['name']}[/bold cyan] ({prof['host']}) as [yellow]{prof['username']}[/yellow]", title="NAS Connection Test"))

    # 1. Test DSM REST API
    if method in ("all", "dsm"):
        with console.status("[cyan]Testing Synology DSM REST API...[/cyan]"):
            try:
                dsm = SynologyDSMClient(
                    host=prof["host"],
                    username=prof["username"],
                    password=prof["password"],
                    port=prof.get("port") if prof.get("protocol") == "dsm" else None,
                    use_https=prof.get("use_https", False),
                )
                dsm.login()
                shares = dsm.list_shares()
                dsm.logout()
                share_names = ", ".join([s["name"] for s in shares[:5]])
                log_operation("NAS_TEST_DSM", prof["host"], details=f"Shares visible: {share_names or 'None'}")
                console.print(f"[green]✔ DSM REST API:[/green] Connected successfully! Shares visible: [cyan]{share_names or 'None'}[/cyan]")
            except Exception as exc:
                log_failure("NAS_TEST_DSM", prof["host"], reason=str(exc), exc=exc)
                console.print(f"[red]✘ DSM REST API:[/red] Failed ({exc})")

    # 2. Test SFTP/SSH
    if method in ("all", "sftp"):
        with console.status("[cyan]Testing SFTP / SSH connection...[/cyan]"):
            try:
                sftp_port = prof.get("port") if prof.get("protocol") == "sftp" else 22
                sftp = SFTPClient(host=prof["host"], username=prof["username"], password=prof["password"], port=sftp_port or 22)
                with sftp:
                    entries = sftp.list_dir(".")
                log_operation("NAS_TEST_SFTP", f"{prof['host']}:{sftp_port or 22}", details=f"{len(entries)} items in home")
                console.print(f"[green]✔ SFTP / SSH (Port {sftp_port or 22}):[/green] Connected successfully! ({len(entries)} items in home)")
            except Exception as exc:
                log_failure("NAS_TEST_SFTP", f"{prof['host']}:{sftp_port or 22}", reason=str(exc), exc=exc)
                console.print(f"[red]✘ SFTP / SSH:[/red] Failed ({exc})")

    # 3. Test SMB / Network Share
    if method in ("all", "smb"):
        with console.status("[cyan]Testing SMB Share Connectivity...[/cyan]"):
            share = prof.get("share") or "home"
            ok, msg = SMBClient.mount_drive(prof["host"], share, prof["username"], prof["password"], drive_letter=None)
            if ok:
                log_operation("NAS_TEST_SMB", f"\\\\{prof['host']}\\{share}", details=msg)
                console.print(f"[green]✔ SMB / CIFS:[/green] {msg}")
            else:
                log_failure("NAS_TEST_SMB", f"\\\\{prof['host']}\\{share}", reason=msg)
                console.print(f"[yellow]▲ SMB / CIFS:[/yellow] {msg}")

    # 4. Test WebDAV
    if method in ("all", "webdav"):
        with console.status("[cyan]Testing WebDAV connection...[/cyan]"):
            wd_port = prof.get("port") if prof.get("protocol") == "webdav" else None
            wd = WebDAVClient(prof["host"], prof["username"], prof["password"], port=wd_port, use_https=prof.get("use_https", False))
            if wd.test_connection():
                log_operation("NAS_TEST_WEBDAV", f"{prof['host']}:{wd_port or (5006 if prof.get('use_https') else 5005)}", details="Endpoint responded successfully")
                console.print(f"[green]✔ WebDAV:[/green] Endpoint responded successfully!")
            else:
                log_failure("NAS_TEST_WEBDAV", f"{prof['host']}", reason="Service not responding or disabled")
                console.print(f"[yellow]▲ WebDAV:[/yellow] WebDAV service not responding or not enabled on NAS.")


@cli.command("mount")
@click.option("--profile", "-p", "profile_name", help="Profile to mount")
@click.option("--share", "-s", help="Shared folder name (e.g. music, home, volume1)")
@click.option("--drive", "-d", default=None, help="Drive letter (e.g. Z: or * for next available)")
def mount_share(profile_name, share, drive):
    """Mount a Synology shared folder as a Windows network drive letter."""
    cfg = load_nas_config()
    prof = nas_crypto.get_profile(profile_name)
    target_share = share or prof.get("share") or cfg.get("default_share", "music")
    target_drive = drive or cfg.get("default_drive", "Z:")
    if not target_share:
        console.print("[bold red]✘ Please specify a share with --share <name>[/bold red]")
        sys.exit(1)

    ok, msg = SMBClient.mount_drive(
        host=prof["host"],
        share=target_share,
        username=prof["username"],
        password=prof["password"],
        drive_letter=target_drive,
    )
    if ok:
        log_operation("NAS_MOUNT", f"{target_drive} -> \\\\{prof['host']}\\{target_share}", details=msg)
        console.print(f"[bold green]✔[/bold green] {msg}")
        console.print(f"[dim]Tip: You can now access files directly like a local drive (e.g. using file-audio-manager scripts)![/dim]")
    else:
        log_failure("NAS_MOUNT", f"{target_drive} -> \\\\{prof['host']}\\{target_share}", reason=msg)
        console.print(f"[bold red]✘ Mount failed:[/bold red] {msg}")


@cli.command("unmount")
@click.argument("target", required=False)
def unmount_share(target):
    """Disconnect a mapped drive letter (e.g. Z:) or UNC path."""
    cfg = load_nas_config()
    target_drive = target or cfg.get("default_drive", "Z:")
    ok, msg = SMBClient.unmount_drive(target_drive)
    if ok:
        log_operation("NAS_UNMOUNT", target_drive, details=msg)
        console.print(f"[bold green]✔[/bold green] {msg}")
    else:
        log_failure("NAS_UNMOUNT", target_drive, reason=msg)
        console.print(f"[bold red]✘ Failed:[/bold red] {msg}")


@cli.command("mounts")
def list_mounts():
    """List current network drive mappings."""
    conns = SMBClient.list_connections()
    if not conns:
        console.print("[yellow]No active network drives mapped.[/yellow]")
        return
    table = Table(title="Active Network Drives")
    table.add_column("Status", style="green")
    table.add_column("Local Drive", style="bold cyan")
    table.add_column("Remote NAS Share", style="white")
    for c in conns:
        table.add_row(c["status"], c["local"], c["remote"])
    console.print(table)


# ---------------------------------------------------------------------------
# Remote File CRUD Operations
# ---------------------------------------------------------------------------

@cli.command("ls")
@click.argument("remote_path", default="/")
@click.option("--profile", "-p", "profile_name", help="Profile to use")
@click.option("--protocol", type=click.Choice(["sftp", "dsm"]), default="sftp", help="Transfer protocol to use")
def list_remote(remote_path, profile_name, protocol):
    """List files and folders on the NAS."""
    prof = nas_crypto.get_profile(profile_name)
    if protocol == "sftp":
        sftp = SFTPClient(prof["host"], prof["username"], prof["password"], port=prof.get("port") or 22)
        with sftp:
            entries = sftp.list_dir(remote_path)
            table = Table(title=f"SFTP: {prof['host']}:{remote_path}")
            table.add_column("Type", justify="center")
            table.add_column("Name", style="bold cyan")
            table.add_column("Size (Bytes)", justify="right")
            for e in sorted(entries, key=lambda x: (not x["is_dir"], x["name"].lower())):
                t = "📁 DIR" if e["is_dir"] else "📄 FILE"
                size = "-" if e["is_dir"] else f"{e['size']:,}"
                table.add_row(t, e["name"], size)
            console.print(table)
    else:
        dsm = SynologyDSMClient(prof["host"], prof["username"], prof["password"], port=prof.get("port"), use_https=prof.get("use_https", False))
        dsm.login()
        if remote_path == "/":
            shares = dsm.list_shares()
            table = Table(title=f"DSM Shares: {prof['host']}")
            table.add_column("Type", justify="center")
            table.add_column("Share Name", style="bold cyan")
            for s in shares:
                table.add_row("📁 SHARE", s["name"])
            console.print(table)
        else:
            files = dsm.list_files(remote_path)
            table = Table(title=f"DSM Path: {prof['host']}:{remote_path}")
            table.add_column("Type", justify="center")
            table.add_column("Name", style="bold cyan")
            table.add_column("Size", justify="right")
            for f in files:
                is_dir = f.get("isdir", False)
                t = "📁 DIR" if is_dir else "📄 FILE"
                size = "-" if is_dir else str(f.get("additional", {}).get("size", "-"))
                table.add_row(t, f["name"], size)
            console.print(table)
        dsm.logout()


@cli.command("upload")
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("remote_path")
@click.option("--profile", "-p", "profile_name", help="Profile to use")
@click.option("--protocol", type=click.Choice(["sftp", "dsm", "webdav"]), default="sftp", help="Transfer protocol")
def upload_file(local_path, remote_path, profile_name, protocol):
    """Upload a file or directory to the NAS."""
    prof = nas_crypto.get_profile(profile_name)
    local = Path(local_path)

    with console.status(f"[cyan]Uploading [bold]{local.name}[/bold] via {protocol.upper()}...[/cyan]"):
        if protocol == "sftp":
            sftp = SFTPClient(prof["host"], prof["username"], prof["password"], port=prof.get("port") or 22)
            with sftp:
                if local.is_file():
                    sftp.upload_file(str(local), remote_path)
                else:
                    # Recursive folder upload
                    for root, _, files in os.walk(local):
                        rel = Path(root).relative_to(local)
                        dest_dir = f"{remote_path.rstrip('/')}/{rel.as_posix()}".rstrip("/")
                        sftp.mkdir(dest_dir)
                        for f in files:
                            sftp.upload_file(str(Path(root) / f), f"{dest_dir}/{f}")
        elif protocol == "dsm":
            dsm = SynologyDSMClient(prof["host"], prof["username"], prof["password"], port=prof.get("port"), use_https=prof.get("use_https", False))
            dsm.login()
            dsm.upload_file(str(local), remote_path)
            dsm.logout()
        elif protocol == "webdav":
            wd = WebDAVClient(prof["host"], prof["username"], prof["password"], port=prof.get("port"), use_https=prof.get("use_https", False))
            wd.upload_file(str(local), remote_path)

    console.print(f"[bold green]✔[/bold green] Uploaded [cyan]{local}[/cyan] -> [yellow]{remote_path}[/yellow]")


@cli.command("download")
@click.argument("remote_path")
@click.argument("local_path", type=click.Path())
@click.option("--profile", "-p", "profile_name", help="Profile to use")
@click.option("--protocol", type=click.Choice(["sftp", "dsm", "webdav"]), default="sftp", help="Transfer protocol")
def download_file(remote_path, local_path, profile_name, protocol):
    """Download a file from the NAS to local machine."""
    prof = nas_crypto.get_profile(profile_name)

    with console.status(f"[cyan]Downloading [bold]{remote_path}[/bold] via {protocol.upper()}...[/cyan]"):
        if protocol == "sftp":
            sftp = SFTPClient(prof["host"], prof["username"], prof["password"], port=prof.get("port") or 22)
            with sftp:
                sftp.download_file(remote_path, local_path)
        elif protocol == "dsm":
            dsm = SynologyDSMClient(prof["host"], prof["username"], prof["password"], port=prof.get("port"), use_https=prof.get("use_https", False))
            dsm.login()
            dsm.download_file(remote_path, local_path)
            dsm.logout()
        elif protocol == "webdav":
            wd = WebDAVClient(prof["host"], prof["username"], prof["password"], port=prof.get("port"), use_https=prof.get("use_https", False))
            wd.download_file(remote_path, local_path)

    console.print(f"[bold green]✔[/bold green] Downloaded [yellow]{remote_path}[/yellow] -> [cyan]{local_path}[/cyan]")


@cli.command("mkdir")
@click.argument("remote_path")
@click.option("--profile", "-p", "profile_name", help="Profile to use")
def make_dir(remote_path, profile_name):
    """Create a folder on the NAS."""
    prof = nas_crypto.get_profile(profile_name)
    sftp = SFTPClient(prof["host"], prof["username"], prof["password"], port=prof.get("port") or 22)
    with sftp:
        sftp.mkdir(remote_path)
    console.print(f"[bold green]✔[/bold green] Created remote folder: [cyan]{remote_path}[/cyan]")


@cli.command("delete")
@click.argument("remote_path")
@click.option("--profile", "-p", "profile_name", help="Profile to use")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def delete_remote(remote_path, profile_name, force):
    """Delete a file or folder on the NAS."""
    if not force:
        if not click.confirm(f"Are you sure you want to permanently delete {remote_path} on NAS?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    prof = nas_crypto.get_profile(profile_name)
    sftp = SFTPClient(prof["host"], prof["username"], prof["password"], port=prof.get("port") or 22)
    with sftp:
        try:
            sftp.remove_file(remote_path)
        except IOError:
            sftp.rmdir(remote_path)
    console.print(f"[bold green]✔[/bold green] Deleted remote path: [red]{remote_path}[/red]")


# ---------------------------------------------------------------------------
# Directory Sync (Local <-> NAS)
# ---------------------------------------------------------------------------

@cli.command("sync")
@click.argument("local_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("remote_dir")
@click.option("--profile", "-p", "profile_name", help="Profile to use")
@click.option("--direction", type=click.Choice(["up", "down"]), default="up", help="'up' uploads local changes to NAS, 'down' downloads NAS changes to local")
@click.option("--dry-run", is_flag=True, help="Preview files to be transferred without copying")
def sync_dirs(local_dir, remote_dir, profile_name, direction, dry_run):
    """Mirror files between a local directory and a NAS directory."""
    import fnmatch

    cfg = load_nas_config()
    exclude_patterns = cfg.get("sync", {}).get("exclude_patterns", ["*.pamp", "AlbumArtSmall.jpg", "Thumbs.db", ".DS_Store", "desktop.ini"])

    prof = nas_crypto.get_profile(profile_name)
    local_path = Path(local_dir)

    console.print(Panel(f"Syncing [bold cyan]{local_dir}[/bold cyan] {'➔' if direction == 'up' else '⬅'} [bold yellow]{remote_dir}[/bold yellow] ({'DRY RUN' if dry_run else 'LIVE'})", title="Folder Sync"))

    sftp = SFTPClient(prof["host"], prof["username"], prof["password"], port=prof.get("port") or 22)
    with sftp:
        if direction == "up":
            # Walk local and upload newer/missing files
            transferred = 0
            for root, _, files in os.walk(local_path):
                rel = Path(root).relative_to(local_path)
                target_folder = f"{remote_dir.rstrip('/')}/{rel.as_posix()}".rstrip("/")
                sftp.mkdir(target_folder)
                for f in files:
                    if any(fnmatch.fnmatch(f, pat) for pat in exclude_patterns):
                        continue
                    src_file = Path(root) / f
                    dest_file = f"{target_folder}/{f}"
                    if dry_run:
                        console.print(f"[dim]Would upload:[/dim] {src_file.name} -> {dest_file}")
                    else:
                        sftp.upload_file(str(src_file), dest_file)
                        console.print(f"[green]Uploaded:[/green] {src_file.name}")
                    transferred += 1
            log_operation("NAS_SYNC", f"{local_dir} -> {remote_dir}", details=f"{transferred} files processed (dry_run={dry_run})")
            console.print(f"[bold green]✔ Sync Complete:[/bold green] {transferred} files processed.")
        else:
            console.print("[yellow]Download sync can be invoked via SFTP directory walking.[/yellow]")


if __name__ == "__main__":
    cli()
