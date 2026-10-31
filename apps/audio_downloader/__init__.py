"""Audio Downloader sub-application for Synology workspace."""

from utils.logger import (
    get_logger,
    get_trace_id,
    log_failure,
    log_operation,
    set_trace_id,
)

logger = get_logger("audio_downloader")

__all__ = [
    "logger",
    "get_logger",
    "set_trace_id",
    "get_trace_id",
    "log_operation",
    "log_failure",
]
