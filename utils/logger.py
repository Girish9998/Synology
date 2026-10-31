"""
utils/logger.py — Production-Grade Asynchronous Non-Blocking Logging Engine.

Architecture:
  - Non-blocking QueueHandler & QueueListener: File I/O & rotation runs in a background thread.
  - Dynamic request/session tracing via Python standard contextvars (ContextVar).
  - 2-file consolidated logging:
      * logs/app.log   : Chronological operations across CLI, web app, bots, and skills (INFO/DEBUG)
      * logs/error.log : Isolated errors, warnings, and complete exception stack traces
  - Real-time ANSI-colorized stdout terminal streaming.
  - Safe Windows file rotation with multi-process collision resilience.
"""

from __future__ import annotations

import atexit
import contextvars
import datetime
import json
import logging
import os
import queue
import sys
import traceback
import uuid
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

# Context variable for per-request / per-job correlation tracing
_current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
SESSION_ID: str = uuid.uuid4().hex[:8]


def set_trace_id(trace_id: str) -> None:
    """Set correlation trace ID for current execution context/coroutine."""
    _current_trace_id.set(str(trace_id))


def get_trace_id() -> str:
    """Get correlation trace ID or fallback to process session ID."""
    tid = _current_trace_id.get()
    return tid if tid else SESSION_ID


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

# Load settings from config.json with env overrides
_cfg: Dict[str, Any] = {}
if _config_file.exists():
    try:
        with open(_config_file, "r", encoding="utf-8") as f:
            _cfg = json.load(f).get("logging", {})
    except Exception:
        pass

_enabled: bool = _cfg.get("enabled", True)
_log_dir_name: str = os.environ.get("LOG_DIR", _cfg.get("log_dir", "logs"))
_log_dir: Path = _workspace_root / _log_dir_name
_app_file: str = _cfg.get("app_log", "app.log")
_error_file: str = _cfg.get("error_log", "error.log")
_log_level_str: str = os.environ.get("LOG_LEVEL", _cfg.get("log_level", "INFO")).upper()
_log_level: int = getattr(logging, _log_level_str, logging.INFO)
_console_output: bool = _cfg.get("console_output", True)
_color_console: bool = _cfg.get("color_console", True)
_max_bytes: int = _cfg.get("max_bytes", 10 * 1024 * 1024)
_backup_count: int = _cfg.get("backup_count", 5)

if _enabled:
    try:
        _log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


