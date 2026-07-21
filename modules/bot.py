import time
import requests
import sounddevice as sd
import numpy as np
import os
import re
import threading
import subprocess
from scipy.io.wavfile import write
from modules.hardware import hw
import modules.db_manager as db

# Force microphone default index routing
sd.default.device = (0, None)

# ================= CONFIGURATION =================
BOT_TOKEN = "7910070356:AAHnNWuR9n_IKEx7W7z5uDwYloJmsJ5Sj_s"

# Verified active Telegram architecture identities
GROUP_CHAT = "-1003471913010"  
ADMIN_CHAT = "1777632144"

DETECTION_ENABLED = True
WIFI_PENDING = None
CURRENT_NAME = None
LAST_UPDATE_ID = None
HEATING = False

# ================= TELEGRAM SEND OUTBOUND =================
def send_alert(chat_id, message):
    """Sends clear diagnostic text sequences to the requested target chat endpoint."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": str(chat_id), "text": message}, timeout=5)
        return r.status_code == 200
    except Exception as e:
        print(f"[Bot Error] Failed to send message: {e}")
        return False

# ================= VOICE NOTE PROCESSOR =================
def download_and_register_voice(file_id, name):
    """Downloads voice files from Admin DM and converts them to clean 16kHz WAV."""
    try:
        file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
        if "result" not in file_info:
            return False
            
        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        data = requests.get(file_url).content

        os.makedirs("staff", exist_ok=True)
        count = len([f for f in os.listdir("staff") if f.startswith(name)])
        
        ogg_file = f"staff/{name}{count+1}.ogg"
        wav_file = f"staff/{name}{count+1}.wav"

        with open(ogg_file, "wb") as f:
            f.write(data)

        # High quality transcode conversion using system audio pipelines
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', ogg_file, '-ar', '16000', '-ac', '1', wav_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        if os.path.exists(ogg_file):
            os.remove(ogg_file)

        if result.returncode == 0:
            db.add_staff(name)
            return True
        return False
    except Exception as e:
        print(f"Voice processor exception: {e}")
        return False

# ================= NETWORK PROVISIONS LAYER =================
def get_wifi_status():
    try:
        active = os.popen("nmcli -t -f active,ssid,signal dev wifi | grep '^yes'").read().strip()
        if active:
            parts = active.split(':')
            return f"📶 WiFi Status: Connected\nSSID: {parts[1]}\nSignal Strength: {parts[2]}%"
        return "❌ WiFi Status: Disconnected"
    except Exception as e:
        return f"Error gathering link parameters: {e}"

def get_saved_wifi():
    try:
        saved = os.popen("nmcli -t -f NAME,TYPE connection show | grep 802-11-wireless | cut -d: -f1").read().strip()
        if saved:
            formatted_list = "\n".join([f"💾 {net}" for net in saved.split('\n')])
            return f"📋 Saved WiFi Networks:\n\n{formatted_list}"
        return "No saved WiFi networks found. 📭"
    except Exception as e:
        return f"Error reading stored data structures: {e}"

def add_wifi(ssid, password):
    try:
        cmd = f'sudo nmcli connection add type wifi con-name "{ssid}" ifname wlan0 ssid "{ssid}" -- wifi-sec.key-mgmt wpa-psk wifi-sec.psk "{password}"'
        os.popen(cmd).read()
        os.system(f'sudo nmcli connection modify "{ssid}" connection.autoconnect yes')
        return f"Network '{ssid}' saved for later fallback! 💾✅\nIt will silently auto-connect if your main WiFi drops."
    except Exception as e:
        return f"WiFi entry injection failed ❌\n{str(e)}"

def delete_wifi(ssid):
    try:
        check = os.popen(f'nmcli connection show "{ssid}" 2>/dev/null').read()
        if not check:
            return f"Network '{ssid}' not found in saved list. ❌"
        os.system(f'sudo nmcli connection delete "{ssid}"')
        return f"Network '{ssid}' removed successfully! 🗑️✅"
    except Exception as e:
        return f"Delete failed ❌\n{e}"

# ================= TIMED HEATER ROUTINE =================
def parse_duration(text_val):
    """Parses customer text formats like '30s', '10m', '2h' into raw seconds."""
    match = re.match(r"^(\d+)([smh]?)$", text_val.lower().strip())
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    if unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    return value  # default fallback is seconds

def heat_sensor_routine(duration, caller_chat_id):
    global HEATING
    HEATING = True
    send_alert(caller_chat_id, f"Heating started 🔥")

    remaining = duration
    while remaining > 0:
        # Format the remaining calculation nicely onto the LCD layout screen
        if remaining >= 3600:
            time_str = f"{remaining // 3600}h {(remaining % 3600) // 60}m"
        elif remaining >= 60:
            time_str = f"{remaining // 60}m {remaining % 60}s"
        else:
            time_str = f"{remaining}s"
            
        hw.display_message("Heating...", time_str)
        time.sleep(1)
        remaining -= 1

    hw.display_message("Sensor Ready", "")
    send_alert(caller_chat_id, "Sensor Ready ✅")
    time.sleep(2)  # Hold status notification briefly

    # Return screen immediately to the expected IDLE state
    try:
        ssid = subprocess.check_output(["iwgetid", "-r"]).decode("utf-8").strip()
        ssid = ssid if ssid else "Disconnected"
    except:
        ssid = "No WiFi"
    hw.display_message("MINDFULME", ssid[:16])

    HEATING = False

# ================= PHYSICAL MIC RECORDING =================
def record_staff_voice_mic(name, caller_chat_id, duration=5):
    try:
        fs = 48000
        os.makedirs("staff", exist_ok=True)
        count = len([f for f in os.listdir("staff") if f.startswith(name)])
        
        final_filename = f"staff/{name}{count+1}.wav"
        temp_filename = f"staff/temp_{name}.wav"

        hw.display_message("Recording...", name[:16])
        audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        write(temp_filename, fs, audio)

        subprocess.run(
            ['ffmpeg', '-y', '-i', temp_filename, '-ar', '16000', '-ac', '1', final_filename],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

        hw.display_message("Saved", name[:16])
        send_alert(caller_chat_id, f"{name} added via physical mic ✅")
        db.add_staff(name)
    except Exception as e:
        send_alert(caller_chat_id, f"Mic recording failed ❌: {e}")

# ================= TELEGRAM PARSING PIPELINE =================
def process_incoming_updates():
    global LAST_UPDATE_ID, DETECTION_ENABLED, WIFI_PENDING, CURRENT_NAME

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        if LAST_UPDATE_ID:
            url += f"?offset={LAST_UPDATE_ID + 1}"
            
        data = requests.get(url, timeout=5).json()
    except:
        return

    for upd in data.get("result", []):
        LAST_UPDATE_ID = upd["update_id"]
        message = upd.get("message", {})
        chat_id = str(message.get("chat", {}).get("id"))
        
        if chat_id != GROUP_CHAT and chat_id != ADMIN_CHAT:
            continue

        if CURRENT_NAME and chat_id == ADMIN_CHAT:
            file_id = None
            if "voice" in message:
                file_id = message["voice"]["file_id"]
            elif "audio" in message:
                file_id = message["audio"]["file_id"]
            elif "document" in message:
                file_id = message["document"]["file_id"]

            if file_id:
                hw.display_message("Processing...", CURRENT_NAME[:16])
                if download_and_register_voice(file_id, CURRENT_NAME):
                    send_alert(ADMIN_CHAT, f"{CURRENT_NAME} added successfully ✅")
                    hw.display_message("Added", CURRENT_NAME[:16])
                else:
                    send_alert(ADMIN_CHAT, f"Error saving voice for {CURRENT_NAME} ❌")
                    hw.display_message("Error", "Save Failed")
                CURRENT_NAME = None
                continue

        text = message.get("text", "")
        if not text:
            continue

        if WIFI_PENDING:
            password = text.strip()
            if len(password) < 8:
                send_alert(chat_id, "Password must be at least 8 characters. Try again or type /cancel ❌")
                continue
            send_alert(chat_id, add_wifi(WIFI_PENDING, password))
            WIFI_PENDING = None
            continue

        if text == "/cancel":
            CURRENT_NAME = None
            WIFI_PENDING = None
            send_alert(chat_id, "Current operation cancelled ❌")
            continue

        # Command Routing Matrix
        if text.startswith("/add"):
            if chat_id != ADMIN_CHAT:
                send_alert(chat_id, "⚠️ Adding new staff voices can only be done in the private Admin DM.")
                continue
            parts = text.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                send_alert(ADMIN_CHAT, "Usage: /add Name")
            else:
                CURRENT_NAME = parts[1].strip()
                send_alert(ADMIN_CHAT, f"Please send the voice note for {CURRENT_NAME} now. 🎤")

        elif text.startswith("/remove"):
            if chat_id != ADMIN_CHAT:
                send_alert(chat_id, "⚠️ Removing staff voices can only be done in the private Admin DM.")
                continue
            parts = text.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                send_alert(ADMIN_CHAT, "Usage: /remove Name")
            else:
                target_name = parts[1].strip()
                removed_count = 0
                if os.path.exists("staff"):
                    for filename in os.listdir("staff"):
                        if filename.lower().startswith(target_name.lower()):
                            os.remove(os.path.join("staff", filename))
                            removed_count += 1
                if removed_count > 0:
                    db.remove_staff(target_name)
                    send_alert(ADMIN_CHAT, f"Removed {removed_count} voice file(s) for '{target_name}'. 🗑️✅")
                else:
                    send_alert(ADMIN_CHAT, f"No voice profiles found for '{target_name}'. ❌")

        elif text == "/staff":
            if not os.path.exists("staff") or not os.listdir("staff"):
                send_alert(chat_id, "No staff members are currently registered. 📭")
            else:
                # Clean filter: explicit inclusion check ignores local system temp capture audio waves
                names = {re.sub(r'\d+', '', f.rsplit('.', 1)[0]).capitalize() 
                         for f in os.listdir("staff") 
                         if f.endswith(('.wav', '.ogg')) and "temp" not in f.lower()}
                if not names:
                    send_alert(chat_id, "No staff members are currently registered. 📭")
                else:
                    list_str = "\n".join([f"👤 {n}" for n in sorted(names)])
                    send_alert(chat_id, f"📋 Registered Staff Members:\n\n{list_str}")

        elif text.startswith("/heat"):
            try:
                raw_val = text.split(" ", 1)[1]
                duration_secs = parse_duration(raw_val)
                if duration_secs is None or duration_secs <= 0:
                    raise ValueError
                threading.Thread(target=heat_sensor_routine, args=(duration_secs, chat_id), daemon=True).start()
            except:
                send_alert(chat_id, "⚠️ Invalid format! Examples:\n/heat 45s (Seconds)\n/heat 15m (Minutes)\n/heat 2h (Hours)")

        elif text.startswith("/wifi"):
            parts = text.split(" ")
            cmd = parts[1].lower() if len(parts) > 1 else ""
            if cmd == "status":
                send_alert(chat_id, get_wifi_status())
            elif cmd == "saved":
                send_alert(chat_id, get_saved_wifi())
            elif cmd == "add":
                if len(parts) < 3:
                    send_alert(chat_id, "Usage: /wifi add <SSID>")
                else:
                    WIFI_PENDING = parts[2].strip()
                    send_alert(chat_id, f"Please send the password for WiFi network: '{WIFI_PENDING}' 📶")
            elif cmd == "remove":
                if len(parts) < 3:
                    send_alert(chat_id, "Usage: /wifi remove <SSID>")
                else:
                    target_ssid = parts[2].strip()
                    send_alert(chat_id, delete_wifi(target_ssid))
            else:
                send_alert(chat_id, "🌐 WiFi Controls:\n/wifi status\n/wifi saved\n/wifi add <name>\n/wifi remove <name>")

        elif text == "/pause":
            DETECTION_ENABLED = False
            send_alert(chat_id, "System Paused ⏸")

        elif text == "/resume":
            DETECTION_ENABLED = True
            send_alert(chat_id, "System Resumed ▶")

        elif text.startswith("/mic"):
            parts = text.split(" ", 1)
            if len(parts) < 2:
                send_alert(chat_id, "Usage: /mic Name")
            else:
                threading.Thread(target=record_staff_voice_mic, args=(parts[1].strip(), chat_id), daemon=True).start()
                send_alert(chat_id, f"Recording {parts[1].strip()} via physical mic in 3 seconds... 🎤")

def bot_listener_loop():
    while True:
        process_incoming_updates()
        time.sleep(1)

def start():
    """Launches the listener thread cleanly inside scanner.py initialization."""
    threading.Thread(target=bot_listener_loop, daemon=True).start()
    send_alert(GROUP_CHAT, "Mindfulme System Started Online ✅")
