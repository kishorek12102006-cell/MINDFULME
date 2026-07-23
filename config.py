import os

# ================= CORE CONFIGURATION =================
# Security Secret for Flask Login Sessions
SECRET_KEY = os.environ.get("MINDFULME_SECRET", "super-secret-dashboard-key-change-me")

# ================= TELEGRAM SETTINGS =================
# Replace with your actual bot token and your numeric chat ID
BOT_TOKEN = os.environ.get("MINDFULME_BOT_TOKEN", "bot token")
ADMIN_CHAT = "cht id"

# ================= HARDWARE SETTINGS =================
AUDIO_DEVICE_INDEX = 0  
ALCOHOL_I2C_ADDR = 0x75
LCD_I2C_ADDR = 0x27
ALCOHOL_THRESHOLD = 0.30
MIC_THRESHOLD = 0.001

# ================= DATABASE =================
DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'mindfulme.db')
