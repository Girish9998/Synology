import argparse
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from downloader import download_audio_to_mp3, save_file_to_nas, get_nas_download_dir

def main():
    parser = argparse.ArgumentParser(description="Download audio from a URL, convert to MP3, and archive to Synology NAS.")
    parser.add_argument(
        'url', 
        type=str, 
        nargs='?', # Make it optional so we can fallback to prompt
        help='The URL of the video or audio to download (YouTube, Spotify, Apple Music)'
    )
    parser.add_argument(
        '--no-nas',
        action='store_true',
        help='Skip copying the downloaded file to the Synology NAS download folder'
    )
    
    args = parser.parse_args()

    # If URL is not provided as an argument, prompt the user for it
    url = args.url
    if not url:
        try:
            url = input("Please enter the URL to download: ").strip()
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            return

    if not url:
        print("No URL provided. Exiting.")
        return

    print("--- Universal Audio to MP3 & Synology NAS Downloader ---")
    filepath = download_audio_to_mp3(url)
    print(f"Downloaded local file: {filepath}")

    if not args.no_nas and filepath:
        nas_path = save_file_to_nas(filepath)
        if nas_path:
            print(f"Archived to Synology NAS: {nas_path}")

if __name__ == "__main__":
    main()
