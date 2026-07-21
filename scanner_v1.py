import time
from modules.hardware import hw
from modules.audio import audio_sys
from modules.bot import bot
import modules.db_manager as db
from config import ALCOHOL_THRESHOLD, ADMIN_CHAT

def run_scanner():
    print("🚀 Starting MindfulMe V2 Scanner Loop...")

    # 1. Boot up the Telegram listener in the background
    bot.start()
    bot.send_alert(ADMIN_CHAT, "✅ MindfulMe V2 System Online and Ready.")

    try:
        while True:
            # 2. Reset the physical screen for the next user
            hw.display_message("MindfulMe Ready", "Please speak...")
            print("\nWaiting for voice check-in...")

            # 3. Trigger recording (You can eventually tie this to a motion sensor or mic threshold)
            audio_file = audio_sys.record_audio(duration=5)
            if not audio_file:
                time.sleep(2)
                continue

            # 4. Pass the recording to the AI module
            hw.display_message("Analyzing Voice", "Please wait...")
            name, confidence = audio_sys.identify_speaker(audio_file)

            # If the AI isn't confident, reject the check-in
            if confidence < 0.7:
                hw.display_message("Unknown Voice", "Please try again")
                print("Unrecognized speaker.")
                time.sleep(3)
                continue

            # 5. Prompt for the alcohol test
            hw.display_message(f"Hi {name}!", "Blow into sensor")
            print(f"User identified: {name}. Waiting for breathalyzer...")

            # Give the user a moment to lean into the sensor
            time.sleep(2)

            # 6. Take the reading safely using our thread lock
            ppm = hw.read_alcohol_ppm()
            print(f"Reading captured: {ppm} PPM")

            # 7. Evaluate, Log, and Alert
            if ppm >= ALCOHOL_THRESHOLD:
                status = "FAILED"
                hw.display_message("TEST FAILED", f"Level: {ppm} PPM")
                bot.send_alert(ADMIN_CHAT, f"🚨 *ALERT:* {name} failed check-in with {ppm} PPM!")
            else:
                status = "PASSED"
                hw.display_message("TEST PASSED", f"Level: {ppm} PPM")
                bot.send_alert(ADMIN_CHAT, f"✅ {name} passed check-in ({ppm} PPM).")

            # 8. Save directly to the SQLite database so it shows up on the web dashboard
            db.log_check_in(name, confidence, ppm, status)

            # Pause before resetting for the next person
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down scanner safely...")
        hw.display_message("System Offline", "")
    except Exception as e:
        print(f"❌ Unexpected Error in scanner loop: {e}")

if __name__ == "__main__":
    run_scanner()
