import time
import os
import subprocess
import numpy as np
import sounddevice as sd
from modules.hardware import hw
from modules.audio import audio_sys
import modules.db_manager as db
import modules.bot as bot
from config import ADMIN_CHAT, AUDIO_DEVICE_INDEX

def get_wifi_ssid():
    """Fetches the active WiFi network name dynamically for the LCD screen."""
    try:
        ssid = subprocess.check_output(["iwgetid", "-r"]).decode("utf-8").strip()
        return ssid if ssid else "Disconnected"
    except Exception:
        return "No WiFi"

def wait_for_voice_trigger(threshold=4500, check_duration=0.4):
    """
    Listens to the microphone in short bursts.
    Returns True when the peak sound wave height passes the set threshold.
    """
    sample_rate = 44100
    channels = 1

    while True:
        try:
            # Thread safety check: Hold listening sequence if bot is busy handling a private task
            if bot.HEATING or bot.CURRENT_NAME or not bot.DETECTION_ENABLED:
                time.sleep(0.5)
                continue

            # Capture a small window of sound
            recording = sd.rec(int(check_duration * sample_rate),
                               samplerate=sample_rate,
                               channels=channels,
                               device=AUDIO_DEVICE_INDEX,
                               dtype='int16')
            sd.wait()

            # Find the absolute peak amplitude within this audio window
            peak_volume = np.max(np.abs(recording))

            # Show real-time capture levels on terminal console
            print(f"Room noise check -> Current Peak Volume: {peak_volume}", end='\r')

            if peak_volume > threshold:
                print(f"\n⚡ Sound threshold passed! Volume: {peak_volume}")
                return True

        except Exception as e:
            time.sleep(0.1)
            continue

def run_scanner():
    print("🚀 Starting MindfulMe V2 Scanner Loop...")

    # Boot up the Telegram listener in the background
    bot.start()
    bot.send_alert(ADMIN_CHAT, "✅ MindfulMe System Online.")

    try:
        while True:
            # 1. IDLE STATE: "MINDFULME" on row 1, WiFi details down on row 2
            wifi_name = get_wifi_ssid()
            hw.display_message("MINDFULME", f"{wifi_name[:16]}")
            print(f"\n[IDLE Screen Active] Waiting for wake trigger... (WiFi: {wifi_name})")

            # Calibrated voice scanner baseline threshold check block
            wait_for_voice_trigger(threshold=32000)

            # 2. WAKE WORD DETECTED STATE: Clear screen matrix, display "SPEAK NOW" on row 1
            hw.display_message("SPEAK NOW", "")
            print("🎙️ Wake phrase registered. Capturing voice pattern profile...")

            # Record the voice profile for 5 seconds using your sounddevice module
            speech_file = audio_sys.record_audio(filename="temp_scan.wav", duration=5)

            if not speech_file:
                print("❌ Failed to output recording file safely. Returning to idle state.")
                continue

            # Visual analysis state transition hook
            hw.display_message("Analyzing...", "")
            name, confidence = audio_sys.identify_speaker(speech_file)

            # Read the actual live alcohol ppm content from the sensor hardware layer
            alcohol_val = hw.read_alcohol_ppm()

            # Calibrated safety threshold to 0.10 ppm to clear natural room noise baseline
            is_alcohol_safe = alcohol_val < 0.10 
            alcohol_status_str = "SAFE" if is_alcohol_safe else "DANGER / ALCOHOL DETECTED"

            # 3. IDENTIFICATION EVALUATION MATRIX (Professor Workflow Alignment)
            if name == "Background":
                line1 = "nosiy background"
                line2 = ""
                display_log_status = "FAILED"
                telegram_user_status = "Noisy Background"
                voice_status_str = "FAILED"
            elif name == "Unknown" or name is None:
                line1 = "sorry"
                line2 = "unknown"
                display_log_status = "FAILED"
                telegram_user_status = "Sorry, Unknown"
                voice_status_str = "FAILED"
            else:
                line1 = "thank you"
                line2 = f"{name.lower()}"
                display_log_status = "PASSED"
                telegram_user_status = name.capitalize()
                voice_status_str = "PASSED"

            # Render text matches onto the hardware lines
            hw.display_message(line1, line2)
            print(f"👤 Classifier Result: [{line1}] [{line2}] | Alcohol: {alcohol_val} ppm")

            # 4. TELEGRAM ALERT DISPATCH PIPELINE
            # Separated Voice Status and Alcohol Status for clear evaluation reporting
            current_time = time.strftime("%H:%M:%S")
            telemetry_alert_msg = (
                f"Mindfulme Staff Check 🚨\n\n"
                f"User: {telegram_user_status}\n"
                f"Voice Auth: {voice_status_str}\n"
                f"Alcohol: {alcohol_val:.2f} ppm\n"
                f"Status: {alcohol_status_str}\n"
                f"Time: {current_time}"
            )
            
            # Fire data packet straight to your configured target group endpoint chat
            bot.send_alert(bot.GROUP_CHAT, telemetry_alert_msg)

            # Keep database engine updated for your dashboard metric trends
            db.log_check_in(telegram_user_status, confidence, alcohol_val, display_log_status)

            # Hold screen output for 4.0 seconds so it can be verified visually
            time.sleep(4.0)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down scanner safely...")
        hw.display_message("System Offline", "")
    except Exception as e:
        print(f"❌ Unexpected Error in scanner loop: {e}")

if __name__ == "__main__":
    run_scanner()
