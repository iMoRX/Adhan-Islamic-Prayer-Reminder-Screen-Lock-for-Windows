"""
Prayer Reminder - Main Application
Runs in system tray, shows warnings, and locks screen at prayer time.
"""

import sys
import os
import time
import threading
import datetime
import json
import math
import subprocess
import ctypes
import logging
from pathlib import Path

# Setup logging
LOG_FILE = os.path.join(os.path.expanduser("~"), "prayer_reminder.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# ─────────────────────────────────────────────
#  CONFIG LOADER
# ─────────────────────────────────────────────

def load_config():
    """
    Load config.json from the same directory as this script.
    Falls back to Jeddah defaults if file is missing or invalid.
    """
    defaults = {
        "location": {
            "city": "Jeddah",
            "country": "Saudi Arabia",
            "latitude": 21.754970671346157,
            "longitude": 39.1961270687735,
            "timezone_offset": 3
        },
        "calculation": {
            "method": "UmmAlQura",
            "asr_method": "Standard"
        },
        "timing": {
            "warning_minutes_before": 5,
            "lock_duration_minutes": 10
        }
    }

    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Deep merge: data over defaults
            for key in defaults:
                if key in data:
                    if isinstance(defaults[key], dict):
                        defaults[key].update(data[key])
                    else:
                        defaults[key] = data[key]
            logging.info(f"Config loaded from {config_path}: lat={defaults['location']['latitude']}, "
                         f"lng={defaults['location']['longitude']}, method={defaults['calculation']['method']}")
        except Exception as e:
            logging.error(f"Failed to read config.json: {e}. Using defaults.")
    else:
        logging.warning(f"config.json not found at {config_path}. Using defaults.")

    return defaults

CONFIG = load_config()

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tk"])
    import tkinter as tk
    from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageDraw, ImageFont
    import pystray
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "pystray"])
    from PIL import Image, ImageDraw, ImageFont
    import pystray

try:
    import win32api
    import win32con
    import win32gui
    import win32process
    import psutil
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "psutil"])
    import win32api
    import win32con
    import win32gui
    import win32process
    import psutil

try:
    from plyer import notification
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "plyer"])
    from plyer import notification


# ─────────────────────────────────────────────
#  PRAYER TIME CALCULATION  (Umm al-Qura / MWL)
# ─────────────────────────────────────────────

