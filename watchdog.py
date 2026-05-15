"""
Prayer Reminder Watchdog
Ensures the prayer app is always running. If the main process dies, this restarts it.
Run this as a Windows Service or at startup via Task Scheduler.
"""

import sys
import os
import time
import subprocess
import logging
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
MAIN_SCRIPT = SCRIPT_DIR / "prayer_app.py"
LOG_FILE = os.path.join(os.path.expanduser("~"), "prayer_watchdog.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

def find_pythonw():
    """Find pythonw.exe (runs without console window)."""
    candidates = [
        sys.executable.replace("python.exe", "pythonw.exe"),
        os.path.join(os.path.dirname(sys.executable), "pythonw.exe"),
        "pythonw",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return sys.executable


def is_prayer_app_running():
    """Check if prayer_app.py process is running."""
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                cmdline_str = " ".join(cmdline)
                if "prayer_app" in cmdline_str and proc.pid != os.getpid():
                    return True
            except Exception:
                pass
    except Exception as e:
        logging.error(f"psutil error: {e}")
    return False


def start_prayer_app():
    pythonw = find_pythonw()
    logging.info(f"Starting prayer app: {pythonw} {MAIN_SCRIPT}")
    proc = subprocess.Popen(
        [pythonw, str(MAIN_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    return proc


def main():
    logging.info("Watchdog started.")
    proc = None

    while True:
        try:
            if proc is None or proc.poll() is not None:
                if not is_prayer_app_running():
                    logging.info("Prayer app not running. Restarting...")
                    proc = start_prayer_app()
                    time.sleep(5)  # give it time to start
        except Exception as e:
            logging.error(f"Watchdog error: {e}")

        time.sleep(15)  # check every 15 seconds


if __name__ == "__main__":
    main()
