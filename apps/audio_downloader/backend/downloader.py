import yt_dlp
import os
import sys
import re
import shutil
import requests
import urllib.parse
from urllib.parse import unquote
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TPE2, TALB, TCON, TDRC, error
from typing import Optional, Dict, Any, List, Tuple

# Determine base directory and workspace root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')

def _find_workspace_root() -> str:
    curr = os.path.abspath(BASE_DIR)
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "config.json")) or os.path.exists(os.path.join(curr, "requirements.txt")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR)))

ROOT_DIR = _find_workspace_root()
COOKIES_FILE = os.path.join(ROOT_DIR, 'cookies.txt')

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Centralized production logging
from utils.logger import get_logger, log_operation, log_failure

logger = get_logger("audio_downloader.downloader")

# FFmpeg paths specific to this setup
FFMPEG_DIR = r'C:\Users\giris\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin'


def get_nas_download_dir() -> str:
    r"""
    Resolves the target NAS download folder path from config.json or environment variables.

    Priority order:
      1. NAS_DOWNLOAD_PATH env var — used by Docker container (volume mount at /nas_downloads)
      2. Z:\Downloads — Windows SMB mapped drive (dev machine default)
      3. \\host\share\Downloads — UNC fallback
    """
    # 1. Docker / Linux container env var override (highest priority)
    env_override = os.environ.get("NAS_DOWNLOAD_PATH")
    if env_override:
        try:
            os.makedirs(env_override, exist_ok=True)
            logger.debug("Using NAS_DOWNLOAD_PATH override: %s", env_override)
            return env_override
        except Exception as e:
            logger.warning("Could not create NAS_DOWNLOAD_PATH dir %s: %s", env_override, e)

    cfg_drive = "Z:"
    cfg_folder = "Downloads"
    try:
        cfg_path = os.path.join(ROOT_DIR, "config.json")
        if os.path.exists(cfg_path):
            import json
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                cfg_drive = cfg.get("synology", {}).get("default_drive", "Z:")
                cfg_folder = cfg.get("synology", {}).get("download_folder", "Downloads")
    except Exception:
        pass

    mapped_target = os.path.join(cfg_drive, os.sep, cfg_folder) if not cfg_drive.endswith(os.sep) else os.path.join(cfg_drive, cfg_folder)
    if os.path.exists(cfg_drive):
        try:
            os.makedirs(mapped_target, exist_ok=True)
            return mapped_target
        except Exception:
            pass

    nas_host = os.environ.get("NAS_HOST", "Girish_NAS")
    nas_share = os.environ.get("NAS_SHARE", "music")
    unc_target = rf"\\{nas_host}\{nas_share}\{cfg_folder}"
    try:
        os.makedirs(unc_target, exist_ok=True)
        return unc_target
    except Exception:
        pass

    return mapped_target


def save_file_to_nas(filepath: str) -> Optional[str]:
    """
    Copies a downloaded audio file directly into the Synology NAS download folder.
    Returns the final destination path on the NAS, or None if copying failed.
    """
    if not filepath or not os.path.exists(filepath):
        logger.warning("save_file_to_nas: Source file does not exist: %s", filepath)
        return None

    nas_dir = get_nas_download_dir()
    os.makedirs(nas_dir, exist_ok=True)
    filename = os.path.basename(filepath)
    nas_filepath = os.path.join(nas_dir, filename)

    try:
        shutil.copy2(filepath, nas_filepath)
        logger.info("Successfully saved file to NAS download folder: %s", nas_filepath)
        try:
            log_operation("SAVE_TO_NAS", nas_filepath, f"File {filename} saved to Synology NAS")
        except Exception:
            pass
        return nas_filepath
    except Exception as e:
        logger.error("Failed to copy file to NAS (%s -> %s): %s", filepath, nas_filepath, e)
        try:
            log_failure("SAVE_TO_NAS", filepath, e)
        except Exception:
            pass
        return None


