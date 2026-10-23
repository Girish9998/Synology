"""
nas_crypto.py - Secure Credential & Profile Storage for Synology NAS Manager

Stores configuration and credentials in an encrypted JSON file at ~/.nas_credentials
using Fernet symmetric encryption with a locally-protected key at ~/.nas_key.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet

# Automatically load .env file from project directory if present
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    pass

CONFIG_PATH = Path.home() / ".nas_credentials"
KEY_PATH = Path.home() / ".nas_key"


def _get_env_profile() -> Optional[Dict[str, Any]]:
    """Synthesize profile from .env variables if present."""
    host = os.environ.get("NAS_HOST")
    user = os.environ.get("NAS_USERNAME") or os.environ.get("NAS_USER")
    pwd = os.environ.get("NAS_PASSWORD") or os.environ.get("NAS_PASS")
    if host and user:
        port_val = os.environ.get("NAS_PORT")
        port = int(port_val) if port_val and port_val.isdigit() else None
        https_val = os.environ.get("NAS_HTTPS", "false").lower() in ("true", "1", "yes")
        return {
            "name": ".env",
            "host": host,
            "username": user,
            "password": pwd or "",
            "protocol": os.environ.get("NAS_PROTOCOL", "smb").lower(),
            "port": port,
            "share": os.environ.get("NAS_SHARE", "music"),
            "use_https": https_val,
        }
    return None


def _get_or_create_key() -> bytes:
    """Retrieve existing encryption key or generate and save a new one."""
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes().strip()
    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    # Set restrictive permissions where supported
    try:
        os.chmod(KEY_PATH, 0o600)
    except Exception:
        pass
    return key


def _get_cipher() -> Fernet:
    return Fernet(_get_or_create_key())


def load_config() -> Dict[str, Any]:
    """Load and decrypt profiles from the credentials file and/or .env."""
    env_prof = _get_env_profile()
    base_config = {"default_profile": None, "profiles": {}}

    if CONFIG_PATH.exists():
        cipher = _get_cipher()
        try:
            raw_data = CONFIG_PATH.read_bytes()
            if raw_data:
                try:
                    decrypted = cipher.decrypt(raw_data)
                    base_config = json.loads(decrypted.decode("utf-8"))
                except Exception:
                    base_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    if env_prof:
        # Register .env profile and prioritize as active default
        base_config.setdefault("profiles", {})[".env"] = env_prof
        base_config["default_profile"] = ".env"

    return base_config


def save_config(config: Dict[str, Any]) -> None:
    """Encrypt and save configuration to disk."""
    cipher = _get_cipher()
    data = json.dumps(config, indent=2).encode("utf-8")
    encrypted = cipher.encrypt(data)
    CONFIG_PATH.write_bytes(encrypted)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except Exception:
        pass


def add_or_update_profile(
    name: str,
    host: str,
    username: str,
    password: str,
    protocol: str = "smb",
    port: Optional[int] = None,
    share: Optional[str] = None,
    use_https: bool = False,
    set_default: bool = False,
) -> None:
    """Add or update a NAS profile."""
    config = load_config()
    profiles = config.setdefault("profiles", {})

    profile_data = {
        "name": name,
        "host": host,
        "username": username,
        "password": password,
        "protocol": protocol.lower(),
        "port": port,
        "share": share or "",
        "use_https": use_https,
    }

    profiles[name] = profile_data

    if set_default or config.get("default_profile") is None:
        config["default_profile"] = name

    save_config(config)


def get_profile(name: Optional[str] = None) -> Dict[str, Any]:
    """Get a specific profile or the default profile."""
    config = load_config()
    profiles = config.get("profiles", {})
    if not profiles:
        raise ValueError("No NAS profiles configured. Use 'profile add' to configure one.")

    target_name = name or config.get("default_profile")
    if not target_name or target_name not in profiles:
        available = ", ".join(profiles.keys())
        raise ValueError(
            f"Profile '{target_name}' not found. Available profiles: {available}"
        )
    return profiles[target_name]


def list_profiles() -> List[Dict[str, Any]]:
    """List all configured profiles with sensitive fields masked."""
    config = load_config()
    default_name = config.get("default_profile")
    result = []
    for name, prof in config.get("profiles", {}).items():
        copy_prof = dict(prof)
        copy_prof["is_default"] = (name == default_name)
        copy_prof["password_set"] = bool(copy_prof.get("password"))
        copy_prof.pop("password", None)
        result.append(copy_prof)
    return result


def remove_profile(name: str) -> bool:
    """Remove a profile by name."""
    config = load_config()
    profiles = config.get("profiles", {})
    if name in profiles:
        del profiles[name]
        if config.get("default_profile") == name:
            config["default_profile"] = next(iter(profiles.keys())) if profiles else None
        save_config(config)
        return True
    return False


def set_default_profile(name: str) -> None:
    """Set the active default profile."""
    config = load_config()
    if name not in config.get("profiles", {}):
        raise ValueError(f"Profile '{name}' does not exist.")
    config["default_profile"] = name
    save_config(config)
