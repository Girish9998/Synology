import os
import sys
import uuid
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SUBAPP_DIR = os.path.dirname(BACKEND_DIR)
APPS_DIR = os.path.dirname(SUBAPP_DIR)
ROOT_DIR = os.path.dirname(APPS_DIR)

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

try:
    from .downloader import download_audio_to_mp3, save_file_to_nas, get_nas_download_dir
except (ImportError, ValueError):
    from downloader import download_audio_to_mp3, save_file_to_nas, get_nas_download_dir

# Centralized production logging integration
from utils.logger import get_logger, set_trace_id, log_operation, log_failure

logger = get_logger("audio_downloader.app")
frontend_logger = get_logger("audio_downloader.frontend")

logger.info("Initializing Audio Downloader FastAPI backend...")

app = FastAPI(title="Universal Audio Downloader API")

# HTTP Middleware for correlation tracing
@app.middleware("http")
async def correlation_trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
    set_trace_id(f"req_{trace_id}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = trace_id
    return response

FRONTEND_DIR = os.path.join(SUBAPP_DIR, "frontend")
INDEX_HTML = os.path.join(FRONTEND_DIR, "index.html")

# Serve static assets (frontend) from the apps/frontend directory
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Root endpoint returns the frontend HTML page
@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    client_host = request.client.host if request.client else "unknown"
    logger.info("Serving frontend homepage index.html to %s", client_host)
    if os.path.exists(INDEX_HTML):
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Audio Downloader Frontend Not Found</h1>"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-NAS-Archiving"],
)

class DownloadRequest(BaseModel):
    url: str
    start_time: int | None = None  # optional start in seconds
    end_time: int | None = None    # optional end in seconds

class ClientLogRequest(BaseModel):
    level: str
    message: str
    timestamp: str
    metadata: dict | None = None

@app.post("/api/log")
async def log_client_message(request: ClientLogRequest):
    level_upper = request.level.upper()
    log_msg = f"[CLIENT] {request.message} (Client Time: {request.timestamp}) | Metadata: {request.metadata}"
    
    if level_upper == "DEBUG":
        frontend_logger.debug(log_msg)
    elif level_upper == "INFO":
        frontend_logger.info(log_msg)
    elif level_upper in ("WARN", "WARNING"):
        frontend_logger.warning(log_msg)
    elif level_upper == "ERROR":
        frontend_logger.error(log_msg)
    else:
        frontend_logger.info(log_msg)
        
    return {"status": "success"}

def _archive_to_nas(filepath: str, filename: str) -> None:
    """Background task to archive downloaded audio file to Synology NAS without delaying response."""
    try:
        nas_path = save_file_to_nas(filepath)
        if nas_path:
            logger.info("Background NAS archive complete: %s", nas_path)
            log_operation("NAS_ARCHIVE", nas_path, f"Archived {filename} to Synology NAS")
        else:
            logger.warning("Background NAS archive returned None for file: %s", filepath)
    except Exception as e:
        logger.error("Exception during background NAS archive of %s: %s", filepath, e)
        log_failure("NAS_ARCHIVE", filepath, str(e), exc=e)


@app.post("/api/download")
async def download_audio(request: DownloadRequest, background_tasks: BackgroundTasks):
    logger.info("Received download request for URL: %s", request.url)
    logger.debug("Request details - start_time: %s, end_time: %s", request.start_time, request.end_time)
    
    if not request.url:
        logger.warning("Empty URL provided in request payload.")
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        logger.debug("Invoking downloader module...")
        filepath = download_audio_to_mp3(
            request.url,
            start_time=request.start_time,
            end_time=request.end_time,
        )
        
        if not filepath or not os.path.exists(filepath):
            logger.error("Download failed or file not found on disk at: %s", filepath)
            raise HTTPException(status_code=500, detail="File download failed or file not found.")

        filename = os.path.basename(filepath)
        logger.info("Successfully processed audio download: %s -> %s", request.url, filename)
        logger.debug("File stored locally at: %s", filepath)

        # Archive to Synology NAS download folder in background (does not block client streaming)
        background_tasks.add_task(_archive_to_nas, filepath, filename)

        # Return the file as a downloadable attachment with confirmation header
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='audio/mpeg',
            headers={"X-NAS-Archiving": "true"}
        )

    except Exception as e:
        logger.exception("An error occurred during audio download processing:")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/restart")
def restart_system():
    logger.info("Received system restart request. Sending SIGTERM to PID 1...")
    import threading, signal
    def _do_exit():
        time.sleep(0.5)
        try:
            os.kill(1, signal.SIGTERM)
        except Exception as e:
            logger.error("Failed to kill PID 1: %s", e)
            os._exit(0)
    threading.Thread(target=_do_exit).start()
    return {"status": "restarting", "message": "Docker container PID 1 signaled to restart."}

@app.get("/health")
def health():
    nas_dir = get_nas_download_dir()
    return {
        "status": "ok",
        "message": "Audio Downloader API is running.",
        "nas_download_dir": nas_dir,
        "nas_dir_accessible": os.path.exists(nas_dir)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
