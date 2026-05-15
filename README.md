# 🕌 Prayer Reminder — Full Documentation

A lightweight Windows background application that:
- Runs silently in the **system tray**
- Gives a **5-minute heads-up** before each prayer
- **Locks your entire screen** at prayer time with a non-closable fullscreen overlay
- The overlay **cannot be dismissed** until a **10-minute countdown** expires
- A **watchdog process** automatically restarts the app if it is killed

---

## 📁 File Structure

```
prayer_reminder/
├── prayer_app.py       ← Main application (tray icon + lock screen)
├── watchdog.py         ← Watchdog that restarts the app if killed
├── install.py          ← One-click installer (run once)
├── build_exe.py        ← Builds standalone .exe files (optional)
├── config.json         ← Your location & calculation settings
└── README.md           ← This file
```

---

## ⚙️ Requirements

- **Windows 10 or 11**
- **Python 3.9+** — Download from https://python.org (check "Add to PATH")
- Internet not required after setup (prayer times are calculated locally)

---

## 🚀 Quick Start (Recommended)

### Step 1 — Install Python
1. Go to https://python.org/downloads
2. Download Python 3.11 or later
3. Run the installer — **check "Add Python to PATH"**
4. Click Install Now

### Step 2 — Run the Installer
1. Open the `prayer_reminder` folder
2. Double-click **`install.py`**  
   *(or right-click → Open with → Python)*
3. The installer will:
   - Install all required Python packages automatically
   - Add the watchdog to Windows startup (via Registry)
   - Generate a Task Scheduler XML backup
   - Launch the app immediately

### Step 3 — Done!
Look for the **crescent moon 🌙** icon in your system tray (bottom-right corner).  
Right-click it to see today's prayer times.

---

## 🕌 How It Works

| Time | What Happens |
|------|-------------|
| T-5 minutes | A gold notification appears in the top-right corner of your screen |
| T-0 (Prayer time) | A fullscreen dark overlay appears immediately |
| T+0 to T+10 min | The overlay counts down 10 minutes — no other windows visible |
| T+10 min | The screen is released automatically |

### The Lock Screen
- **Fullscreen** — covers everything
- **Always on top** — no window can appear above it
- **Alt-F4 blocked** — cannot be closed with keyboard shortcuts
- **Focus guardian** — grabs focus back every 0.5 seconds
- **10-minute countdown** — timer visible on screen; releases automatically

### The Watchdog
- Runs as a separate process
- Checks every 15 seconds if the main app is alive
- If the app is killed (via Task Manager or otherwise), **restarts it within 15 seconds**
- Added to Windows startup so it survives reboots

---

## ⚙️ Configuration (config.json)

Edit `config.json` to change your location or calculation method:

```json
{
  "location": {
    "city": "Najran",
    "latitude": 17.4924,
    "longitude": 44.1277,
    "timezone_offset": 3
  },
  "calculation": {
    "method": "UmmAlQura"
  },
  "timing": {
    "warning_minutes_before": 5,
    "lock_duration_minutes": 10
  }
}
```

### Available Calculation Methods
| Method | Used By |
|--------|---------|
| `UmmAlQura` | Saudi Arabia (recommended) |
| `MWL` | Muslim World League |
| `ISNA` | North America |
| `Egypt` | Egypt |
| `Karachi` | Pakistan, India |

### Finding Your Coordinates
1. Go to maps.google.com
2. Right-click your city → "What's here?"
3. Copy the latitude and longitude shown

---

## 🏗️ Building a Standalone .exe (Optional)

If you want to distribute the app without requiring Python:

```
# In Command Prompt, navigate to the prayer_reminder folder:
cd path\to\prayer_reminder

# Run the build script:
python build_exe.py
```

This creates:
- `dist/PrayerInstaller.exe` — Full installer for other PCs
- `dist/PrayerReminder.exe` — Main app
- `dist/PrayerReminderWatchdog.exe` — Watchdog

---

## 🛠️ Manual Startup (Alternative to Installer)

If you prefer to set up startup manually via **Task Scheduler**:

1. Open **Task Scheduler** (search in Start Menu)
2. Click **Action → Import Task**
3. Select the `prayer_task.xml` file (created by installer)
4. Click OK — done!

Or manually via Registry:
1. Press `Win + R`, type `regedit`, press Enter
2. Navigate to: `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
3. Create a new **String Value** named `PrayerReminderWatchdog`
4. Set value to: `"C:\path\to\pythonw.exe" "C:\path\to\prayer_reminder\watchdog.py"`

---

## 📝 Log Files

Logs are written to your user folder:
- `C:\Users\YourName\prayer_reminder.log` — Main app log
- `C:\Users\YourName\prayer_watchdog.log` — Watchdog log

---

## ❓ Troubleshooting

**App doesn't start:**
- Make sure Python is installed and added to PATH
- Open Command Prompt and run: `python install.py`

**Tray icon not showing:**
- Check the hidden icons area (arrow ^ in taskbar)
- Check `prayer_reminder.log` for errors

**Prayer times seem off:**
- Verify your latitude/longitude in `config.json`
- Confirm your timezone offset (Saudi Arabia = 3)
- Try changing the calculation method to `MWL`

**App gets killed and doesn't restart:**
- Make sure `watchdog.py` is in startup (check Registry or Task Scheduler)
- The watchdog checks every 15 seconds — wait a moment

---

## 🌙 May Allah accept your prayers

> *"Indeed, prayer has been decreed upon the believers a decree of specified times."*  
> — Quran 4:103

---

## Uninstall

1. Right-click tray icon → Quit
2. Open `regedit` → `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → Delete `PrayerReminderWatchdog`
3. Delete the `prayer_reminder` folder