# Dynamically write cookies.txt from environment variable if provided
cookies_env = os.environ.get("COOKIES_CONTENT")
if cookies_env:
    logger.info("COOKIES_CONTENT environment variable detected. Attempting to write to cookies file...")
    try:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write(cookies_env.strip())
        logger.info("Successfully wrote COOKIES_CONTENT to file at: %s", COOKIES_FILE)
    except Exception as e:
        logger.error("Failed to write COOKIES_CONTENT to file: %s", e)
else:
    logger.warning("No COOKIES_CONTENT environment variable detected in system env.")


def clean_movie_album_name(collection_name: str) -> str:
    """
    Extracts the clean movie/album name by stripping soundtrack labels,
    years, and redundant bracketed noise. E.g.:
    'Mahavatar Narsimha (Telugu) [Original Motion Picture Soundtrack]' -> 'Mahavatar Narsimha'
    """
    if not collection_name:
        return ""
    # Strip soundtrack descriptors
    clean = re.sub(
        r'(?i)\s*(\[|\()(original motion picture soundtrack|ost|soundtrack|motion picture soundtrack|from\s+.*?|single)(\]|\))',
        '',
        collection_name
    ).strip()
    # Strip language indicators if enclosed in parentheses
    clean = re.sub(r'(?i)\s*\((telugu|tamil|hindi|kannada|malayalam)\)', '', clean).strip()
    return clean.strip() or collection_name.strip()


