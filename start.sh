#!/bin/sh
LOG_FILE="/volume1/docker/audio-downloader/build.log"
exec > "$LOG_FILE" 2>&1

echo "=== Deployment started at $(date) ==="
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

cd /volume1/docker/audio-downloader || exit 1

echo "Docker binary: $(which docker 2>&1)"
echo "Docker-compose binary: $(which docker-compose 2>&1)"

if which docker-compose >/dev/null 2>&1; then
    echo "Restarting with latest code and volumes: docker-compose up -d --force-recreate"
    docker-compose up -d --force-recreate
elif which docker >/dev/null 2>&1; then
    echo "Restarting with latest code and volumes: docker compose up -d --force-recreate"
    docker compose up -d --force-recreate
else
    echo "ERROR: Neither docker-compose nor docker command found in PATH."
    exit 1
fi

echo "Exit status: $?"
echo "=== Deployment finished at $(date) ==="
