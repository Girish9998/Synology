import subprocess
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

from utils.logger import get_logger

logger = get_logger("runner")

processes = []

# Get Port from environment, default to 8000
port = os.environ.get("PORT", "8000")

# Start FastAPI web app (always run this)
logger.info("Starting Audio Downloader FastAPI web app on port %s...", port)
fastapi_proc = subprocess.Popen([
    sys.executable, "-m", "uvicorn", "apps.audio_downloader.backend.app:app",
    "--host", "0.0.0.0",
    "--port", port,
    "--reload"
])
processes.append(fastapi_proc)

# Start Telegram Bot if token is provided in environment
token = os.environ.get("TELEGRAM_BOT_TOKEN")
if token:
    logger.info("Starting Telegram Bot (PaniManishi @kirklandmaid_bot)...")
    bot_proc = subprocess.Popen([
        sys.executable, "apps/audio_downloader/backend/bot.py"
    ])
    processes.append(bot_proc)
else:
    logger.warning("TELEGRAM_BOT_TOKEN not set. Skipping Telegram Bot startup.")

try:
    while True:
        # Check if any process has exited
        for p in processes[:]:
            poll_result = p.poll()
            if poll_result is not None:
                logger.warning("Process %s exited with code %s", p.args, poll_result)
                if "bot.py" in str(p.args):
                    logger.warning("⚠️ Telegram bot exited. Continuing with the FastAPI web app...")
                    processes.remove(p)
                else:
                    # If FastAPI exits, terminate everything and exit
                    for other in processes:
                        if other != p:
                            other.terminate()
                    sys.exit(poll_result)
        time.sleep(2)
except KeyboardInterrupt:
    logger.info("Stopping all processes...")
    for p in processes:
        p.terminate()
