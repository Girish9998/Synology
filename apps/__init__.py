"""Applications package for Synology NAS automation."""
import sys

try:
    from . import audio_downloader
    audiodownloader = audio_downloader
    sys.modules[__name__ + ".audiodownloader"] = audio_downloader
except ImportError:
    pass
