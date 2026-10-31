// app.js - Premium Frontend Logger & Request Handler
(function () {
    // Send logs asynchronously to the server
    function sendLogToServer(level, message, args) {
        // Avoid sending the log call itself recursively
        const payload = {
            level: level,
            message: message,
            timestamp: new Date().toISOString(),
            metadata: args.length > 0 ? { args: args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : arg) } : null
        };
        fetch('/api/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).catch(err => {
            // Quiet fallback to console in case backend logging fails
            console.warn("Failed to send frontend log to server:", err);
        });
    }

    // Industry-standard frontend namespace logger
    const Logger = {
        debug(message, ...args) {
            console.debug(`%c[DEBUG] %c[${new Date().toISOString()}] ${message}`, "color: #a59cb8; font-weight: bold;", "color: inherit;", ...args);
            sendLogToServer("debug", message, args);
        },
        info(message, ...args) {
            console.info(`%c[INFO]  %c[${new Date().toISOString()}] ${message}`, "color: #8a2be2; font-weight: bold;", "color: inherit;", ...args);
            sendLogToServer("info", message, args);
        },
        warn(message, ...args) {
            console.warn(`%c[WARN]  %c[${new Date().toISOString()}] ${message}`, "color: #ff9800; font-weight: bold;", "color: inherit;", ...args);
            sendLogToServer("warn", message, args);
        },
        error(message, ...args) {
            console.error(`%c[ERROR] %c[${new Date().toISOString()}] ${message}`, "color: #ff5252; font-weight: bold;", "color: inherit;", ...args);
            sendLogToServer("error", message, args);
        }
    };

    Logger.info("Frontend application initialized.");

    const form = document.getElementById('downloadForm');
    const statusDiv = document.getElementById('status');
    const progressWrapper = document.getElementById('progressWrapper');
    const progressBar = document.getElementById('progressBar');
    const progressStage = document.getElementById('progressStage');

    if (!form) {
        Logger.error("Failed to find downloadForm element in the DOM.");
        return;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const urlInput = document.getElementById('url');
        const startInput = document.getElementById('start_time');
        const endInput = document.getElementById('end_time');

        const url = urlInput ? urlInput.value.trim() : '';
        const start = startInput ? startInput.value : '';
        const end = endInput ? endInput.value : '';

        Logger.info("Form submitted.", { url, start_time: start, end_time: end });

        // Update UI to show downloading progress
        statusDiv.textContent = '⏳ Processing audio...';
        statusDiv.style.color = '#f3f0ff';
        statusDiv.className = 'status fade-in';

        // Show progress bar and reset status
        progressWrapper.style.display = 'block';
        progressBar.style.width = '5%';
        progressStage.textContent = 'Analyzing URL & Smart Matching...';

        // Animate simulated progress checkpoints
        let percent = 5;
        const progressInterval = setInterval(() => {
            if (percent < 90) {
                // Slower increment as it reaches 90%
                const step = percent < 40 ? 5 : (percent < 70 ? 2 : 1);
                percent += step;
                progressBar.style.width = `${percent}%`;

                // Update text based on checkpoints
                if (percent < 25) {
                    progressStage.textContent = 'Analyzing URL & Smart Matching...';
                } else if (percent < 75) {
                    progressStage.textContent = 'Downloading audio stream via yt-dlp...';
                } else {
                    progressStage.textContent = 'Applying high-res ID3 metadata tags...';
                }
                Logger.debug(`Estimated progress: ${percent}% - ${progressStage.textContent}`);
            }
        }, 600);

        // Prepare request parameters
        const payload = { url };
        if (start) {
            payload.start_time = parseInt(start, 10);
            Logger.debug("Adding start_time to request parameter:", payload.start_time);
        }
        if (end) {
            payload.end_time = parseInt(end, 10);
            Logger.debug("Adding end_time to request parameter:", payload.end_time);
        }

        try {
            Logger.info("Sending request to backend /api/download...");
            Logger.debug("Request payload:", payload);

            const response = await fetch('/api/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'audio/mpeg',
                },
                body: JSON.stringify(payload),
            });

            Logger.debug(`Response status received: ${response.status} ${response.statusText}`);

            // Clear the simulated interval
            clearInterval(progressInterval);

            if (!response.ok) {
                let errorMessage = 'Download failed';
                try {
                    const errData = await response.json();
                    errorMessage = errData.detail || errorMessage;
                } catch (jsonErr) {
                    Logger.warn("Failed to parse error response JSON. Using default error message.");
                }
                throw new Error(errorMessage);
            }

            // Fill progress bar to 100%
            progressBar.style.width = '100%';
            progressStage.textContent = 'Packaging MP3 file...';

            Logger.info("File downloaded successfully. Processing stream blob...");
            const blob = await response.blob();
            const urlObject = URL.createObjectURL(blob);
            
            // Extract filename from header
            const disposition = response.headers.get('content-disposition');
            let filename = 'audio.mp3';
            if (disposition) {
                const filenameMatch = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
                if (filenameMatch && filenameMatch[1]) {
                    filename = decodeURIComponent(filenameMatch[1]);
                    Logger.debug("Extracted filename from headers:", filename);
                } else {
                    Logger.warn("No filename pattern matched in Content-Disposition header:", disposition);
                }
            } else {
                Logger.warn("No Content-Disposition header present, using default filename.");
            }

            // Trigger file saving dialog
            Logger.info(`Saving file: ${filename}`);
            const a = document.createElement('a');
            a.href = urlObject;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(urlObject);

            statusDiv.textContent = '✅ Download complete!';
            statusDiv.style.color = '#4caf50';
            progressStage.textContent = 'Done!';
            Logger.info("Download session completed successfully.");

            // Hide progress bar after 3 seconds
            setTimeout(() => {
                progressWrapper.style.display = 'none';
            }, 3000);

        } catch (err) {
            clearInterval(progressInterval);
            progressBar.style.width = '0%';
            progressWrapper.style.display = 'none';
            Logger.error("Error occurred during download process:", err);
            statusDiv.textContent = `❌ Error: ${err.message}`;
            statusDiv.style.color = '#ff5252';
        }
    });
})();
