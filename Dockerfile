# Production Dockerfile for Audio Downloader on Synology NAS
FROM python:3.11-slim

# Install system dependencies: ffmpeg for audio transcoding
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy repository source code
COPY . .

# Expose web service port
EXPOSE 8000

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    LOG_LEVEL=INFO

# Start application via supervisor (runs FastAPI web app and Telegram bot)
CMD ["python", "run_all.py"]
