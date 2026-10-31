import requests
import os
import urllib.parse
from urllib.parse import unquote
import logging

# Set up logging matching workspace production standard
from utils.logger import get_logger

logger = get_logger("audio_downloader.cobalt")

COBALT_API_URL = os.environ.get("COBALT_API_URL", "https://api.cobalt.tools/")

def download_via_cobalt(url: str, output_dir: str, start_time: int = None, end_time: int = None) -> str:
    """
    Downloads audio from a URL using the public Cobalt API instance as a fallback.
    Returns the absolute path to the downloaded MP3.
    """
    logger.info("Initiating fallback download via Cobalt API for URL: %s", url)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Use current Cobalt v10 parameter format
    payload = {
        "url": url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
        "youtubeVideoCodec": "h264"
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(COBALT_API_URL, json=payload, headers=headers, timeout=30)
        logger.debug("Cobalt API responded with status code: %s", response.status_code)
        
        if response.status_code != 200:
            logger.error("Cobalt API returned error code %s: %s", response.status_code, response.text)
            raise ValueError(f"Cobalt API failed with status {response.status_code}")

        data = response.json()
        logger.debug("Cobalt response data: %s", data)

        # The 'url' field contains the direct link to the compiled MP3 file
        download_url = data.get("url")
        if not download_url:
            status = data.get("status", "unknown")
            text = data.get("text", "No message")
            raise ValueError(f"Cobalt response status: {status} | Details: {text}")

        # Download the file content from Cobalt's streaming server
        logger.info("Cobalt processing complete. Downloading MP3 stream from: %s", download_url)
        file_response = requests.get(download_url, stream=True, timeout=60)
        
        if file_response.status_code != 200:
            raise ValueError(f"Failed to stream processed MP3 from Cobalt endpoint: {file_response.status_code}")

        # Determine a filename. Use fallback if headers don't have it
        filename = "cobalt_audio.mp3"
        disposition = file_response.headers.get("content-disposition")
        if disposition:
            # Parse filename from Content-Disposition header
            import re
            name_match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', disposition, re.IGNORECASE)
            if name_match:
                filename = unquote(name_match.group(1))
        
        # Ensure it has .mp3 extension
        if not filename.lower().endswith(".mp3"):
            filename = os.path.splitext(filename)[0] + ".mp3"

        filepath = os.path.join(output_dir, filename)
        logger.debug("Writing streamed MP3 file to path: %s", filepath)
        
        with open(filepath, "wb") as f:
            for chunk in file_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Check if we need to trim the audio locally using ffmpeg (since Cobalt does not support custom start/end timestamps)
        if start_time is not None or end_time is not None:
            logger.info("Applying start_time=%s and end_time=%s slicing locally...", start_time, end_time)
            filepath = trim_audio_locally(filepath, start_time, end_time)

        logger.info("Successfully downloaded audio via Cobalt API! File: %s", filepath)
        return filepath

    except Exception as e:
        logger.exception("An error occurred during Cobalt API fallbacks:")
        raise e

def trim_audio_locally(filepath: str, start_time: int = None, end_time: int = None) -> str:
    """Uses native system ffmpeg to cut and slice audio when time stamps are supplied."""
    import subprocess
    
    base, ext = os.path.splitext(filepath)
    temp_filepath = base + "_trimmed" + ext
    
    # Construct slicing commands
    cmd = ["ffmpeg", "-y"]
    if start_time is not None:
        cmd.extend(["-ss", str(start_time)])
    if end_time is not None:
        cmd.extend(["-to", str(end_time)])
        
    cmd.extend(["-i", filepath, "-acodec", "copy", temp_filepath])
    
    # Local Windows compatibility check
    win_ffmpeg = r'C:\Users\giris\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffmpeg.exe'
    if os.name == 'nt' and os.path.exists(win_ffmpeg):
        cmd[0] = win_ffmpeg

    logger.debug("Running trimming command: %s", " ".join(cmd))
    try:
        # Run command silently
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        # Clean up original large file
        os.remove(filepath)
        # Rename sliced file
        os.rename(temp_filepath, filepath)
        logger.debug("Local slicing applied successfully.")
    except Exception as err:
        logger.error("Failed to slice audio locally using ffmpeg: %s", err)
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
            
    return filepath
