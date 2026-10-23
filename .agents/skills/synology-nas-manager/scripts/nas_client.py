"""
nas_client.py - Unified Multi-Protocol Client for Synology NAS

Supports:
- SMB/CIFS (Windows Drive Letter Mount & Network Share)
- SFTP/SSH (High-Speed Paramiko File Operations)
- Synology DSM REST API (FileStation API)
- WebDAV (Standard HTTP Storage)
"""

import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
import requests


# ---------------------------------------------------------------------------
# SMB / CIFS Client (Windows Native & UNC)
# ---------------------------------------------------------------------------

class SMBClient:
    """Manages SMB/CIFS connections, mounting to Windows drive letters or UNC authentication."""

    @staticmethod
    def mount_drive(
        host: str,
        share: str,
        username: str,
        password: str,
        drive_letter: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Mount a network share to a Windows drive letter or authenticate UNC session.
        If drive_letter is None or '*', Windows assigns the next available letter.
        """
        unc_path = f"\\\\{host}\\{share.strip('/')}"
        drive_target = f"{drive_letter.rstrip(':')}:" if drive_letter and drive_letter != "*" else "*"

        cmd = ["net", "use", drive_target, unc_path, f"/user:{username}", password, "/persistent:no"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                # Find which drive letter was assigned if '*'
                match = re.search(r"([A-Za-z]): is now connected to", res.stdout)
                assigned = match.group(1) + ":" if match else drive_target
                return True, f"Successfully mounted {unc_path} to {assigned}"
            return False, res.stderr.strip() or res.stdout.strip()
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def unmount_drive(drive_letter_or_path: str) -> Tuple[bool, str]:
        """Disconnect a mapped drive letter or UNC share."""
        target = drive_letter_or_path.rstrip("\\")
        if len(target) == 1 or (len(target) == 2 and target.endswith(":")):
            target = f"{target[0]}:"
        cmd = ["net", "use", target, "/delete", "/yes"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return True, f"Successfully disconnected {target}"
            return False, res.stderr.strip() or res.stdout.strip()
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def list_connections() -> List[Dict[str, str]]:
        """List current Windows network connections using net use."""
        try:
            res = subprocess.run(["net", "use"], capture_output=True, text=True, check=False)
            lines = res.stdout.splitlines()
            connections = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 3 and parts[0] in ("OK", "Disconnected", "Unavailable"):
                    status = parts[0]
                    local = parts[1] if parts[1].endswith(":") else ""
                    remote = parts[2] if parts[1].endswith(":") else parts[1]
                    connections.append({"status": status, "local": local, "remote": remote})
            return connections
        except Exception:
            return []


# ---------------------------------------------------------------------------
# SFTP / SSH Client (High Speed File Transfer)
# ---------------------------------------------------------------------------

class SFTPClient:
    """SFTP file transfer client using Paramiko."""

    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port or 22
        self._ssh = None
        self._sftp = None

    def connect(self) -> None:
        import paramiko
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=15,
            look_for_keys=False,
            allow_agent=False,
        )
        self._sftp = self._ssh.open_sftp()

    def close(self) -> None:
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def list_dir(self, remote_path: str = ".") -> List[Dict[str, Any]]:
        """List files and folders in remote path."""
        entries = []
        for attr in self._sftp.listdir_attr(remote_path):
            is_dir = stat.S_ISDIR(attr.st_mode)
            entries.append({
                "name": attr.filename,
                "is_dir": is_dir,
                "size": attr.st_size if not is_dir else 0,
                "mtime": attr.st_mtime,
                "path": f"{remote_path.rstrip('/')}/{attr.filename}",
            })
        return entries

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """Upload a single file."""
        self._sftp.put(local_path, remote_path)

    def download_file(self, remote_path: str, local_path: str) -> None:
        """Download a single file."""
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self._sftp.get(remote_path, local_path)

    def mkdir(self, remote_path: str) -> None:
        """Create directory on remote."""
        try:
            self._sftp.mkdir(remote_path)
        except IOError:
            # Already exists or parent missing
            pass

    def remove_file(self, remote_path: str) -> None:
        """Delete file on remote."""
        self._sftp.remove(remote_path)

    def rmdir(self, remote_path: str) -> None:
        """Delete directory on remote."""
        self._sftp.rmdir(remote_path)


# ---------------------------------------------------------------------------
# Synology DSM REST API Client (FileStation API)
# ---------------------------------------------------------------------------

class SynologyDSMClient:
    """Client for Synology DSM FileStation REST API."""

    def __init__(self, host: str, username: str, password: str, port: Optional[int] = None, use_https: bool = False):
        self.host = host
        self.username = username
        self.password = password
        self.protocol = "https" if use_https else "http"
        self.port = port or (5001 if use_https else 5000)
        self.base_url = f"{self.protocol}://{self.host}:{self.port}/webapi"
        self.sid: Optional[str] = None
        self.session = requests.Session()

    def login(self) -> bool:
        """Authenticate with DSM and obtain session ID (sid)."""
        url = f"{self.base_url}/auth.cgi"
        params = {
            "api": "SYNO.API.Auth",
            "version": "6",
            "method": "login",
            "account": self.username,
            "passwd": self.password,
            "session": "FileStation",
            "format": "sid",
        }
        resp = self.session.get(url, params=params, verify=False, timeout=10)
        data = resp.json()
        if data.get("success"):
            self.sid = data["data"]["sid"]
            return True
        raise ConnectionError(f"DSM Login Failed: {data.get('error', {}).get('code', 'Unknown error')}")

    def logout(self) -> None:
        """Logout of DSM session."""
        if not self.sid:
            return
        url = f"{self.base_url}/auth.cgi"
        params = {"api": "SYNO.API.Auth", "version": "6", "method": "logout", "session": "FileStation", "_sid": self.sid}
        try:
            self.session.get(url, params=params, verify=False, timeout=5)
        except Exception:
            pass
        self.sid = None

    def list_shares(self) -> List[Dict[str, Any]]:
        """List shared folders on the Synology NAS."""
        if not self.sid:
            self.login()
        url = f"{self.base_url}/entry.cgi"
        params = {
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list_share",
            "_sid": self.sid,
        }
        resp = self.session.get(url, params=params, verify=False, timeout=15)
        data = resp.json()
        if data.get("success"):
            return data["data"].get("shares", [])
        raise RuntimeError(f"Failed to list shares: {data.get('error')}")

    def list_files(self, folder_path: str) -> List[Dict[str, Any]]:
        """List contents of a remote folder."""
        if not self.sid:
            self.login()
        url = f"{self.base_url}/entry.cgi"
        params = {
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list",
            "folder_path": folder_path,
            "_sid": self.sid,
        }
        resp = self.session.get(url, params=params, verify=False, timeout=15)
        data = resp.json()
        if data.get("success"):
            return data["data"].get("files", [])
        raise RuntimeError(f"Failed to list path {folder_path}: {data.get('error')}")

    def download_file(self, remote_path: str, local_path: str) -> None:
        """Download a file via DSM FileStation download API."""
        if not self.sid:
            self.login()
        url = f"{self.base_url}/entry.cgi"
        params = {
            "api": "SYNO.FileStation.Download",
            "version": "2",
            "method": "download",
            "path": remote_path,
            "mode": "download",
            "_sid": self.sid,
        }
        with self.session.get(url, params=params, verify=False, stream=True, timeout=60) as r:
            r.raise_for_status()
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)

    def upload_file(self, local_path: str, dest_folder_path: str) -> None:
        """Upload a file via DSM FileStation upload API."""
        if not self.sid:
            self.login()
        url = f"{self.base_url}/entry.cgi"
        params = {
            "api": "SYNO.FileStation.Upload",
            "version": "2",
            "method": "upload",
            "_sid": self.sid,
        }
        file_path = Path(local_path)
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            data = {"dest_folder_path": dest_folder_path, "create_parents": "true", "overwrite": "true"}
            resp = self.session.post(url, params=params, data=data, files=files, verify=False, timeout=120)
            res_json = resp.json()
            if not res_json.get("success"):
                raise RuntimeError(f"Upload failed: {res_json.get('error')}")

    def create_folder(self, parent_path: str, folder_name: str) -> None:
        """Create a new folder on the NAS."""
        if not self.sid:
            self.login()
        url = f"{self.base_url}/entry.cgi"
        params = {
            "api": "SYNO.FileStation.CreateFolder",
            "version": "2",
            "method": "create",
            "folder_path": parent_path,
            "name": folder_name,
            "_sid": self.sid,
        }
        resp = self.session.get(url, params=params, verify=False, timeout=15)
        res_json = resp.json()
        if not res_json.get("success"):
            raise RuntimeError(f"Failed to create folder: {res_json.get('error')}")

    def delete_path(self, path: str) -> None:
        """Delete a file or folder via DSM API."""
        if not self.sid:
            self.login()
        url = f"{self.base_url}/entry.cgi"
        params = {
            "api": "SYNO.FileStation.Delete",
            "version": "2",
            "method": "start",
            "path": path,
            "_sid": self.sid,
        }
        resp = self.session.get(url, params=params, verify=False, timeout=15)
        res_json = resp.json()
        if not res_json.get("success"):
            raise RuntimeError(f"Delete failed: {res_json.get('error')}")


# ---------------------------------------------------------------------------
# WebDAV Client
# ---------------------------------------------------------------------------

class WebDAVClient:
    """Basic WebDAV Client for Synology WebDAV Server."""

    def __init__(self, host: str, username: str, password: str, port: Optional[int] = None, use_https: bool = False):
        self.host = host
        self.username = username
        self.password = password
        self.protocol = "https" if use_https else "http"
        self.port = port or (5006 if use_https else 5005)
        self.base_url = f"{self.protocol}://{self.host}:{self.port}"
        self.auth = requests.auth.HTTPBasicAuth(username, password)

    def test_connection(self) -> bool:
        """Send PROPFIND request to test WebDAV connectivity."""
        try:
            resp = requests.request("PROPFIND", self.base_url, auth=self.auth, headers={"Depth": "0"}, timeout=10, verify=False)
            return resp.status_code in (200, 207, 301, 302)
        except Exception:
            return False

    def upload_file(self, local_path: str, remote_rel_path: str) -> None:
        """Upload file via HTTP PUT."""
        url = f"{self.base_url}/{remote_rel_path.lstrip('/')}"
        with open(local_path, "rb") as f:
            resp = requests.put(url, data=f, auth=self.auth, timeout=120, verify=False)
            resp.raise_for_status()

    def download_file(self, remote_rel_path: str, local_path: str) -> None:
        """Download file via HTTP GET."""
        url = f"{self.base_url}/{remote_rel_path.lstrip('/')}"
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, auth=self.auth, stream=True, timeout=60, verify=False) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