class PrayerTimes:
    """
    Calculates Islamic prayer times using standard astronomical formulas.
    Coordinates and method are loaded from config.json via CONFIG.

    Key fix: hour_angle() uses sin(altitude) not cos(angle).
    Fajr/Isha angles are BELOW horizon, so altitude = -angle.
    """

    def __init__(self, latitude=None, longitude=None, timezone=None,
                 method=None, asr_method=None):
        loc  = CONFIG["location"]
        calc = CONFIG["calculation"]
        self.lat        = latitude   if latitude   is not None else loc["latitude"]
        self.lng        = longitude  if longitude  is not None else loc["longitude"]
        self.tz         = timezone   if timezone   is not None else loc["timezone_offset"]
        self.method     = method     or calc.get("method",     "UmmAlQura")
        self.asr_method = asr_method or calc.get("asr_method", "Standard")

        logging.info(f"PrayerTimes init: lat={self.lat}, lng={self.lng}, "
                     f"tz={self.tz}, method={self.method}, asr={self.asr_method}")

        # method -> (fajr_angle°, isha_angle° or None, isha_minutes_after_maghrib or None)
        self.methods = {
            "UmmAlQura": (18.5, None, 90),
            "Makkah":    (18.5, None, 90),
            "MWL":       (18.0, 17.0, None),
            "ISNA":      (15.0, 15.0, None),
            "Egypt":     (19.5, 17.5, None),
            "Karachi":   (18.0, 18.0, None),
        }

    def _jd(self, date):
        y, m, d = date.year, date.month, date.day
        if m <= 2:
            y -= 1; m += 12
        A = int(y / 100)
        B = 2 - A + int(A / 4)
        return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5

    def _sun_position(self, jd):
        D  = jd - 2451545.0
        g  = math.radians(357.529 + 0.98560028 * D)
        q  = 280.459 + 0.98564736 * D
        q_norm = q % 360          # normalize before converting to hours
        L  = math.radians(q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
        e  = math.radians(23.439 - 0.00000036 * D)
        RA = math.degrees(math.atan2(math.cos(e) * math.sin(L), math.cos(L))) / 15
        dec = math.asin(math.sin(e) * math.sin(L))   # radians
        eq_t = q_norm / 15 - RA                       # equation of time in hours
        return dec, eq_t

    def _hour_angle(self, dec, altitude_deg):
        """
        Return hour angle (degrees) for the given altitude above the horizon.
        altitude_deg is POSITIVE above horizon, NEGATIVE below.
        """
        lat     = math.radians(self.lat)
        sin_alt = math.sin(math.radians(altitude_deg))
        num     = sin_alt - math.sin(lat) * math.sin(dec)
        den     = math.cos(lat) * math.cos(dec)
        if abs(den) < 1e-10:
            return None
        ratio = num / den
        if ratio < -1 or ratio > 1:
            return None
        return math.degrees(math.acos(ratio))

    def get_times(self, date=None):
        if date is None:
            date = datetime.date.today()

        jd          = self._jd(date)
        dec, eq_t   = self._sun_position(jd)
        noon_ut     = 12 - self.lng / 15 - eq_t
        noon_local  = noon_ut + self.tz

        def to_time(decimal_h):
            decimal_h = decimal_h % 24
            h = int(decimal_h)
            m = int((decimal_h - h) * 60)
            s = int(((decimal_h - h) * 60 - m) * 60)
            return datetime.time(h, m, s)

        fajr_angle, isha_angle, isha_minutes = self.methods.get(
            self.method, self.methods["MWL"]
        )

        # Fajr: sun fajr_angle° BELOW horizon
        fajr_ha = self._hour_angle(dec, -fajr_angle) or 0
        fajr    = noon_local - fajr_ha / 15

        # Dhuhr: solar noon
        dhuhr = noon_local + 0.0333

        # Sunrise / Sunset: standard -0.833° (refraction + solar disc)
        sr_ha   = self._hour_angle(dec, -0.833) or 0
        maghrib = noon_local + sr_ha / 15   # sunset

        # Asr: shadow length = shadow_factor * object height
        sf = 1 if self.asr_method == "Standard" else 2
        asr_alt = math.degrees(math.atan(1.0 / (sf + math.tan(abs(math.radians(self.lat) - dec)))))
        asr_ha  = self._hour_angle(dec, asr_alt) or 0
        asr     = noon_local + asr_ha / 15

        # Isha
        if isha_minutes is not None:
            isha = maghrib + isha_minutes / 60
        else:
            isha_ha = self._hour_angle(dec, -isha_angle) or 0
            isha    = noon_local + isha_ha / 15

        names  = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        values = [fajr,   dhuhr,   asr,   maghrib,   isha]
        return {n: to_time(v) for n, v in zip(names, values)}


# ─────────────────────────────────────────────
#  LOCK SCREEN WINDOW
# ─────────────────────────────────────────────

class PrayerLockScreen:
    """
    Covers ALL monitors with a fullscreen lock window on each.
    Uses win32api to enumerate monitor geometry, then places one
    Toplevel window per monitor at the correct position and size.
    The primary window holds the countdown UI; secondary windows
    show a plain black overlay with the prayer message.
    All windows are always-on-top, overrideredirect, and focus-guarded.
    """

    LOCK_DURATION = 10 * 60  # 10 minutes in seconds

    def __init__(self, prayer_name, on_complete):
        self.prayer_name  = prayer_name
        self.on_complete  = on_complete
        self.seconds_left = self.LOCK_DURATION
        self.root         = None          # primary Tk root
        self.overlays     = []            # secondary Toplevel windows
        self._alive       = True
        self._thread      = threading.Thread(target=self._build, daemon=True)
        self._thread.start()

    # ── helpers ────────────────────────────────────────────────

    def _get_monitors(self):
        """
        Return list of (x, y, w, h) for every monitor via win32api.
        Falls back to single primary screen if win32api is unavailable.
        """
        monitors = []
        try:
            import win32api as _w32
            for mon in _w32.EnumDisplayMonitors():
                info = _w32.GetMonitorInfo(mon[0])
                r = info["Monitor"]          # (left, top, right, bottom)
                x, y, r2, b = r
                monitors.append((x, y, r2 - x, b - y))
        except Exception as e:
            logging.warning(f"Monitor enumeration failed ({e}), using primary only.")
        if not monitors:
            # Fallback: create a temporary root just to get screen size
            tmp = tk.Tk(); tmp.withdraw()
            monitors = [(0, 0, tmp.winfo_screenwidth(), tmp.winfo_screenheight())]
            tmp.destroy()
        logging.info(f"Monitors detected: {monitors}")
        return monitors

    def _make_window(self, x, y, w, h, is_primary=False):
        """Create and configure one lock window at the given screen position."""
        win = tk.Toplevel(self.root) if not is_primary else self.root
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#0a0a0f")
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        for seq in ("<Alt-F4>", "<Alt-Tab>", "<Escape>",
                    "<Super_L>", "<Super_R>", "<Control-Escape>"):
            win.bind(seq, lambda e: "break")
        return win

    # ── build ──────────────────────────────────────────────────

    def _build(self):
        self.root = tk.Tk()
        self.root.withdraw()   # hide root briefly while we set up

        monitors = self._get_monitors()

        # Pick the largest monitor as primary (for main UI)
        monitors_sorted = sorted(monitors, key=lambda m: m[2]*m[3], reverse=True)
        primary = monitors_sorted[0]
        secondaries = monitors_sorted[1:]

        px, py, pw, ph = primary

        # Build primary window (main UI)
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0a0a0f")
        self.root.geometry(f"{pw}x{ph}+{px}+{py}")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        for seq in ("<Alt-F4>", "<Alt-Tab>", "<Escape>",
                    "<Super_L>", "<Super_R>", "<Control-Escape>"):
            self.root.bind(seq, lambda e: "break")

        self._build_ui(self.root, pw, ph)

        # Build secondary overlay windows
        for (sx, sy, sw, sh) in secondaries:
            ov = self._make_window(sx, sy, sw, sh, is_primary=False)
            self._build_secondary_ui(ov, sw, sh)
            self.overlays.append(ov)

        self._start_focus_guardian()
        self._tick()
        self.root.mainloop()

    def _build_secondary_ui(self, win, W, H):
        """Plain black overlay with centered prayer message for secondary monitors."""
        canvas = tk.Canvas(win, width=W, height=H, bg="#0a0a0f", highlightthickness=0)
        canvas.place(x=0, y=0)

        # Subtle grid
        for i in range(0, W, 80):
            canvas.create_line(i, 0, i, H, fill="#1a1a25", width=1)
        for i in range(0, H, 80):
            canvas.create_line(0, i, W, i, fill="#1a1a25", width=1)

        canvas.create_text(W//2, H//2 - 60,
                           text="🕌",
                           font=("Segoe UI Emoji", 72),
                           fill="#c9a84c", anchor="center")
        canvas.create_text(W//2, H//2 + 30,
                           text=f"Time for {self.prayer_name} Prayer",
                           font=("Georgia", 32, "bold"),
                           fill="#ffffff", anchor="center")
        canvas.create_text(W//2, H//2 + 80,
                           text=" الصَّلَاةَ وَأَقِيمُوا •  Establish the Prayer",
                           font=("Georgia", 16),
                           fill="#c9a84c", anchor="center")

        # Live timer label — linked to same StringVar as primary
        tk.Label(win, textvariable=self.timer_var,
                 font=("Courier New", 48, "bold"),
                 fg="#c9a84c", bg="#0a0a0f").place(relx=0.5, rely=0.78, anchor="center")

    def _build_ui(self, root, W, H):
        """Main prayer lock UI on the primary monitor."""
        canvas = tk.Canvas(root, width=W, height=H, bg="#0a0a0f",
                           highlightthickness=0)
        canvas.place(x=0, y=0)
        self._draw_background(canvas, W, H)

        canvas.create_text(W//2, 80,
                           text=" النَّوْم مِنَ خَيْرٌ ِالصَّلَاةُ",
                           font=("Georgia", 28, "italic"),
                           fill="#c9a84c", anchor="center")
        canvas.create_text(W//2, 130,
                           text="Prayer is better than sleep",
                           font=("Georgia", 16),
                           fill="#8a7a5a", anchor="center")
        canvas.create_text(W//2, 240,
                           text="🕌",
                           font=("Segoe UI Emoji", 90),
                           fill="#c9a84c", anchor="center")
        canvas.create_text(W//2, 360,
                           text=f"Time for {self.prayer_name} Prayer",
                           font=("Georgia", 42, "bold"),
                           fill="#ffffff", anchor="center")
        canvas.create_text(W//2, 415,
                           text="الصَّلَاةَ وَأَقِيمُوا  •  Establish the Prayer",
                           font=("Georgia", 18),
                           fill="#c9a84c", anchor="center")
        canvas.create_line(W//2 - 300, 445, W//2 + 300, 445,
                           fill="#c9a84c", width=1)

        bx1, by1 = W//2 - 380, 460
        bx2, by2 = W//2 + 380, 560
        canvas.create_rectangle(bx1, by1, bx2, by2,
                                 outline="#c9a84c", width=2, fill="#12121a")
        canvas.create_text(W//2, 495,
                           text="Stop what you are doing. Make Wudu. Go pray.",
                           font=("Georgia", 20, "bold"),
                           fill="#ffffff", anchor="center")
        canvas.create_text(W//2, 530,
                           text="This screen will release after the countdown below.",
                           font=("Georgia", 14),
                           fill="#aaaaaa", anchor="center")

        # Shared timer StringVar (secondary windows also read this)
        self.timer_var = tk.StringVar(value="10:00")
        tk.Label(root, textvariable=self.timer_var,
                 font=("Courier New", 72, "bold"),
                 fg="#c9a84c", bg="#0a0a0f").place(relx=0.5, rely=0.78, anchor="center")
        tk.Label(root, text="minutes remaining",
                 font=("Georgia", 16),
                 fg="#666666", bg="#0a0a0f").place(relx=0.5, rely=0.87, anchor="center")
        tk.Label(root,
                 text="📿  Remember: Prayer is the pillar of the religion  📿",
                 font=("Georgia", 14, "italic"),
                 fg="#8a7a5a", bg="#0a0a0f").place(relx=0.5, rely=0.94, anchor="center")

        self.canvas = canvas

    def _draw_background(self, canvas, W, H):
        layers = 20
        for i in range(layers, 0, -1):
            r = int(10 + (i / layers) * 4)
            g = int(10 + (i / layers) * 4)
            b = int(15 + (i / layers) * 20)
            color = f"#{r:02x}{g:02x}{b:02x}"
            pad = (layers - i) * (W // (layers * 2))
            canvas.create_rectangle(pad, pad, W - pad, H - pad,
                                    fill=color, outline="")
        for i in range(0, W, 80):
            canvas.create_line(i, 0, i, H, fill="#1a1a25", width=1)
        for i in range(0, H, 80):
            canvas.create_line(0, i, W, i, fill="#1a1a25", width=1)

    # ── countdown ──────────────────────────────────────────────

    def _tick(self):
        if self.seconds_left <= 0:
            self._release()
            return
        m = self.seconds_left // 60
        s = self.seconds_left % 60
        self.timer_var.set(f"{m:02d}:{s:02d}")
        self.seconds_left -= 1
        self.root.after(1000, self._tick)

    # ── focus guardian ─────────────────────────────────────────

    def _start_focus_guardian(self):
        """Keep all lock windows on top and focused."""
        def guardian():
            while self._alive and self.root:
                try:
                    if self.root.winfo_exists():
                        self.root.focus_force()
                        self.root.lift()
                        self.root.attributes("-topmost", True)
                    for ov in self.overlays:
                        try:
                            if ov.winfo_exists():
                                ov.lift()
                                ov.attributes("-topmost", True)
                        except Exception:
                            pass
                except Exception:
                    pass
                time.sleep(0.4)
        threading.Thread(target=guardian, daemon=True).start()

    # ── release ────────────────────────────────────────────────

    def _release(self):
        self._alive = False
        logging.info(f"Prayer lock screen released for {self.prayer_name}")
        for ov in self.overlays:
            try:
                ov.destroy()
            except Exception:
                pass
        self.overlays.clear()
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None
        if self.on_complete:
            self.on_complete()


# ─────────────────────────────────────────────
#  WARNING NOTIFICATION WINDOW
# ─────────────────────────────────────────────

class WarningWindow:
    """5-minute heads-up toast window."""

    def __init__(self, prayer_name, minutes_left):
        self.prayer_name = prayer_name
        self.minutes_left = minutes_left
        threading.Thread(target=self._show, daemon=True).start()

    def _show(self):
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.95)
        root.configure(bg="#1a1208")

        W_screen = root.winfo_screenwidth()
        W, H = 420, 160
        x = W_screen - W - 20
        y = 20
        root.geometry(f"{W}x{H}+{x}+{y}")

        # Border frame
        frame = tk.Frame(root, bg="#c9a84c", padx=2, pady=2)
        frame.pack(fill="both", expand=True)

        inner = tk.Frame(frame, bg="#1a1208", padx=15, pady=12)
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="🕌  Prayer Reminder",
                 font=("Georgia", 14, "bold"),
                 fg="#c9a84c", bg="#1a1208").pack(anchor="w")

        tk.Label(inner,
                 text=f"{self.prayer_name} prayer in {self.minutes_left} minutes",
                 font=("Georgia", 16, "bold"),
                 fg="#ffffff", bg="#1a1208").pack(anchor="w", pady=4)

        tk.Label(inner,
                 text="Prepare yourself • Make Wudu • Face Qibla",
                 font=("Georgia", 10),
                 fg="#8a7a5a", bg="#1a1208").pack(anchor="w")

        # Progress bar showing time
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Gold.Horizontal.TProgressbar",
                         troughcolor="#0a0a0f",
                         background="#c9a84c")
        bar = ttk.Progressbar(inner, style="Gold.Horizontal.TProgressbar",
                               length=380, mode="determinate", value=100)
        bar.pack(pady=6)

        # Auto-close after 30 seconds or when user clicks
        def close():
            root.destroy()

        root.after(30000, close)
        root.bind("<Button-1>", lambda e: close())

        # Countdown on bar
        remaining = [100]
        def tick():
            if remaining[0] > 0:
                remaining[0] -= 100 / 30
                bar["value"] = remaining[0]
                root.after(1000, tick)
            else:
                close()
        tick()
        root.mainloop()


