import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
import modules.db_manager as db_manager
from config import SECRET_KEY

# Initialize Flask App
app = Flask(__name__)
app.secret_key = SECRET_KEY

# Setup Flask-Login for Secure Sessions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class AdminUser(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    return AdminUser(username)

# Initialize DB and create default admin account if it doesn't exist
db_manager.init_db()
if not db_manager.verify_admin("admin", "admin123"):
    db_manager.create_admin("admin", "admin123")
    print("Default admin account created: admin / admin123")

# ================= ROUTES =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if db_manager.verify_admin(username, password):
            login_user(AdminUser(username))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    # Fetch all registered staff to display on the main control panel matrix
    staff_list = db_manager.get_all_staff()
    return render_template('index.html', staff=staff_list)

# ================= API ENDPOINTS =================

@app.route('/api/add_staff', methods=['POST'])
@login_required
def api_add_staff():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({"status": "error", "message": "Name is required"}), 400

    if db_manager.add_staff(name):
        return jsonify({"status": "success", "message": f"{name} added successfully!"}), 200
    else:
        return jsonify({"status": "error", "message": "Staff member already exists."}), 400

@app.route('/api/telemetry', methods=['GET'])
@login_required
def api_system_telemetry():
    """
    Polled every 2 seconds by index.html to dynamically pull check-in database logs
    directly into the dashboard view without breaking current browser states.
    """
    try:
        # Fetch raw check-in entries out of database storage safely
        if hasattr(db_manager, 'get_all_logs'):
            raw_logs = db_manager.get_all_logs()
        elif hasattr(db_manager, 'get_check_ins'):
            raw_logs = db_manager.get_check_ins()
        else:
            raw_logs = []

        formatted_logs = []
        latest_ppm = 0.0

        # Process the 5 most recent check-in system actions
        for index, entry in enumerate(raw_logs[:5]):
            if isinstance(entry, dict):
                name = entry.get('name', 'Unknown')
                confidence = entry.get('confidence', 0.0)
                sensor_val = entry.get('sensor_val', 0.0)
                status = entry.get('status', 'FAILED')
            else:
                # Array index safety checks mapping (name, confidence, sensor_val, status)
                name = entry[0]
                confidence = entry[1]
                sensor_val = entry[2]
                status = entry[3]

            # The very first index item represents the most recent system transaction
            if index == 0:
                latest_ppm = float(sensor_val)

            log_line = f"Access check: {name} (Conf: {confidence:.2f}) -> {status} [Val: {sensor_val} PPM]"
            formatted_logs.append(log_line)

        # Fallback messages if no scan activity is logged yet
        if not formatted_logs:
            formatted_logs = [
                "Voice_Core_Model: Initialized safely",
                "SEN0376_Sensor: Calibrated baseline (0.0 PPM)",
                "System Status: Awaiting check-in datastream..."
            ]

        return jsonify({
            "status": "success",
            "ppm": latest_ppm,
            "logs": formatted_logs
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "ppm": 0.0,
            "logs": [f"Telemetry Pipeline Error: {str(e)}"]
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
