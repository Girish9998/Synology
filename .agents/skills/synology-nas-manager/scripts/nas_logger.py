"""
nas_logger.py — Enterprise SDLC-compliant multi-tier logging & audit framework for Synology NAS Manager.

Architecture:
  - logs/info.log    : Operational milestones, sync completions, connection tests (INFO)
  - logs/error.log   : Isolated anomalies, network failures, auth errors (WARNING/ERROR/CRITICAL)
  - logs/detail.log  : Deep diagnostics, raw payloads, tracebacks (DEBUG)
  - logs/audit.jsonl : Structured immutable event stream for compliance & analytics (JSON Lines)
"""

from __future__ import annotations

import datetime
import json
import logging
import sys
import traceback
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


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


_workspace_root = find_workspace_root()
_config_file = _workspace_root / "config.json"

# Load config settings
_cfg: Dict[str, Any] = {}
if _config_file.exists():
    try:
        with open(_config_file, "r", encoding="utf-8") as f:
            _cfg = json.load(f).get("logging", {})
    except Exception:
        pass

_enabled: bool = _cfg.get("enabled", True)
_log_dir_name: str = _cfg.get("log_dir", "logs")
_log_dir: Path = _workspace_root / _log_dir_name
_info_file: str = _cfg.get("info_log", "info.log")
_error_file: str = _cfg.get("error_log", "error.log")
_detail_file: str = _cfg.get("detail_log", "detail.log")
_audit_file: str = _cfg.get("audit_log", "audit.jsonl")
_max_bytes: int = _cfg.get("max_bytes", 10 * 1024 * 1024)
_backup_count: int = _cfg.get("backup_count", 5)

# Generate unique session execution correlation ID
SESSION_ID: str = uuid.uuid4().hex[:8]


class ContextFilter(logging.Filter):
    """Injects session correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = SESSION_ID  # type: ignore[attr-defined]
        return True


if _enabled:
    try:
        _log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# NAS Logger
logger = logging.getLogger("synology_nas")
logger.setLevel(logging.DEBUG)

if _enabled and not logger.handlers and _log_dir.exists():
    ctx_filter = ContextFilter()

    # 1. Operational Info Log (INFO and above)
    info_path = _log_dir / _info_file
    h_info = RotatingFileHandler(str(info_path), maxBytes=_max_bytes, backupCount=_backup_count, encoding="utf-8")
    h_info.setLevel(logging.INFO)
    fmt_info = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [sid:%(session_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    h_info.setFormatter(fmt_info)
    h_info.addFilter(ctx_filter)
    logger.addHandler(h_info)

    # 2. Dedicated Error & Warning Log (WARNING and ERROR only)
    error_path = _log_dir / _error_file
    h_error = RotatingFileHandler(str(error_path), maxBytes=_max_bytes, backupCount=_backup_count, encoding="utf-8")
    h_error.setLevel(logging.WARNING)
    fmt_error = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [sid:%(session_id)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    h_error.setFormatter(fmt_error)
    h_error.addFilter(ctx_filter)
    logger.addHandler(h_error)

    # 3. Comprehensive Technical Detail Log (DEBUG and above, tracebacks, raw payloads)
    detail_path = _log_dir / _detail_file
    h_detail = RotatingFileHandler(str(detail_path), maxBytes=_max_bytes, backupCount=_backup_count, encoding="utf-8")
    h_detail.setLevel(logging.DEBUG)
    fmt_detail = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [sid:%(session_id)s] [%(name)s:%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    h_detail.setFormatter(fmt_detail)
    h_detail.addFilter(ctx_filter)
    logger.addHandler(h_detail)


def append_audit_event(event: Dict[str, Any]) -> None:
    """Append structured JSON audit record to audit.jsonl."""
    if not _enabled or not _log_dir.exists():
        return
    audit_path = _log_dir / _audit_file
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session_id": SESSION_ID,
        "component": "synology_nas",
        **event
    }
    try:
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def log_operation(
    action: str,
    target: str,
    details: Optional[str] = None,
    status: str = "SUCCESS",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Standardized high-level operation logger."""
    if not _enabled:
        return

    msg = f"[{action}] [{status}] {target}"
    if details:
        msg += f" — {details}"

    if status.upper() in ("FAIL", "FAILURE", "ERROR"):
        logger.warning(msg)
    else:
        logger.info(msg)

    # Record in detail log
    logger.debug(f"[NAS_OP_TRACE] {action} | target='{target}' | status={status} | extra={json.dumps(extra, default=str)}")

    # Record in structured audit trail
    append_audit_event({
        "event_type": "OPERATION",
        "action": action,
        "target": target,
        "status": status,
        "details": details,
        "extra": extra or {}
    })


def log_failure(
    action: str,
    target: str,
    reason: str,
    exc: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Standardized failure & anomaly logger for NAS operations.
    Emits alerts to error.log, info.log, detail.log, and audit.jsonl.
    """
    if not _enabled:
        return

    # 1. Summary line for info.log and error.log
    err_msg = f"[{action}] [FAILED] {target} — Reason: {reason}"
    logger.error(err_msg)

    # 2. Granular breakdown for detail.log
    detail_lines = [
        f"=== [NAS FAILURE ANOMALY] ===",
        f"Session ID: {SESSION_ID}",
        f"Action:     {action}",
        f"Target:     {target}",
        f"Reason:     {reason}",
    ]
    if context:
        detail_lines.append(f"Context:    {json.dumps(context, indent=2, default=str)}")
    if exc:
        detail_lines.append(f"Exception:  {type(exc).__name__}: {str(exc)}")
        detail_lines.append("Traceback:")
        detail_lines.append(traceback.format_exc())
    detail_lines.append("=" * 28)

    logger.debug("\n".join(detail_lines))

    # 3. Structured audit event
    append_audit_event({
        "event_type": "FAILURE",
        "action": action,
        "target": target,
        "status": "FAILED",
        "reason": reason,
        "exception_type": type(exc).__name__ if exc else None,
        "context": context or {}
    })