# ─────────────────────────────────────────────
#  SYSTEM TRAY ICON
# ─────────────────────────────────────────────

def create_tray_icon():
    """Create a crescent-moon tray icon."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw crescent
    draw.ellipse([8, 8, 56, 56], fill="#c9a84c")
    draw.ellipse([18, 4, 58, 52], fill=(0, 0, 0, 0))
    # Star
    draw.ellipse([44, 10, 52, 18], fill="#c9a84c")
    return img


# ─────────────────────────────────────────────
#  MAIN DAEMON
# ─────────────────────────────────────────────

class PrayerDaemon:
    def __init__(self):
        # Re-read config fresh so any edits to config.json take effect on restart
        global CONFIG
        CONFIG = load_config()
        self.prayer_calc = PrayerTimes()
        self.lock_active = False
        self.warned = {}    # track which prayers we've warned about today
        self.locked = {}    # track which prayers we've locked for today
        self.running = True
        self.tray = None
        timing = CONFIG.get("timing", {})
        self.warn_minutes = timing.get("warning_minutes_before", 5)
        self.lock_minutes = timing.get("lock_duration_minutes", 10)
        # Push lock duration into PrayerLockScreen
        PrayerLockScreen.LOCK_DURATION = self.lock_minutes * 60

    def get_todays_times(self):
        return self.prayer_calc.get_times()

    def check_loop(self):
        logging.info("Prayer daemon check loop started.")
        while self.running:
            try:
                now = datetime.datetime.now()
                today = now.date()
                times = self.get_todays_times()

                for name, ptime in times.items():
                    prayer_dt = datetime.datetime.combine(today, ptime)
                    diff = (prayer_dt - now).total_seconds()

                    warn_key = f"{today}_{name}_warn"
                    lock_key = f"{today}_{name}_lock"

                    # Warning window (configurable minutes before prayer)
                    warn_secs = self.warn_minutes * 60
                    warn_low  = warn_secs - 60   # 1-minute window
                    warn_high = warn_secs + 60
                    if warn_low <= diff <= warn_high and warn_key not in self.warned:
                        self.warned[warn_key] = True
                        logging.info(f"Warning: {name} in ~{self.warn_minutes} minutes")
                        WarningWindow(name, self.warn_minutes)

                    # Lock screen when prayer time hits
                    if -30 <= diff <= 30 and lock_key not in self.locked and not self.lock_active:
                        self.locked[lock_key] = True
                        self.lock_active = True
                        logging.info(f"Lock screen triggered for {name}")
                        PrayerLockScreen(name, on_complete=self._on_lock_complete)

            except Exception as e:
                logging.error(f"Check loop error: {e}")

            time.sleep(10)

    def _on_lock_complete(self):
        self.lock_active = False
        logging.info("Lock screen completed.")

    def build_menu(self):
        def show_times(icon, item):
            times = self.get_todays_times()
            msg = "\n".join(f"{n}: {t.strftime('%I:%M %p')}" for n, t in times.items())
            # show in simple window
            root = tk.Tk()
            root.title("Today's Prayer Times")
            root.configure(bg="#0a0a0f")
            root.geometry("320x280")
            root.attributes("-topmost", True)
            tk.Label(root, text="🕌 Prayer Times", font=("Georgia", 16, "bold"),
                     fg="#c9a84c", bg="#0a0a0f").pack(pady=15)
            tk.Label(root, text=msg, font=("Courier New", 14),
                     fg="#ffffff", bg="#0a0a0f", justify="left").pack(pady=5, padx=20)
            tk.Button(root, text="Close", command=root.destroy,
                      bg="#c9a84c", fg="#0a0a0f",
                      font=("Georgia", 11, "bold")).pack(pady=15)
            root.mainloop()

        def quit_app(icon, item):
            self.running = False
            icon.stop()
            os._exit(0)

        return pystray.Menu(
            pystray.MenuItem("🕌 Prayer Times Today", show_times),
            pystray.MenuItem("Quit", quit_app),
        )

    def run(self):
        # Start check loop in background thread
        threading.Thread(target=self.check_loop, daemon=True).start()

        # System tray
        icon_img = create_tray_icon()
        self.tray = pystray.Icon(
            "PrayerReminder",
            icon_img,
            "Prayer Reminder",
            menu=self.build_menu()
        )
        logging.info("Prayer Reminder started.")
        self.tray.run()


if __name__ == "__main__":
    daemon = PrayerDaemon()
    daemon.run()
