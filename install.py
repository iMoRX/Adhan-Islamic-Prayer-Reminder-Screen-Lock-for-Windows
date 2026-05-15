"""
Prayer Reminder - Windows Installer
Installs dependencies, sets up startup entry, and launches the app.
Run this ONCE as Administrator.
"""

import sys
import os
import subprocess
import winreg
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
WATCHDOG = SCRIPT_DIR / "watchdog.py"
MAIN_APP = SCRIPT_DIR / "prayer_app.py"
APP_NAME = "PrayerReminderWatchdog"


def pip_install(packages):
    print(f"Installing: {' '.join(packages)}")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "--quiet", *packages
    ])


def install_dependencies():
    print("=" * 50)
    print("Installing Python dependencies...")
    print("=" * 50)
    packages = [
        "Pillow",
        "pystray",
        "pywin32",
        "psutil",
        "plyer",
    ]
    pip_install(packages)
    print("✓ Dependencies installed.\n")


def add_to_startup():
    """Add watchdog to Windows Registry startup (HKCU - no admin needed)."""
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable

    cmd = f'"{pythonw}" "{WATCHDOG}"'
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path,
                              0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        print(f"✓ Added to Windows startup registry.\n  Command: {cmd}\n")
        return True
    except Exception as e:
        print(f"✗ Could not add to registry: {e}")
        print("  You can manually add it via Task Scheduler.\n")
        return False


def create_task_scheduler_xml():
    """Generate an XML file for Task Scheduler (alternative to registry)."""
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Prayer Reminder Watchdog - Ensures prayer reminders run at all times.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{pythonw}</Command>
      <Arguments>"{WATCHDOG}"</Arguments>
      <WorkingDirectory>{SCRIPT_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""
    xml_path = SCRIPT_DIR / "prayer_task.xml"
    xml_path.write_text(xml, encoding="utf-16")
    print(f"✓ Task Scheduler XML created: {xml_path}")
    print("  Import it via: Task Scheduler > Action > Import Task\n")
    return xml_path


def launch_app():
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable
    print("Launching Prayer Reminder...")
    subprocess.Popen(
        [pythonw, str(WATCHDOG)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    print("✓ Prayer Reminder is now running in the system tray.\n")


def main():
    print("\n" + "=" * 50)
    print("  🕌  PRAYER REMINDER - INSTALLER")
    print("=" * 50 + "\n")

    install_dependencies()
    add_to_startup()
    create_task_scheduler_xml()
    launch_app()

    print("=" * 50)
    print("  Installation Complete!")
    print("  Look for the crescent moon 🌙 in your system tray.")
    print("  Right-click the icon to see today's prayer times.")
    print("=" * 50)
    input("\nPress Enter to close...")


if __name__ == "__main__":
    main()
