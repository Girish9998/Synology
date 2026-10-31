import os
import re
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def _find_workspace_root() -> str:
    curr = os.path.abspath(CURRENT_DIR)
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "config.json")) or os.path.exists(os.path.join(curr, "requirements.txt")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))

ROOT_DIR = _find_workspace_root()

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, '.env'))

# Import download and NAS saving logic
try:
    from .downloader import download_audio_to_mp3, DEFAULT_DOWNLOAD_DIR, save_file_to_nas, get_nas_download_dir
except (ImportError, ValueError):
    from downloader import download_audio_to_mp3, DEFAULT_DOWNLOAD_DIR, save_file_to_nas, get_nas_download_dir

# Centralized production logging
from utils.logger import get_logger, set_trace_id, log_operation, log_failure

logger = get_logger("audio_downloader.bot")

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


def parse_time_str(time_str: str) -> int:
    """Converts a string like '3:00' or '03:00' or '1:05:00' to seconds."""
    parts = list(map(int, time_str.split(':')))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a greeting when the user starts the bot."""
    await update.message.reply_text(
        "Hello! I am your Universal Audio Downloader & Synology NAS Bot 🎵\n\n"
        "Send me any music link (YouTube, Spotify, Apple Music) and I will:\n"
        "1. Download & tag the song with high-res album art\n"
        "2. Save the track directly to your Synology NAS (Downloads folder)\n"
        "3. Send the MP3 back to you right here in Telegram!\n\n"
        "Bonus Tip: You can add start and end times to trim the audio!\n"
        "Example: https://youtu.be/dQw4w9WgXcQ 01:00 01:30"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming messages, checks for URLs, and downloads audio."""
    text = update.message.text
    if not text:
        return

    # Set trace ID for this telegram request
    set_trace_id(f"tg_{update.update_id}")

    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or update.effective_user.first_name if update.effective_user else "Unknown"
    logger.info("Received Telegram message from %s (chat_id: %s): %s", user_name, chat_id, text)

    # Simple check if the message contains a URL
    if not re.search(r'http[s]?://', text):
        logger.warning("No URL found in message from %s: %s", user_name, text)
        await update.message.reply_text("Please send me a valid URL (e.g., from YouTube, Spotify, or Apple Music).")
        return

    # Extract the first URL found in the message
    url = re.search(r'(http[s]?://\S+)', text).group(1)

    # Search for optional time stamps like MM:SS or HH:MM:SS
    time_matches = re.findall(r'\b\d{1,2}:\d{2}(?::\d{2})?\b', text)
    start_time, end_time = None, None
    if len(time_matches) >= 1:
        start_time = parse_time_str(time_matches[0])
    if len(time_matches) >= 2:
        end_time = parse_time_str(time_matches[1])

    logger.info("Initiating download for URL: %s (start_time=%s, end_time=%s)", url, start_time, end_time)

    status_text = "⏳ Downloading... This might take a moment."
    if start_time is not None:
        status_text = "⏳ Downloading specific section... This might take a moment."
    status_msg = await update.message.reply_text(status_text)

    filepath = None
    last_error = None

    # Try up to 2 times (once + one automatic retry on transient failures)
    for attempt in range(1, 3):
        try:
            filepath = await asyncio.to_thread(download_audio_to_mp3, url, DEFAULT_DOWNLOAD_DIR, start_time, end_time)
            if filepath and os.path.exists(filepath):
                break
            else:
                last_error = "File was not found after download."
        except Exception as e:
            last_error = str(e)
            logger.error(f"Download attempt {attempt} failed: {e}")
            if attempt < 2:
                await status_msg.edit_text(
                    f"⚠️ Attempt {attempt} failed. Retrying in 3 seconds...\n"
                    f"{last_error[:200]}"
                )
                await asyncio.sleep(3)
                await status_msg.edit_text("🔄 Retrying download...")

    if not filepath or not os.path.exists(filepath):
        await status_msg.edit_text(
            f"❌ Download failed after retrying.\n\n"
            f"URL: {url}\n"
            f"Error: {last_error[:300] if last_error else 'Unknown error'}\n\n"
            "Please try again or send a different link."
        )
        return

    # Save to Synology NAS download folder
    await status_msg.edit_text("💾 Archiving track to Synology NAS...")
    nas_filepath = None
    try:
        nas_filepath = await asyncio.to_thread(save_file_to_nas, filepath)
    except Exception as e:
        logger.error(f"Failed to copy file to NAS: {e}")

    await status_msg.edit_text("✅ Saved to NAS! Uploading MP3 to Telegram...")

    # Send the audio file to Telegram
    try:
        filename = os.path.basename(filepath)
        clean_title = filename.replace('.mp3', '')
        caption = f"🎵 {clean_title}"
        if nas_filepath:
            caption += f"\n💾 Saved to NAS: Downloads/{filename}"

        with open(filepath, 'rb') as audio_file:
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=audio_file,
                title=clean_title,
                caption=caption
            )

        # Cleanup the status message
        await status_msg.delete()
        log_operation("TELEGRAM_REQUEST", filepath, f"Sent to {update.effective_chat.id} and saved to NAS: {nas_filepath}")

    except Exception as e:
        logger.error(f"Error uploading file to Telegram: {e}")
        status_info = f"\n\n💾 Note: The track was successfully saved to your NAS at: {nas_filepath}" if nas_filepath else ""
        await status_msg.edit_text(f"❌ Telegram upload failed:{status_info}\n{str(e)[:300]}")
    finally:
        # Delete local temporary cache file from the server to save space (file is already safely saved on NAS!)
        try:
            if filepath and os.path.exists(filepath):
                if nas_filepath and os.path.abspath(filepath) != os.path.abspath(nas_filepath):
                    os.remove(filepath)
        except Exception as e:
            logger.error(f"Failed to delete local staging file {filepath}: {e}")


if __name__ == '__main__':
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set in the .env file.")
        sys.exit(1)

    print("Starting Telegram Bot (PaniManishi @kirklandmaid_bot)...")
    app = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start polling
    app.run_polling()
