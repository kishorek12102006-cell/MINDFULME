# MindfulMe — Onboarding Guide for New Contributors


## 1. What this project is

MindfulMe is a Raspberry Pi–based workplace safety kit that combines:
- **Voice biometric check-in** — identifies a staff member by their voice.
- **Breath alcohol telemetry** — an electrochemical sensor reads BAC (in PPM) during the same check-in.
- **Remote administration** — a Telegram bot for live alerts and admin commands, plus a browser-based web portal for enrollment and log management.

The full user-facing workflow (boot sequence, check-in steps, response codes, troubleshooting table) is documented in the project PDF — read that first for the *product* behavior before touching code.

## 2. System architecture

```
                     ┌───────────────────────┐
   USB Mic  ───────▶ │                       │
   Alcohol Sensor ──▶│   Raspberry Pi        │◀──── LCD (16x2, status/prompts)
   (electrochemical) │   (main.py / Flask)   │
                     │                       │
                     └──────────┬────────────┘
                                │
                 ┌──────────────┼───────────────┐
                 ▼              ▼               ▼
          modules/audio.py  modules/hardware.py  db_manager.py
          (voice capture,   (LCD, sensor,        (SQLite: staff,
           speaker match,    Wi-Fi via nmcli)     check-in logs,
           centroid vectors)                      admin creds)
                 │
                 ▼
          voice_profiles/  (per-staff .npy centroid vectors)
```

- **Web app**: Flask + `flask_login`, two roles (`admin` / `customer`), served on port `5000`.
- **Voice matching**: each staff member's voice is reduced to an averaged "centroid" vector saved as a `.npy` file in `voice_profiles/`, built from 10 samples (5 near-field @ 3–6", 5 far-field @ ~1 ft). Real-time check-ins are compared against these centroids for a match.
- **Alcohol sensor**: read through `modules/hardware.py` (`hw.read_alcohol_ppm()`), tied to a `sensor_catalog.json` (likely calibration/reference data — confirm on read).
- **Wi-Fi management**: done via shelling out to `nmcli`/`iwgetid`, not a Python Wi-Fi library — this only works when running directly on Raspberry Pi OS.
- **Persistence**: SQLite via `modules/db_manager.py` — staff directory, check-in logs (with confidence score + PPM + status), admin login credentials.

## 3. Repo file map

| File / folder | Purpose |
|---|---|
| `main.py` | The active Flask app. Routes for login, dashboards, hardware enrollment, staff CRUD, telemetry, diagnostics stream, Wi-Fi management, mic test, system shutdown. **This is the entry point — start reading here.** |
| `main_legacy.py` | An older version of the app. Useful to diff against `main.py` to see what changed, but don't build on it. |
| `config.py` | Holds `SECRET_KEY` and likely other constants — check what else lives here. |
| `modules/hardware.py` | Hardware interfacing — LCD display, Wi-Fi control via `nmcli`, and the entry point for alcohol sensor reads (`hw.read_alcohol_ppm()`). Likely wraps `DFRobot_Alcohol.py` rather than talking to the sensor directly. |
| `modules/audio.py` | Voice biometrics — recording, building the per-staff centroid vectors, and matching a live sample against `voice_profiles/`. |
| `modules/db_manager.py` | SQLite layer — staff directory, check-in logs, admin credentials. |
| `modules/DFRobot_Alcohol.py` | Official DFRobot driver for the alcohol sensor (matches the "SEN0376" reference in `main.py`'s telemetry log). Supports both I2C (default addresses `0x72`–`0x75`) and UART (`/dev/ttyAMA0`) wiring, and both automatic (continuous) and passive (on-demand) read modes. Returns PPM as `raw_value / 1000.0`, averaged over a rolling sample window (`get_average_num`). This is vendor code — don't modify it, just call into it from `hardware.py`. |
| `modules/bot.py` | The Telegram bot — implements `/mic`, `/pause`, `/resume`, `/staff`, `/heat`, `/wifi status/add/remove`, and the admin-only `/add` / `/remove`. |
| `modules/bot_leagcy.py` | Earlier version of the bot (note the typo in the filename itself — it's `bot_leagcy.py`, not `bot_legacy.py`. Worth a quick rename during cleanup so it doesn't look like a deliberate naming scheme). |
| `templates/` | Flask/Jinja2 HTML templates (`login.html`, `index.html`, `customer_dashboard.html`, `diagnostics.html`, etc.) |
| `voice_profiles/` | Saved `.npy` centroid vectors, one per enrolled staff member. |
| `dataset/` | Likely training/reference audio or sensor data — confirm contents. |
| `record_samples.py` | Standalone script, probably for capturing raw audio samples outside the web flow (testing/debugging the mic). |
| `scanner.py` / `scanner_v1.py` | Continuous background scanner logic (referenced by the Telegram `/pause` and `/resume` commands) — `scanner.py` is current, `scanner_v1.py` is the earlier version. |
| `sensor_catalog.json` | Reference/calibration data for the alcohol sensor. |
| `test_sensor_dash.py` | A test/debug script for the sensor dashboard — good starting point for a junior to run in isolation without the full app. |
| `voice_model.pkl` | A pickled model artifact — clarify whether this is still used by `audio.py` or is legacy, since the current approach (per `main.py`) looks centroid-based rather than a trained classifier. |

## 4. Getting it running

1. **Hardware**: Raspberry Pi, USB microphone, electrochemical alcohol sensor, 16×2 LCD, stable 5V USB-C power. Boot takes ~30s — don't interrupt power mid-boot (can corrupt the voice database).
2. **Software**: clone the repo on the Pi, install dependencies (check for a `requirements.txt`; if none exists, that's the first gap to fill — list what `main.py` imports: `flask`, `flask_login`, plus whatever `modules/audio.py` uses for audio/ML, likely something like `sounddevice`/`pyaudio` + `numpy`/`librosa`).
3. **Run**: `python main.py` — starts on `0.0.0.0:5000`, so it's reachable at `http://mindfulme.local:5000` or `http://<pi-ip>:5000` on the local network.
4. **Default login**: on first run, `main.py` auto-creates an admin account — **`admin` / `admin123`**. Change this before handing the kit to anyone outside your immediate team; it's hardcoded in `main.py` right now.
5. **Enroll staff**: via the web portal → Active Staff Directory → "Enroll via Kit Mic" → 10-sample near/far protocol.

## 5. Telegram bot

Group-accessible commands: `/mic <name>`, `/pause`, `/resume`, `/staff`, `/heat <duration>`, `/wifi status`, `/wifi add <ssid>`, `/wifi remove <ssid>`.
Admin DM-only: `/add <name>`, `/remove <name>` (irreversible).

The bot's own source isn't visible in the top-level file list — it's likely inside `modules/` or a file not yet inspected. Find and document it next.



## 6. Suggested first tasks for a junior

1. Read `main.py` top to bottom, then `modules/hardware.py` and `modules/audio.py`.
2. Run `test_sensor_dash.py` in isolation to see the alcohol sensor pipeline without the full web app.
3. Write the missing `requirements.txt` by tracing every import.
4. Do one full enrollment + check-in cycle on the physical kit, side-by-side with the PDF guide.