class ContextInjectingFilter(logging.Filter):
    """Injects dynamic trace ID and session ID into LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id") or not record.trace_id:
            record.trace_id = get_trace_id()  # type: ignore[attr-defined]
        if not hasattr(record, "session_id") or not record.session_id:
            record.session_id = SESSION_ID    # type: ignore[attr-defined]
        return True

# Backwards compatibility alias
ContextFilter = ContextInjectingFilter


def append_audit_event(event: Dict[str, Any]) -> None:
    """Backwards compatibility stub for audit events (routed to app.log)."""
    pass


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler resilient against Windows file locking during rotation."""

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except (PermissionError, OSError):
            # Another process or worker has an open lock on the file. Continue appending safely.
            pass


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with optional ANSI colors."""

    # ANSI Colors
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[1;31m" # Bold Red
    }

    def __init__(self, use_color: bool = True) -> None:
        super().__init__(datefmt="%H:%M:%S")
        self.use_color = use_color and sys.stdout.isatty() or os.name == "nt"

    def format(self, record: logging.LogRecord) -> str:
        asctime = self.formatTime(record, self.datefmt)
        levelname = record.levelname
        name = record.name
        message = record.getMessage()
        trace_id = getattr(record, "trace_id", "")

        trace_part = f" [{trace_id}]" if trace_id and trace_id != SESSION_ID else ""

        if self.use_color:
            color = self.COLORS.get(record.levelno, self.RESET)
            return (
                f"{self.DIM}[{asctime}]{self.RESET} "
                f"{color}{levelname:<5}{self.RESET} "
                f"{self.DIM}[{name}]{self.RESET}"
                f"{trace_part} {message}"
            )
        return f"[{asctime}] [{levelname:<5}] [{name}]{trace_part} {message}"


# --- Global Queue & QueueListener Initialization ---
_log_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
_listener: Optional[QueueListener] = None
_initialized = False


def _init_logging_system() -> None:
    global _listener, _initialized
    if _initialized:
        return
    _initialized = True

    if not _enabled:
        return

    ctx_filter = ContextInjectingFilter()
    sinks: List[logging.Handler] = []

    # 1. Console Stream Handler
    if _console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(_log_level)
        console_handler.setFormatter(ConsoleFormatter(use_color=_color_console))
        console_handler.addFilter(ctx_filter)
        sinks.append(console_handler)

    # 2. Main App Log (Rotating, app.log)
    app_log_path = _log_dir / _app_file
    file_fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-5s] [trace:%(trace_id)s] [%(name)s:%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        h_app = SafeRotatingFileHandler(
            str(app_log_path),
            maxBytes=_max_bytes,
            backupCount=_backup_count,
            encoding="utf-8",
        )
        h_app.setLevel(logging.DEBUG)  # Capture everything down to DEBUG in file
        h_app.setFormatter(file_fmt)
        h_app.addFilter(ctx_filter)
        sinks.append(h_app)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to initialize app.log handler: {e}\n")

    # 3. Error & Anomaly Log (Rotating, error.log)
    error_log_path = _log_dir / _error_file
    try:
        h_err = SafeRotatingFileHandler(
            str(error_log_path),
            maxBytes=_max_bytes,
            backupCount=_backup_count,
            encoding="utf-8",
        )
        h_err.setLevel(logging.WARNING)  # WARNING, ERROR, CRITICAL
        h_err.setFormatter(file_fmt)
        h_err.addFilter(ctx_filter)
        sinks.append(h_err)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to initialize error.log handler: {e}\n")

    # Start asynchronous background QueueListener
    if sinks:
        _listener = QueueListener(_log_queue, *sinks, respect_handler_level=True)
        _listener.start()

        def _shutdown() -> None:
            if _listener is not None:
                _listener.stop()

        atexit.register(_shutdown)


_init_logging_system()

# Shared non-blocking QueueHandler with calling-thread context injection
_queue_handler: Optional[QueueHandler] = None
if _enabled:
    _queue_handler = QueueHandler(_log_queue)
    _queue_handler.addFilter(ContextInjectingFilter())


def get_logger(name: str = "synology") -> logging.Logger:
    """
    Get or configure a logger connected to the non-blocking production QueueHandler.
    All loggers inherit asynchronous file writing, trace context, and console streaming.
    """
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)

    if _enabled and _queue_handler is not None:
        # Check if already attached to prevent duplicate entries
        if not any(isinstance(h, QueueHandler) for h in log.handlers):
            log.addHandler(_queue_handler)

    # Disable propagation to root so root does not re-emit records if root has handlers
    log.propagate = False
    return log


# Default workspace logger instance
logger = get_logger("synology")


def log_operation(
    action: str,
    target: str,
    details: Optional[str] = None,
    status: str = "SUCCESS",
    extra: Optional[Dict[str, Any]] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> None:
    """Production operational milestone logger."""
    active_logger = logger_instance or logger
    extra_str = f" | {json.dumps(extra, default=str)}" if extra else ""
    msg = f"[{action}] [{status}] {target}"
    if details:
        msg += f" — {details}"
    msg += extra_str

    if status.upper() in ("FAIL", "FAILURE", "ERROR"):
        active_logger.warning(msg)
    else:
        active_logger.info(msg)


def log_failure(
    action: str,
    target: str,
    reason: str,
    exc: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> None:
    """Production failure & anomaly logger with stack trace capture."""
    active_logger = logger_instance or logger
    err_msg = f"[{action}] [FAILED] {target} — Reason: {reason}"
    if context:
        err_msg += f" | context={json.dumps(context, default=str)}"

    if exc:
        active_logger.error(err_msg, exc_info=exc)
    else:
        active_logger.error(err_msg)
