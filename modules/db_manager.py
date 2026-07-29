import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            voice_profile_path TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS check_ins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_name TEXT NOT NULL,
            confidence_score REAL,
            alcohol_ppm REAL,
            status TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

def create_admin(username, password):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        hashed = generate_password_hash(password, method='scrypt')
        cursor.execute('INSERT INTO admins (username, password_hash) VALUES (?, ?)', (username.lower(), hashed))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_admin(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM admins WHERE username = ?', (username.lower(),))
    row = cursor.fetchone()
    conn.close()
    if row and check_password_hash(row['password_hash'], password):
        return True
    return False

def add_staff(name, voice_path=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO staff (name, voice_profile_path) VALUES (?, ?)', (name.capitalize(), voice_path))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def remove_staff(name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM staff WHERE LOWER(name) = ?', (name.lower(),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Error] Failed to delete staff: {e}")
        return False

def get_all_staff():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM staff ORDER BY name ASC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def log_check_in(name, score, ppm, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO check_ins (staff_name, confidence_score, alcohol_ppm, status) VALUES (?, ?, ?, ?)',
                   (name, score, ppm, status))
    conn.commit()
    conn.close()

def get_check_ins(date_filter=None):
    """Fetches check-ins using local time matching."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if date_filter:
            cursor.execute('''
                SELECT staff_name AS name, confidence_score AS confidence, alcohol_ppm AS sensor_val, status, 
                       DATETIME(timestamp, 'localtime') AS timestamp 
                FROM check_ins 
                WHERE DATE(timestamp, 'localtime') = DATE(?)
                ORDER BY id DESC
            ''', (date_filter,))
        else:
            cursor.execute('''
                SELECT staff_name AS name, confidence_score AS confidence, alcohol_ppm AS sensor_val, status, 
                       DATETIME(timestamp, 'localtime') AS timestamp 
                FROM check_ins 
                ORDER BY id DESC 
                LIMIT 100
            ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB Error] Failed to fetch check-ins: {e}")
        return []

def prune_old_logs(days=30):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM check_ins WHERE timestamp < DATETIME('now', '-' || ? || ' days')", (days,))
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.execute("VACUUM;")
        conn.close()
        return deleted_count
    except Exception as e:
        print(f"[DB Error] Prune failed: {e}")
        return 0