def sanitize_filename(name: str) -> str:
    """Removes invalid filesystem characters from filenames on Windows."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r'\s+', " ", clean).strip()
    return clean or "Track"


def extract_search_candidates(raw_title: str) -> Tuple[List[Tuple[str, Optional[str], str]], List[str]]:
    """
    Intelligently splits noisy YouTube video titles (e.g. 'Song | Movie | Composer | Studio')
    into candidate iTunes search queries, identifying the probable song title and movie album name.
    """
    clean = re.sub(r'\[.*?\]|\(.*?\)', '', raw_title)
    # Split by common YouTube title delimiters
    parts = [p.strip() for p in re.split(r'\||//| - | – | ~ ', clean) if p.strip()]

    noise_pattern = (
        r'(?i)\b(official|video|song|songs|lyrics|lyric|audio|visualizer|music|hd|4k|'
        r'remaster|remastered|full|promo|teaser|trailer|hombale films|kleem productions|'
        r't-series|aditya music|sony music|zee music|think music|lahari music)\b'
    )
    cleaned_parts = [re.sub(noise_pattern, '', p).strip() for p in parts]
    cleaned_parts = [p for p in cleaned_parts if p]

    candidates = []
    if len(cleaned_parts) >= 2:
        # Candidate 1: Song + Movie
        candidates.append((f"{cleaned_parts[0]} {cleaned_parts[1]}", cleaned_parts[1], cleaned_parts[0]))
        # Candidate 2: Song alone
        candidates.append((cleaned_parts[0], cleaned_parts[1], cleaned_parts[0]))
        # Candidate 3: Movie + Song
        candidates.append((f"{cleaned_parts[1]} {cleaned_parts[0]}", cleaned_parts[1], cleaned_parts[0]))
    elif len(cleaned_parts) == 1:
        candidates.append((cleaned_parts[0], None, cleaned_parts[0]))

    whole = re.sub(noise_pattern, '', clean).strip()
    whole = re.sub(r'\s+', ' ', whole)
    if whole:
        fallback_t = cleaned_parts[0] if cleaned_parts else whole
        candidates.append((whole, None, fallback_t))

    return candidates, cleaned_parts


def search_itunes_smart(raw_title: str) -> Optional[Dict[str, Any]]:
    """
    Attempts multiple query candidates against the iTunes search API, returning
    the verified metadata dict with clean movie album name and 1000x1000 artwork.
    """
    candidates, cleaned_parts = extract_search_candidates(raw_title)
    logger.debug("Smart search candidates for '%s': %s", raw_title, candidates)

    for query, fallback_movie, fallback_title in candidates:
        try:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=1"
            resp = requests.get(url, timeout=6).json()
            if resp.get('resultCount', 0) > 0:
                track = resp['results'][0]
                collection = track.get('collectionName', '')
                clean_album = clean_movie_album_name(collection) or fallback_movie
                # Ensure album is never 'Download' or 'Downloads'
                if not clean_album or clean_album.lower() in ('download', 'downloads'):
                    clean_album = fallback_movie or track.get('trackName', 'Single')

                art_url = track.get('artworkUrl100', '').replace('100x100bb', '1000x1000bb')
                metadata = {
                    'title': track.get('trackName', fallback_title),
                    'album': clean_album,
                    'artist': track.get('artistName', cleaned_parts[2] if len(cleaned_parts) > 2 else 'Unknown Artist'),
                    'albumartist': cleaned_parts[2] if len(cleaned_parts) > 2 else track.get('artistName', ''),
                    'genre': track.get('primaryGenreName', 'Film Soundtrack'),
                    'year': track.get('releaseDate', '')[:4] if track.get('releaseDate') else None,
                    'art_url': art_url,
                    'source': 'itunes'
                }
                logger.info("iTunes smart match found: Title='%s' | Album='%s' | Artist='%s'",
                            metadata['title'], metadata['album'], metadata['artist'])
                return metadata
        except Exception as e:
            logger.debug("Candidate query '%s' failed: %s", query, e)

    # Fallback to parsed title segments if iTunes returned no matches
    if cleaned_parts:
        title = cleaned_parts[0]
        album = cleaned_parts[1] if len(cleaned_parts) > 1 else title
        artist = cleaned_parts[2] if len(cleaned_parts) > 2 else "Unknown Artist"
        if not album or album.lower() in ('download', 'downloads'):
            album = title
        return {
            'title': title,
            'album': album,
            'artist': artist,
            'albumartist': artist,
            'genre': 'Soundtrack',
            'year': None,
            'art_url': None,
            'source': 'parsed_fallback'
        }

    return None


def apply_id3_tags(filepath: str, metadata: Dict[str, Any]) -> str:
    """
    Embeds metadata tags into the MP3 file, strictly assigning Album to the Movie Album Name
    (never 'Downloads' or 'Download'). Renames the file to clean {Title}.mp3.
    Returns the final (potentially renamed) absolute filepath.
    """
    if not filepath or not os.path.exists(filepath):
        return filepath

    try:
        audio = MP3(filepath, ID3=ID3)
        try:
            audio.add_tags()
        except error:
            pass  # Tags already exist

        title = metadata.get('title')
        artist = metadata.get('artist')
        album = metadata.get('album')
        albumartist = metadata.get('albumartist')
        genre = metadata.get('genre')
        year = metadata.get('year')
        art_url = metadata.get('art_url')

        # Critical rule: Album must be the movie album name, NEVER 'Download' or 'Downloads'
        if not album or album.lower() in ('download', 'downloads'):
            album = title or "Single"

        if title:
            audio.tags.add(TIT2(encoding=3, text=title))
        if artist:
            audio.tags.add(TPE1(encoding=3, text=artist))
        if album:
            audio.tags.add(TALB(encoding=3, text=album))
        if albumartist:
            audio.tags.add(TPE2(encoding=3, text=albumartist))
        if genre:
            audio.tags.add(TCON(encoding=3, text=genre))
        if year:
            audio.tags.add(TDRC(encoding=3, text=str(year)))

        if art_url:
            try:
                art_data = requests.get(art_url, timeout=10).content
                audio.tags.add(
                    APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,  # Cover front
                        desc='Cover',
                        data=art_data
                    )
                )
            except Exception as art_err:
                logger.warning("Failed to embed cover art: %s", art_err)

        audio.save(v2_version=3)
        logger.info("Saved tags to file: Title='%s' | Album='%s' | Artist='%s'", title, album, artist)

        # Rename to clean {Title}.mp3
        if title:
            clean_name = sanitize_filename(title) + ".mp3"
            new_path = os.path.join(os.path.dirname(filepath), clean_name)
            if os.path.abspath(new_path) != os.path.abspath(filepath):
                if os.path.exists(new_path):
                    try:
                        os.remove(new_path)
                    except Exception:
                        pass
                try:
                    os.rename(filepath, new_path)
                    logger.info("Renamed file to clean title: %s", new_path)
                    filepath = new_path
                except Exception as ren_err:
                    logger.warning("Could not rename file to clean title: %s", ren_err)

        return filepath
    except Exception as e:
        logger.exception("Failed to apply custom ID3 tags: %s", e)
        return filepath


def extract_spotify_title(url: str):
    """Scrapes the Spotify track title and artist from the page title."""
    try:
        html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if match:
            title = match.group(1)
            title = title.replace(" - song and lyrics by ", " ")
            title = title.replace(" | Spotify", "")
            title = title.replace(" - song by ", " ")
            return title.strip()
    except Exception:
        pass
    return None


def extract_applemusic_title(url: str):
    """Fallback simple extraction for Apple Music using the URL path."""
    try:
        match = re.search(r'/album/([^/]+)', url)
        if match:
            title = unquote(match.group(1)).replace('-', ' ')
            return title.strip()
    except Exception:
        pass
    return None


def duration_filter(info, *, incomplete):
    """Filters out videos longer than 10 minutes (600 seconds)."""
    duration = info.get('duration')
    if duration and duration > 600:
        return 'The video is too long (over 10 minutes).'
    return None


def download_with_ytdlp(query: str, output_dir: str, start_time: int = None, end_time: int = None) -> str:
    """Downloads a YouTube URL or a ytsearch query directly and returns the file path."""
    logger.info("Using yt-dlp to download: %s", query)
    if start_time is not None or end_time is not None:
        logger.debug("Download time range: start=%s, end=%s", start_time, end_time)

    is_search = str(query).startswith('ytsearch')
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': not is_search,
        'ignoreerrors': False if is_search else True,
        'writethumbnail': True,
        'match_filter': duration_filter,
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            },
            {
                'key': 'EmbedThumbnail',
            }
        ],
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': True,
    }

    if os.path.exists(COOKIES_FILE):
        logger.info("Using exported cookies from: %s", COOKIES_FILE)
        ydl_opts['cookiefile'] = COOKIES_FILE
    else:
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['web', 'ios', 'android'],
            }
        }

    win_ffmpeg = r'C:\Users\giris\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin'
    if os.name == 'nt' and os.path.exists(win_ffmpeg):
        ydl_opts['ffmpeg_location'] = win_ffmpeg

    if start_time is not None or end_time is not None:
        def time_range(info_dict, ydl):
            yield (start_time or 0, end_time or float('inf'))
        ydl_opts['download_ranges'] = time_range

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.debug("Calling extract_info on query...")
            info = ydl.extract_info(query, download=True)

            if info is None:
                logger.error("extract_info returned None. YouTube blocked request or invalid query.")
                raise ValueError("No video information retrieved.")

            if 'entries' in info:
                entries = [e for e in (info.get('entries') or []) if e]
                if entries:
                    info = entries[0]
                else:
                    raise ValueError(f"No search results returned for query: {query}")

            if not info or (not info.get('requested_downloads') and not ydl.prepare_filename(info)):
                raise ValueError("Download skipped. Ensure video is not a livestream.")

            if 'requested_downloads' in info and len(info['requested_downloads']) > 0:
                final_path = info['requested_downloads'][0]['filepath']
            else:
                original_path = ydl.prepare_filename(info)
                if not os.path.exists(original_path) and not os.path.exists(os.path.splitext(original_path)[0] + '.mp3'):
                    raise ValueError("The video is too long (over 10 minutes) and was skipped.")
                base_name, _ = os.path.splitext(original_path)
                final_path = base_name + '.mp3'

            return final_path
    except Exception as e:
        logger.exception("An error occurred during yt-dlp download: %s", e)
        raise e


def download_audio_to_mp3(url: str, output_dir: str = DEFAULT_DOWNLOAD_DIR, start_time: int = None, end_time: int = None) -> str:
    """
    Downloads audio from the given URL and converts it to an MP3 file.
    Performs smart metadata matching, assigns Movie Album Name to the Album tag,
    and returns the absolute path to the clean tagged MP3.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    search_query = None
    matched_metadata = None

    if 'spotify.com' in url or 'spotify.link' in url:
        clean_title = extract_spotify_title(url)
        if clean_title:
            matched_metadata = search_itunes_smart(clean_title)
            search_query = clean_title

    elif 'apple.com' in url:
        clean_title = extract_applemusic_title(url)
        if clean_title:
            matched_metadata = search_itunes_smart(clean_title)
            search_query = clean_title

    else:
        # Strip playlist, mix, radio, and mobile tracking params (?is=, ?si=, &list=)
        if "watch?v=" in url or "youtu.be/" in url:
            url = re.sub(r'([?&](list|start_radio|index|is|si)=[^&]+)', '', url)

        # Smart Match for YouTube / generic URLs
        logger.info("Analyzing URL for smart matching: %s", url)
        try:
            ydl_opts_meta = {'quiet': True, 'no_warnings': True, 'noplaylist': True}
            if os.path.exists(COOKIES_FILE):
                ydl_opts_meta['cookiefile'] = COOKIES_FILE
            else:
                ydl_opts_meta['extractor_args'] = {'youtube': {'player_client': ['web', 'ios', 'android']}}

            with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    # 1. Try YouTube official Content ID metadata
                    if info.get('track') and info.get('artist'):
                        cid_title = f"{info['artist']} {info['track']}"
                        matched_metadata = search_itunes_smart(cid_title)
                        if not matched_metadata:
                            matched_metadata = {
                                'title': info['track'],
                                'album': info.get('album') or info['track'],
                                'artist': info['artist'],
                                'albumartist': info['artist'],
                                'genre': info.get('genre', 'Music'),
                                'year': str(info.get('release_year', '')) if info.get('release_year') else None,
                                'art_url': None
                            }
                        search_query = cid_title
                    else:
                        # 2. Extract candidates from video title
                        video_title = info.get('title', '')
                        matched_metadata = search_itunes_smart(video_title)
                        if matched_metadata and matched_metadata.get('source') == 'itunes':
                            search_query = f"{matched_metadata['artist']} {matched_metadata['title']}"
        except Exception as e:
            logger.warning("Smart match lookup error, proceeding with direct download: %s", e)

    # Execute Download with resilient fallback
    try:
        if search_query:
            yt_search = f"ytsearch1:{search_query} official audio"
            try:
                filepath = download_with_ytdlp(yt_search, output_dir, start_time, end_time)
            except Exception as search_err:
                logger.warning("Smart search failed (%s). Falling back to direct URL: %s", search_err, url)
                filepath = download_with_ytdlp(url, output_dir, start_time, end_time)
        else:
            filepath = download_with_ytdlp(url, output_dir, start_time, end_time)
    except Exception as ytdlp_err:
        logger.warning("yt-dlp download failed (%s). Attempting fallback via Cobalt API...", ytdlp_err)
        try:
            from .cobalt import download_via_cobalt
        except (ImportError, ValueError):
            from cobalt import download_via_cobalt
        try:
            filepath = download_via_cobalt(url, output_dir, start_time, end_time)
        except Exception as cobalt_err:
            logger.error("Both yt-dlp and Cobalt API fallback failed.")
            raise ValueError(f"Download failed. yt-dlp: {ytdlp_err} | Cobalt: {cobalt_err}")

    # Apply ID3 Tags & Clean File Renaming
    if matched_metadata:
        filepath = apply_id3_tags(filepath, matched_metadata)

    return filepath
