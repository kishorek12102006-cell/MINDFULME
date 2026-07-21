import time
import threading
import smbus2 as smbus
from RPLCD.i2c import CharLCD
from config import ALCOHOL_I2C_ADDR, LCD_I2C_ADDR

# Resilient Import handling for local module structures
try:
    from modules.DFRobot_Alcohol import DFRobot_Alcohol_I2C, MEASURE_MODE_AUTOMATIC
except ImportError:
    try:
        from DFRobot_Alcohol import DFRobot_Alcohol_I2C, MEASURE_MODE_AUTOMATIC
    except ImportError:
        print("⚠️ DFRobot_Alcohol.py not found in execution paths!")

# The secret weapon: A thread lock prevents data collisions on the I2C pins
i2c_lock = threading.Lock()

class HardwareController:
    def __init__(self):
        self.bus_number = 1
        self.bus = smbus.SMBus(self.bus_number)
        self.lcd = None
        self.alcohol_sensor = None

        self.setup_lcd()
        self.setup_alcohol_sensor()

    def setup_lcd(self):
        """Initializes the LCD safely."""
        with i2c_lock:
            try:
                self.lcd = CharLCD(i2c_expander='PCF8574', address=LCD_I2C_ADDR, port=self.bus_number)
                self.lcd.clear()
                self.lcd.write_string('MindfulMe V2\nSystem Ready')
                print("LCD Initialized Successfully.")
            except Exception as e:
                print(f"Hardware Error - LCD not found: {e}")
                self.lcd = None

    def setup_alcohol_sensor(self):
        """Initializes the DFRobot Alcohol Sensor and sets measurement parameters."""
        with i2c_lock:
            try:
                # 1 = I2C bus number, ALCOHOL_I2C_ADDR = 0x75
                self.alcohol_sensor = DFRobot_Alcohol_I2C(self.bus_number, ALCOHOL_I2C_ADDR)
                
                # Crucial Fix: Initialize internal configuration registers to active mode
                self.alcohol_sensor.set_mode(MEASURE_MODE_AUTOMATIC)
                print("Alcohol Sensor Initialized and Set to Automatic Mode Successfully.")
            except Exception as e:
                print(f"Hardware Error - Alcohol Sensor setup failed: {e}")
                self.alcohol_sensor = None

    def display_message(self, line1, line2=""):
        """Clears the screen and writes up to two lines of text."""
        if not self.lcd:
            return
        with i2c_lock:
            try:
                self.lcd.clear()
                self.lcd.cursor_pos = (0, 0)
                self.lcd.write_string(str(line1)[:16])
                if line2:
                    self.lcd.cursor_pos = (1, 0)
                    self.lcd.write_string(str(line2)[:16])
            except Exception as e:
                print(f"LCD Write Error: {e}")

    def read_alcohol_ppm(self):
        """
        Safely reads the alcohol concentration using DFRobot's conversion math.
        """
        if not self.alcohol_sensor:
            return 0.0

        with i2c_lock:
            try:
                # Take 20 samples and average them for a stable 0 - 5 ppm reading
                ppm = self.alcohol_sensor.get_alcohol_data(20)
                if ppm == -1:  # Check for driver error constant
                    return 0.0
                return round(ppm, 2)
            except Exception as e:
                print(f"Hardware Error - Sensor read failed: {e}")
                return 0.0

# Initialize a single global instance so the rest of the app can share it
hw = HardwareController()
