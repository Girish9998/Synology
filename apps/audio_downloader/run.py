"""Direct entry point for running the Audio Downloader sub-application."""
import os
import sys

SUBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(SUBAPP_DIR))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from run_all import main if "main" in dir() else None

if __name__ == "__main__":
    import subprocess
    run_all_script = os.path.join(ROOT_DIR, "run_all.py")
    subprocess.run([sys.executable, run_all_script])
