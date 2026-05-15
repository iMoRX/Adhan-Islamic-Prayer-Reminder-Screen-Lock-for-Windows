"""
Build Script - Creates standalone .exe files using PyInstaller.
Run this on Windows to produce distributable executables.
"""

import subprocess
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()


def install_pyinstaller():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build(script_name, exe_name, windowed=True, icon=None):
    args = [
        "pyinstaller",
        "--onefile",
        f"--name={exe_name}",
        "--clean",
    ]
    if windowed:
        args.append("--windowed")  # no console window
    if icon and os.path.isfile(icon):
        args.append(f"--icon={icon}")

    args.append(str(SCRIPT_DIR / script_name))
    print(f"\nBuilding {exe_name}.exe ...")
    subprocess.check_call(args, cwd=str(SCRIPT_DIR))
    print(f"✓ {exe_name}.exe created in dist/")


if __name__ == "__main__":
    print("Installing PyInstaller...")
    install_pyinstaller()

    build("watchdog.py", "PrayerReminderWatchdog", windowed=True)
    build("install.py", "PrayerInstaller", windowed=False)
    build("prayer_app.py", "PrayerReminder", windowed=True)

    print("\n" + "="*50)
    print("Build complete! Find your .exe files in the dist/ folder.")
    print("Distribute: PrayerInstaller.exe + config.json together.")
    print("="*50)
